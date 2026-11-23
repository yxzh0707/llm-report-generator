"""Build a Chinese, single-file, one-question-at-a-time pre-review packet."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LABELS={'supported':'证据支持','contradicted':'证据矛盾','insufficient':'证据不足',
        'satisfied':'满足要求','not_satisfied':'不满足要求','uncertain':'暂无法确定'}
CELLS_ZH={'T1_uploaded_only':'NVIDIA年报','T2_uploaded_only':'NVIDIA双文档综合',
 'T3_uploaded_only':'AMD年报','T4_uploaded_only':'AMD双文档综合',
 'T5_uploaded_only':'两公司比较·上传','T5_web_only':'两公司比较·网络',
 'T6_hybrid':'两公司比较·混合','C_structure':'结构定制配对','C_style':'风格定制配对','C_depth':'深度定制配对'}
DOCS={
 'nvidia_fy2025_10k':{'title_zh':'NVIDIA 2025财年年报（Form 10-K）','why_zh':'用于核对业务、全年业绩和风险；这是任务指定的年度主资料。财年截至2025-01-26。'},
 'nvidia_fy2025_q4_cfo_commentary':{'title_zh':'NVIDIA 2025财年第四季度及全年CFO说明','why_zh':'用于补充第四季度及全年业绩、市场平台和分部口径；与年报组成两文档综合任务，不称作电话会议记录。材料本身发布日期未确认。'},
 'amd_fy2024_10k':{'title_zh':'AMD 2024财年年报（Form 10-K）','why_zh':'用于核对AMD业务、全年业绩、分部和风险；财年截至2024-12-28，与NVIDIA财年并不完全一致。'},
 'amd_fy2024_q4_release':{'title_zh':'AMD 2024年第四季度及全年财务业绩公告','why_zh':'用于补充季度及年度数字、分部业绩和管理层说明，并与年报区分证据范围。'},
}


def sha(data):return hashlib.sha256(data).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def build(session,partial=False):
    session=Path(session).resolve()
    m=json.loads((session/'manifest.json').read_text())
    for rel,expected in m['original_artifact_sha256'].items():
        if sha((ROOT/rel).read_bytes())!=expected:
            raise ValueError('Original report/human input changed during model pre-review: '+rel)
    translation_path=session/'translations_zh.json'
    translations=json.loads(translation_path.read_text()) if translation_path.exists() else {'items':{}}
    runs={};items=[];missing=[]
    for qid in m['question_order']:
        path=session/'questions'/(qid+'.json')
        if sha(path.read_bytes())!=m['question_sha256'][qid]:raise ValueError('Question changed: '+qid)
        q=json.loads(path.read_text());result_path=session/'results'/(qid+'.json')
        if not result_path.exists():missing.append(qid);continue
        r=json.loads(result_path.read_text())
        if r['qid']!=qid or r['input_sha256']!=m['question_sha256'][qid] or r['actual_human_reviewed'] is not False:
            raise ValueError('Result identity/type mismatch: '+qid)
        source_map={s['citation']:s for s in q['sources']}
        for check in r['evidence_checks']:
            s=source_map[check['source_id']];start=check['char_start']-s['char_start'];end=check['char_end']-s['char_start']
            if s['text'][start:end]!=check['quote_en']:raise ValueError('Saved source quote/range changed: '+qid)
        supplement=translations['items'].get(qid,[])
        if supplement:
            if len(supplement)!=len(r['evidence_checks']):raise ValueError('Translation evidence count differs: '+qid)
            for translated,check in zip(supplement,r['evidence_checks']):
                if translated['quote_sha256']!=sha(check['quote_en'].encode()):raise ValueError('Translation refers to a different quote')
                check['literal_translation_zh']=translated['translation_zh']
        for check in r['report_checks']:
            if q['raw_report'][check['char_start']:check['char_end']]!=check['quote_en']:raise ValueError('Saved report quote/range changed: '+qid)
        if q['run_id'] not in runs:
            runs[q['run_id']]={k:q[k] for k in ('run_id','cell','run_dir','request','raw_report','raw_report_sha256','sources')}
        items.append({'qid':qid,'kind':q['kind'],'cell':q['cell'],'run_id':q['run_id'],
            'cell_label_zh':CELLS_ZH.get(q['cell'].rsplit('_r',1)[0],q['cell'])+' · 第'+q['cell'].rsplit('_r',1)[1]+'次',
            'item_id':q.get('item_id'),'criterion':q['criterion'],'exact_claim':q.get('exact_claim'),
            'original_citation_ids':q.get('original_citation_ids',[]),'question_sha256':m['question_sha256'][qid],
            'result_sha256':sha(result_path.read_bytes()),'result':r})
    if missing and not partial:raise ValueError(f'{len(missing)} judgments pending; use --partial only for a development preview')
    counts={kind:dict(Counter(i['result']['judgment'] for i in items if i['kind']==kind)) for kind in ('source_support','content')}
    summary={'purpose':'model_assisted_pre_review','judge':m['judge'],'planned':m['items_planned'],
        'accepted':len(items),'complete':not missing,'missing':missing,'counts':counts,
        'actual_human_judgments_added':0,'human_gate_passed':False,
        'cost':m['budget']['judge_cost'],'tokens':m['budget']['judge_tokens'],
        'review_started_at':m['created_at'],'built_at':datetime.now(timezone.utc).isoformat(),
        'first_result_at':items[0]['result']['accepted_at'] if items else None,
        'last_result_at':items[-1]['result']['accepted_at'] if items else None,
        'limitations':['Post-hoc model pre-review, not human evaluation or factual accuracy ground truth.',
          'No measured agreement with human reviewers; confidence is uncalibrated.',
          'All original reports, evidence, automatic outcomes and human inputs preserved.',
          'Collaboration model token/call usage and fees are not exposed; unknown.',
          'Original weak/non-material sample claims retained and flagged rather than resampled.',
          'The prespecified first-five sample emphasizes early report claims; its support counts cannot represent every fact in the reports.']}
    summary['source_selection_suitability']={s:{'count':sum(i['kind']=='source_support' and i['result']['selection_suitability']==s for i in items),
        'judgments':dict(Counter(i['result']['judgment'] for i in items if i['kind']=='source_support' and i['result']['selection_suitability']==s))}
        for s in ('material','less_material')}
    summary['content_by_group']={g:dict(Counter(i['result']['judgment'] for i in items if i['kind']=='content' and i['cell'].startswith(prefix)))
        for g,prefix in (('main','T'),('customization','C'))}
    summary['limitations'].append('One sequential worker conversation is reused; per-item judgments do not have fresh independent model contexts.')
    if items:
        summary['preparation_to_last_acceptance_seconds']=(datetime.fromisoformat(items[-1]['result']['accepted_at'])-datetime.fromisoformat(m['created_at'])).total_seconds()
        summary['elapsed_scope']='Wall-clock span from packet preparation to last acceptance, including tool work; not pure model latency.'
    trace=[{'event':'review_packets_prepared','at':m['created_at'],'planned':m['items_planned'],
            'manifest_sha256':sha((session/'manifest.json').read_bytes())}]
    trace.extend({'event':'model_judgment_accepted','sequence':n,'qid':i['qid'],
        'at':i['result']['accepted_at'],'input_sha256':i['question_sha256'],
        'result_sha256':i['result_sha256'],'judgment':i['result']['judgment'],
        'trace_scope':'acceptance-event projection; native model/tool trajectory not exposed'} for n,i in enumerate(items,1))
    (session/'decision_trace.jsonl').write_text(''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in trace))
    bundle={'session':session.name,'freeze_id':m['freeze_id'],'manifest_sha256':sha((session/'manifest.json').read_bytes()),
        'summary':summary,'documents':DOCS,'runs':runs,'items':items}
    save(session/'summary.json',summary);save(session/'review_bundle.json',bundle)
    with (session/'per_item.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['qid','kind','cell','item_id','criterion','judgment','confidence','judgment_type','actual_human_reviewed'])
        writer.writeheader()
        for i in items:writer.writerow({**{k:i.get(k) for k in ('qid','kind','cell','item_id','criterion')},
            'judgment':i['result']['judgment'],'confidence':i['result']['confidence'],
            'judgment_type':'model_assisted_pre_review','actual_human_reviewed':False})
    data=json.dumps(bundle,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    html=HTML.replace('__REVIEW_DATA__',data)
    (session/'review_zh.html').write_text(html)
    delivery=ROOT/'docs/model_review_zh.html'
    if not missing:delivery.write_text(html)
    lines=['# Astra high 中文逐题预评','',
        f'已接受 {len(items)}/{m["items_planned"]} 题；真实人工评分新增0条。',
        '主要入口：review_zh.html。该单文件在浏览器打开，每次只显示一道题，中文解释在前，英文原稿与证据可展开。',
        '每道题均保留原报告、来源URL、实际提供给模型的区间、输入/结果hash和判断理由。',
        '这是模型辅助预评，不能称为人工评分或人类准确率。未改写原正式生成及人工工作表。','',
        '## 模型预评计数','',f'事实支持（预选20条）：{counts["source_support"]}',
        f'内容/风格/深度（123项）：{counts["content"]}','',
        f'事实候选适合度分列（由模型提出，待人工确认）：{summary["source_selection_suitability"]}', '',
        '## 语料来源和选用原因','']
    for name,doc in DOCS.items():lines.extend([f'- {doc["title_zh"]}：{doc["why_zh"]}'])
    lines.extend(['','网络资料为正式任务当时打开并冻结的官方业绩网页快照；hybrid同时包含上传及网页两类证据。来源类别取决于本次获取路径，同一官方公告可作为上传文件或网页快照，不能据官网域名误判来源模式。',
        '人工复核时填写评审者，逐题确认或改判，然后导出人工复核JSON；浏览器中的确认记录不会自动写回原评分文件。',
        '弱事实型候选保留原样并分列，不用它们提高重要事实支持率。若实际评审者要替换，请暂跳过并提供同一原稿中的新原句及原因，按原selection_change合同记录后再评分。','',
        '## 逐题索引','', '| 题号 | 报告 | 类型 | 模型预评 | 信心（未校准） |','|---|---|---|---|---|'])
    for i in items:lines.append(f'| {i["qid"]} | {i["cell"]} | {"事实支持" if i["kind"]=="source_support" else "内容/定制"} | {LABELS[i["result"]["judgment"]]} | {i["result"]["confidence"]} |')
    (session/'README_zh.md').write_text('\n'.join(lines)+'\n')
    save(session/'presentation_manifest.json',{'builder_sha256':sha(Path(__file__).read_bytes()),
        'bundle_sha256':sha((session/'review_bundle.json').read_bytes()),'html_sha256':sha((session/'review_zh.html').read_bytes()),
        'summary_sha256':sha((session/'summary.json').read_bytes()),'original_inputs_preserved':True,
        'display_translation_sha256':sha(translation_path.read_bytes()) if translation_path.exists() else None,
        'delivery_copy':str(delivery.relative_to(ROOT)) if not missing else None,
        'delivery_sha256':sha(delivery.read_bytes()) if not missing else None,
        'decision_trace_sha256':sha((session/'decision_trace.jsonl').read_bytes())})
    print(json.dumps({'session':str(session),'accepted':len(items),'missing':len(missing),'counts':counts},ensure_ascii=False))
    return session/'review_zh.html'


HTML=r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>中文逐题复核 · LLM-Based Report Generator</title>
<style>
:root{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft Yahei",sans-serif;color:#192c3c;background:#f3f5f7;line-height:1.7}*{box-sizing:border-box}body{margin:0}main{max-width:1000px;margin:30px auto;padding:0 22px 50px}header{margin-bottom:20px}h1{font-size:27px;line-height:1.4;margin-bottom:8px}h2{font-size:21px}h3{font-size:16px;margin:0 0 8px}.muted{font-size:13px;color:#627484}.toolbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:16px 0}button,select,input,textarea{font:inherit;border:1px solid #c7d2dc;border-radius:8px;padding:8px 12px}button{cursor:pointer;background:#fff;color:#223e54}button.primary{background:#155e75;color:white;border-color:#155e75}button:disabled{opacity:.45;cursor:default}input{min-width:180px}select{max-width:100%}textarea{width:100%;min-height:80px;resize:vertical}.card{background:white;border:1px solid #dce3e9;border-radius:14px;padding:22px;margin:14px 0;box-shadow:0 2px 5px #182c3c04}.chip{display:inline-block;background:#e7f0f4;color:#24546b;padding:2px 9px;border-radius:20px;font-size:12px;margin-right:7px}.verdict{font-size:20px;font-weight:650;color:#155e75}.verdict.bad{color:#a03d32}.verdict.unknown{color:#8b6526}.warn{background:#fff7e4;border-left:4px solid #b58222;padding:12px 16px;border-radius:6px}.quote{border-left:3px solid #9bb9c6;padding-left:14px;margin:12px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.65 ui-monospace,SFMono-Regular,monospace;background:#f5f7f9;padding:14px;border-radius:8px;max-height:440px;overflow:auto}summary{cursor:pointer;color:#24546b;margin:8px 0}a{color:#176980;overflow-wrap:anywhere}p{margin:8px 0 14px}.label{font-size:13px;color:#526c7f}.check{display:flex;gap:10px;align-items:flex-start}.check input{min-width:auto;margin-top:8px}#notice{color:#946018;font-weight:600}#rawContext{max-height:500px}.stats{font-size:13px;padding:8px 0}.origin{background:#f4f7f9;padding:10px 13px;border-radius:8px;margin-top:8px}.end{font-size:12px;color:#6a7884;margin-top:20px}@media(max-width:600px){main{padding:0 12px;margin-top:15px}.card{padding:16px}h1{font-size:23px}.toolbar>*{max-width:100%}}
</style><main>
<header><div class="label">LLM-Based Report Generator · 中文复核包</div><h1>一次核对一个问题</h1><p>先看中文陈述、Astra high 的理由和关键证据；需要时再展开英文原文。模型预评与实际人工确认分别保存。</p><div id="stats" class="stats"></div></header>
<details class="card"><summary>语料从哪里来，为什么选这些材料？</summary><div id="corpus"></div><p class="muted">只有本次实际提供给生成模型的正文可作为预评证据。所有原文保留英文，中文为复核辅助翻译；网页为当时已冻结的快照。本批模型评分未经人类一致性校准。</p></details>
<div class="toolbar"><select id="filter" aria-label="筛选问题"><option value="all">全部问题</option><option value="source_support">事实支持（20题）</option><option value="content">内容与定制（123题）</option><option value="pending">尚未人工确认</option><option value="issues">先看未满足／不确定／证据不足</option><option value="uncertain">模型判断不确定或证据不足</option><option value="priority">优先复核：不通过／低信心／选样疑问</option></select><select id="jump" aria-label="跳转题号"></select><button id="prev">上一题</button><button id="next">下一题</button></div>
<section id="question"></section><section class="card" id="human"><h2>你的复核</h2><p class="muted">实际查看本题后再确认。未确认的题保持未审；本页不会自动代填人工评分文件。</p><label>评审者 <input id="reviewer" placeholder="姓名或固定评审者编号" autocomplete="off"></label><p class="check" id="selectionRow"><input type="checkbox" id="selection"><label for="selection">确认此原句适合作为本次重要事实抽样项（不代表认定事实正确）</label></p><div class="toolbar"><select id="humanLabel" aria-label="人工判断"></select></div><p id="sourceIdsRow"><label for="humanSources">实际核对的来源编号</label><input id="humanSources" placeholder="例如 [S2] [S4]" style="width:100%"></p><label for="humanReason">你的理由（接受预评时可留空；修改判断时请说明）</label><textarea id="humanReason" placeholder="例如：原文仅报告收入增长，不能充分支持所述因果关系。"></textarea><div class="toolbar"><button class="primary" id="accept">核对后接受预评，并下一题</button><button id="override">保存我的判断，并下一题</button><button id="skip">暂时跳过</button></div><p id="notice" role="status"></p></section>
<div class="toolbar"><button id="export">导出人工复核记录</button><span class="muted">确认记录保存在当前浏览器；导出后交回项目导入。</span></div><p class="end">模型预评不是人工评测。信心等级未校准；不代表准确率。原正式生成与自动结果未因预评改变。</p>
</main><script id="review-data" type="application/json">__REVIEW_DATA__</script><script>
'use strict';const B=JSON.parse(document.getElementById('review-data').textContent),L={supported:'证据支持',contradicted:'证据矛盾',insufficient:'证据不足',satisfied:'满足要求',not_satisfied:'不满足要求',uncertain:'暂无法确定'},K='dissa-review-'+B.session+'-'+B.manifest_sha256;let state={reviewer:'',answers:{}},pos=0;try{state=JSON.parse(localStorage.getItem(K))||state}catch(e){}if(!state.answers)state.answers={};const $=id=>document.getElementById(id);function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n}function p(parent,text,cls){parent.append(el('p',text,cls))}function details(parent,title,text){const d=el('details');d.append(el('summary',title),el('pre',text));parent.append(d)}function persist(){try{localStorage.setItem(K,JSON.stringify(state))}catch(e){$('notice').textContent='浏览器无法持久保存，请及时导出记录。'}}function filtered(){const f=$('filter').value;return B.items.filter(i=>f==='all'||i.kind===f||(f==='pending'&&!state.answers[i.qid])||(f==='issues'&&['insufficient','uncertain','not_satisfied','contradicted'].includes(i.result.judgment))||(f==='uncertain'&&['insufficient','uncertain'].includes(i.result.judgment))||(f==='priority'&&(['insufficient','uncertain','not_satisfied'].includes(i.result.judgment)||i.result.confidence!=='high'||i.result.selection_suitability==='less_material')))}function current(){return filtered()[pos]}function stat(){const source=Object.values(state.answers).filter(a=>a.kind==='source_support').length,content=Object.values(state.answers).filter(a=>a.kind==='content').length;$('stats').textContent=`模型预评 ${B.summary.accepted}/${B.summary.planned} · 本浏览器人工确认：事实 ${source}/20，内容/定制 ${content}/123。`}
function origin(source){const box=el('div',undefined,'origin'),doc=B.documents[source.document_id];p(box,(source.source_kind==='web'?'网页快照':'上传文档')+' · '+(doc?doc.title_zh:source.title||source.document_id));if(source.source_url){const a=el('a','查看原始发布来源');a.href=source.source_url;a.target='_blank';a.rel='noopener noreferrer';box.append(a)}return box}
function render(){const a=filtered();if(pos>=a.length)pos=Math.max(0,a.length-1);$('jump').replaceChildren(...a.map((i,n)=>{const o=el('option',i.qid+' · '+i.cell_label_zh+(state.answers[i.qid]?' ✓':''));o.value=n;return o}));$('jump').value=pos;stat();const q=$('question');q.replaceChildren();$('notice').textContent='';if(!a.length){q.append(el('div','此筛选条件下没有待显示的问题。','card'));$('human').hidden=true;return}$('human').hidden=false;const i=a[pos],r=i.result,run=B.runs[i.run_id],c=el('div',undefined,'card');c.append(el('span',i.qid+' / '+B.summary.planned,'chip'),el('span',i.kind==='source_support'?'事实支持':'内容与定制','chip'),el('span',i.cell_label_zh,'chip'),el('h2',r.question_zh));p(c,'任务：'+r.request_summary_zh,'muted');if(i.kind==='source_support'){p(c,r.claim_zh,'quote');details(c,'查看英文原句及原引用',i.exact_claim+'\n\n原引用：'+(i.original_citation_ids.join(' ')||'本句没有识别到引用编号'));if(r.selection_suitability==='less_material')p(c,'选样提示：此句可能不是重要事实型陈述。保留原候选供你复核，未自动换样。','warn')}p(c,'Astra high 预评：'+L[r.judgment],'verdict'+(['contradicted','not_satisfied'].includes(r.judgment)?' bad':['insufficient','uncertain'].includes(r.judgment)?' unknown':''));p(c,'模型自报信心：'+({high:'高',medium:'中',low:'低'}[r.confidence])+'（未校准）','muted');p(c,r.rationale_zh);if(r.uncertainties_zh)p(c,r.uncertainties_zh,'warn');q.append(c);
const proofs=el('div',undefined,'card');proofs.append(el('h3','关键证据与中文说明'));if(!r.evidence_checks.length&&!r.report_checks.length)p(proofs,'未提供可逐字定位的关键引文；请根据理由检查完整上下文。','muted');for(const v of r.report_checks){const x=el('div',undefined,'quote');p(x,i.kind==='source_support'&&v.quote_en===i.exact_claim?r.claim_zh:v.interpretation_zh);details(x,'展开报告原句 · 第'+v.line+'行',v.quote_en);proofs.append(x)}for(const v of r.evidence_checks){const x=el('div',undefined,'quote');if(v.literal_translation_zh){p(x,v.literal_translation_zh);p(x,'预评说明：'+v.interpretation_zh,'muted')}else{p(x,v.interpretation_zh)}const source=run.sources.find(s=>s.citation===v.source_id);x.append(origin(source));details(x,v.source_id+' · 查看英文证据及字符位置',v.quote_en+'\n\n规范化正文字符区间 ['+v.char_start+', '+v.char_end+')；实际返回区间 ['+v.returned_char_start+', '+v.returned_char_end+')');proofs.append(x)}const context=el('details');context.append(el('summary','需要更多上下文？展开英文原报告与全部返回证据'));details(context,'英文原始报告（不含事后修订）',run.raw_report);for(const s of run.sources){const d=el('details');d.append(el('summary',s.citation+' · '+(B.documents[s.document_id]?.title_zh||s.title||s.document_id)),origin(s),el('pre',s.text));context.append(d)}proofs.append(context);q.append(proofs);
$('selectionRow').hidden=i.kind!=='source_support';$('sourceIdsRow').hidden=i.kind!=='source_support';const prior=state.answers[i.qid];$('humanSources').value=(prior?.reviewed_evidence_ids||[...new Set(r.evidence_checks.map(e=>e.source_id))]).join(' ');$('selection').checked=!!prior?.selection_confirmed;$('humanReason').value=prior?.reason||'';const labels=i.kind==='source_support'?['supported','contradicted','insufficient']:['satisfied','not_satisfied','uncertain'];$('humanLabel').replaceChildren(el('option','请选择你的判断'),...labels.map(x=>{const o=el('option',L[x]);o.value=x;return o}));$('humanLabel').firstChild.value='';$('humanLabel').value=prior?.judgment||'';$('prev').disabled=pos===0;$('next').disabled=pos===a.length-1}
function submit(useAI){const i=current();if(!i)return;const reviewer=$('reviewer').value.trim(),choice=useAI?i.result.judgment:$('humanLabel').value,reason=$('humanReason').value.trim();if(!reviewer){$('notice').textContent='请先填写评审者。';return}if(i.kind==='source_support'&&!$('selection').checked){$('notice').textContent='请先人工确认此句是否适合作为重要事实抽样项；也可暂时跳过。';return}if(!choice){$('notice').textContent='请选择你的判断。';return}const reviewedIds=[...new Set(($('humanSources').value.match(/\[S\d+\]/g)||[]))];if(i.kind==='source_support'&&(reviewedIds.some(id=>!B.runs[i.run_id].sources.some(s=>s.citation===id))||(['supported','contradicted'].includes(choice)&&!reviewedIds.length))){$('notice').textContent='请填写实际核对的有效来源编号，例如 [S2]。';return}if(!useAI&&!reason){$('notice').textContent='请填写你的判断理由。';return}state.reviewer=reviewer;state.answers[i.qid]={qid:i.qid,kind:i.kind,cell:i.cell,run_id:i.run_id,item_id:i.item_id,criterion:i.criterion,question_sha256:i.question_sha256,result_sha256:i.result_sha256,raw_report_sha256:B.runs[i.run_id].raw_report_sha256,judgment:choice,reason:reason||'我已核对本题所列原文与证据，同意模型预评及其理由。',actual_reviewer:reviewer,selection_confirmed:i.kind==='source_support'?true:null,accepted_model_pre_review:useAI,reviewed_evidence_ids:i.kind==='source_support'?reviewedIds:[],confirmed_at:new Date().toISOString()};persist();if($('filter').value!=='pending')pos=Math.min(pos+1,filtered().length-1);render();scrollTo({top:0,behavior:'smooth'})}
for(const [id,doc]of Object.entries(B.documents)){const b=el('div',undefined,'origin');b.append(el('h3',doc.title_zh));p(b,doc.why_zh);const urls=[...new Set(Object.values(B.runs).flatMap(r=>r.sources.filter(s=>s.document_id===id).map(s=>s.source_url)).filter(Boolean))];for(const url of urls){const a=el('a',url);a.href=url;a.target='_blank';a.rel='noopener noreferrer';b.append(a,el('br'))}$('corpus').append(b)}$('reviewer').value=state.reviewer||'';$('reviewer').addEventListener('input',()=>{state.reviewer=$('reviewer').value;persist()});$('filter').onchange=()=>{pos=0;render()};$('jump').onchange=()=>{pos=Number($('jump').value);render()};$('prev').onclick=()=>{pos=Math.max(0,pos-1);render()};$('next').onclick=$('skip').onclick=()=>{pos=Math.min(filtered().length-1,pos+1);render();scrollTo({top:0,behavior:'smooth'})};$('accept').onclick=()=>submit(true);$('override').onclick=()=>submit(false);$('export').onclick=()=>{const out={schema:'actual-human-review-confirmations-v1',session:B.session,freeze_id:B.freeze_id,manifest_sha256:B.manifest_sha256,exported_at:new Date().toISOString(),answers:Object.values(state.answers)},a=el('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)],{type:'application/json'}));a.download=B.session+'_human_confirmations.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)};render();
</script></html>'''


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--partial',action='store_true');a=p.parse_args();build(a.session,a.partial)
