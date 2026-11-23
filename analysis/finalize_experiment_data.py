"""Package saved experiments and explicit author confirmation; no model calls.

The frozen generation and Astra records are never rewritten. This artifact-only
export verifies their identities and provides bilingual, traceable thesis data.
"""
import argparse
from collections import Counter
import csv
import hashlib
import html
import json
from pathlib import Path
import shutil
import statistics
import zipfile

ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,value):Path(p).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def table(p,rows):
    with Path(p).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def mdtable(rows,columns):
    esc=lambda v:str(v).replace('|','\\|').replace('\n',' ')
    return '\n'.join(['| '+' | '.join(label for _,label in columns)+' |',
        '| '+' | '.join('---' for _ in columns)+' |']+
        ['| '+' | '.join(esc(row.get(k,'')) for k,_ in columns)+' |' for row in rows])

def render_markdown(text):
    """Render this export's headings, paragraphs, fenced commands and tables."""
    lines=text.splitlines();parts=[];i=0
    while i<len(lines):
        line=lines[i]
        if not line.strip():i+=1;continue
        if line.startswith('```'):
            code=[];i+=1
            while i<len(lines) and not lines[i].startswith('```'):code.append(lines[i]);i+=1
            parts.append('<pre><code>'+html.escape('\n'.join(code))+'</code></pre>');i+=1;continue
        if line.startswith('| '):
            cells=[] 
            while i<len(lines) and lines[i].startswith('| '):
                row=lines[i].strip('| ').split(' | ')
                if not all(set(c.strip())<={'-',':',' '} for c in row):cells.append(row)
                i+=1
            parts.append('<div class="table"><table>')
            for n,row in enumerate(cells):
                tag='th' if n==0 else 'td'
                parts.append('<tr>'+''.join(f'<{tag}>'+html.escape(c)+f'</{tag}>' for c in row)+'</tr>')
            parts.append('</table></div>');continue
        if line.startswith('#'):
            level=len(line)-len(line.lstrip('#'))
            parts.append(f'<h{level}>'+html.escape(line[level:].strip())+f'</h{level}>')
        else:parts.append('<p>'+html.escape(line)+'</p>')
        i+=1
    return ''.join(parts)

def build(freeze,author):
    freeze,author=Path(freeze).resolve(),Path(author).resolve()
    t=ROOT/'artifacts/tables'/freeze.name
    summary,rows,plan=read(t/'summary.json'),read(t/'per_run.json'),read(freeze/'run_plan.json')
    confirmation,export=read(author/'confirmation.json'),read(author/'confirmations.json')
    if sha(author/'confirmation.json')!=export['confirmation_record_sha256']:
        raise ValueError('Author confirmation changed')
    if len(export['answers'])!=143 or len({a['qid'] for a in export['answers']})!=143:
        raise ValueError('Incomplete or duplicate author confirmations')
    session=ROOT/'artifacts/model_reviews'/export['session']
    manifest,bundle=read(session/'manifest.json'),read(session/'review_bundle.json')
    applied=read(author/'import_applied.json')
    if not applied['apply'] or applied['export_sha256']!=sha(author/'confirmations.json'):
        raise ValueError('Missing verified applied import')
    allowed={x['path'] for x in applied['files']}
    for rel,want in manifest['original_artifact_sha256'].items():
        if rel not in allowed and sha(ROOT/rel)!=want:raise ValueError('Original input changed: '+rel)
    for name,want in read(freeze/'freeze_manifest.json')['files'].items():
        if sha(freeze/name)!=want:raise ValueError('Frozen input changed: '+name)
    with (t/'human_content_worksheet.csv').open() as f:content=list(csv.DictReader(f))
    content_map={(r['cell'],r['criterion']):r for r in content}
    source_items=read(t/'source_support_items.json')
    source_map={(r['cell'],r['id']):r for r in source_items}
    items=[];input_paths=[freeze/'freeze_manifest.json',freeze/'run_plan.json',freeze/'rubric.json',
        author/'confirmation.json',author/'confirmations.json',author/'import_applied.json',
        session/'manifest.json',session/'review_bundle.json',session/'summary.json',
        ROOT/'data/corpus/processed/manifest.json',ROOT/'docs/corpus_metadata.md']
    for answer in export['answers']:
        qpath=session/'questions'/f"{answer['qid']}.json";rpath=session/'results'/f"{answer['qid']}.json"
        q,r=read(qpath),read(rpath);input_paths.extend([qpath,rpath])
        if sha(qpath)!=answer['question_sha256'] or sha(rpath)!=answer['result_sha256']:
            raise ValueError('Question or model judgment changed')
        if q['raw_report_sha256']!=answer['raw_report_sha256'] or r['judgment']!=answer['judgment']:
            raise ValueError('Confirmation does not match reviewed report/label')
        for check in r['evidence_checks']:
            s=next(s for s in q['sources'] if s['citation']==check['source_id'])
            if s['text'][check['char_start']-s['char_start']:check['char_end']-s['char_start']]!=check['quote_en']:
                raise ValueError('Untraceable source quote')
        for check in r['report_checks']:
            if q['raw_report'][check['char_start']:check['char_end']]!=check['quote_en']:
                raise ValueError('Untraceable report quote')
        if q['kind']=='content':
            h=content_map[(q['cell'],q['criterion'])]
            label='uncertain' if h['judgment_type']=='actual_human_uncertain' else {'true':'satisfied','false':'not_satisfied'}[h['satisfied']]
            if h['model_result_sha256']!=sha(rpath):raise ValueError('Worksheet model reference differs')
        else:
            h=source_map[(q['cell'],q['item_id'])];label=h['judgment']
        if label!=answer['judgment'] or h['review_method']!=confirmation['review_method']:
            raise ValueError('Imported author judgment differs')
        items.append({'qid':q['qid'],'cell':q['cell'],'run_id':q['run_id'],'kind':q['kind'],
            'criterion':q['criterion'],'question_zh':r['question_zh'],'judgment':label,
            'reason_zh':r['rationale_zh'],'selection_suitability':r.get('selection_suitability'),
            'review_method':confirmation['review_method'],'confirmation_origin':'explicit_chat_confirmation',
            'question_sha256':sha(qpath),'model_result_sha256':sha(rpath)})
    assert len(rows)==24 and len(content)==123 and len(source_items)==20
    assert all(r['actual_human_review_completed'] for r in rows)
    out=ROOT/'artifacts/dissertation_data'/freeze.name;out.mkdir(parents=True,exist_ok=True)
    conditions=[]
    for condition in dict.fromkeys(r['condition'] for r in rows):
        runs=[r for r in rows if r['condition']==condition];cells={r['cell'] for r in runs}
        labels=Counter(i['judgment'] for i in items if i['kind']=='content' and i['cell'] in cells)
        conditions.append({'condition':condition,'group':runs[0]['group'],'runs':len(runs),
            'runtime_completed':sum(r['runtime_completed'] for r in runs),
            'automatic_passed':sum(r['automatic_passed'] for r in runs),
            'strict_true':sum(r['strict_success'] is True for r in runs),
            'strict_false':sum(r['strict_success'] is False for r in runs),
            'strict_indeterminate':sum(r['strict_success'] is None for r in runs),
            'content_satisfied':labels['satisfied'],'content_not_satisfied':labels['not_satisfied'],
            'content_uncertain':labels['uncertain'],
            'body_words_min':min(r['body_word_count'] for r in runs),
            'body_words_max':max(r['body_word_count'] for r in runs),
            'mean_elapsed_seconds':round(statistics.mean(r['elapsed_seconds'] for r in runs),3),
            'total_tokens':sum(r['total_tokens'] for r in runs),
            'run_ids':';'.join(r['run_id'] for r in runs)})
    tasks=[{'cell':f"{p['condition_id']}_r{p['repetition']}",**p['request'],
        'documents':';'.join(p.get('document_ids',[])),'model':p['expected_model'],
        'evidence_sha256':p['frozen_evidence_sha256'],'model_calls_limit':p['budget']['model_calls'],
        'run_timeout_seconds':p['budget']['run_timeout_seconds'],
        'automatic_revisions':p['budget']['automatic_revisions']} for p in plan]
    documents=read(ROOT/'data/corpus/processed/manifest.json')['documents']
    reasons={'nvidia_fy2025_10k':'年度业务、AI战略、财务表现与风险',
        'nvidia_fy2025_q4_cfo_commentary':'补充季度和市场平台信息，检验同公司多文档综合',
        'amd_fy2024_10k':'第二家公司年度业务、财务表现和风险',
        'amd_fy2024_q4_release':'补充季度与分部表现，支持AMD多文档及跨公司比较'}
    corpus=[{'document_id':d['id'],'title':d['title'],'source_url':d['source_url'],
        'selection_reason_zh':reasons[d['id']],'normalized_chars':d['normalized_chars'],
        'file_sha256':d['file_sha256'],'normalized_text_sha256':d['normalized_text_sha256']} for d in documents]
    failures=[r for r in rows if not r['automatic_passed']]
    issues=[i for i in items if i['judgment'] in {'not_satisfied','uncertain','insufficient','contradicted'}]
    for name,data in [('condition_results.csv',conditions),('task_configuration.csv',tasks),
                      ('corpus_sources.csv',corpus),('author_review_items.csv',items),
                      ('review_issues.csv',issues),('automatic_failures.csv',failures)]:
        table(out/name,data)
    for name in ('summary.json','per_run.json','per_run.csv','automatic_items.csv','citation_items.csv',
                 'customization_pairs.json','human_content_worksheet.csv','human_audit_selection.json',
                 'source_support_items.json','provenance.json'):
        shutil.copyfile(t/name,out/name);input_paths.append(t/name)
    shutil.copyfile(author/'confirmation.json',out/'author_confirmation.json')
    save(out/'model_summary_original.json',read(session/'summary.json'))
    save(out/'author_review_items.json',items)
    number_map={'freeze_id':freeze.name,'metrics':{
        'main_completion':{'path':'summary.json','pointer':'/main/runtime_completion'},
        'main_automatic_pass':{'path':'summary.json','pointer':'/main/automatic_all_constraints'},
        'main_content':{'path':'summary.json','pointer':'/main/human_task_coverage'},
        'customization_content':{'path':'summary.json','pointer':'/customization/human_task_coverage'},
        'sample_source_support':{'path':'summary.json','pointer':'/main/factual_support'},
        'strict_success':{'path':'summary.json','pointer':'/*/strict_success'},
        'pairs':{'path':'customization_pairs.json'},
        'token_usage':{'path':'per_run.csv','formula':'sum(total_tokens); main/customization separate'},
        'elapsed_time':{'path':'per_run.csv','formula':'sum(elapsed_seconds); not batch wall-clock'},
        'each_reviewed_label':{'path':'author_review_items.json','key':'qid; immutable question/result hashes'}}}
    save(out/'number_map.json',number_map)
    # This supplements the older automatic-only number map without altering it.
    main,custom=summary['main'],summary['customization'];support=main['factual_support']
    report=f"""# 毕业论文基础实验数据包

冻结批次：`{freeze.name}`。24次首次生成及143项作者复核均已归档，可用于撰写实验部分。结果含失败和不确定项，完成实验不代表全部质量要求通过。

## 实验设置与语料

系统目标是多来源信息整合，以及structure、style、depth定制。六类任务形成七个主条件，每条件重复三次，共21次；另有3次单因素定制配对。生成采用冻结证据回放和真实Qwen3.8-27B调用；实时网页开发smoke另行保存。每个配对只改一种定制设置，输入证据hash相同。

温度0.2，thinking=false，最多6000输出token/请求；最多8次模型请求/运行，180秒模型超时、480秒运行超时，自动重试和自动修订均为0。BGE-M3远程embedding串行且优先缓存；正式生成阶段未新增embedding或live web调用。远程权重revision和seed未知，不保证逐字复现。

{mdtable(corpus,[('title','语料'),('selection_reason_zh','选用原因'),('normalized_chars','规范化字符数'),('source_url','原始来源')])}

NVIDIA财年截至2025-01-26，AMD截至2024-12-28，两公司财期和分部口径不同。CFO说明本身的发布日期未知，不能套用相邻业绩公告日期。完整hash在corpus_sources.csv；原始metadata补充说明保持事后补充身份。切片为sentence-parent-child-v1：子块1000/1500字符，父块2400/4000字符；实际父块正文上下文上限18000字符；四文档1077子块、363父块。

## 评估方法

自动检查与作者复核分列。Astra high先对20条预选事实和123项内容/定制标准逐题给出判断与理由，作者随后报告已复核全部143项并确认判断一致；登记依据为本会话明确确认，记录见author_confirmation.json。该过程是参考模型预评后的作者复核，不是独立盲评、双人标注或人类一致性校准。没有另行保存逐题人工点击、人工耗时或独立打分轨迹。

来源抽样为预选4份报告各5条，保留原样本；其中2条被标记为较弱事实候选，单列敏感性结果：18条较重要候选中17条支持、1条不足；2条较弱候选中1条支持、1条不足。不据此推广全部报告事实准确率。内容的9项“不确定”和来源的2项“证据不足”均保留，不视作通过。该模型预评加作者复核的具体实施发生在正式生成之后，原rubric与自动阈值未改写。

## 主实验与定制结果

{mdtable(conditions,[('condition','条件'),('runs','运行数'),('runtime_completed','运行完成'),('automatic_passed','全部自动通过'),('strict_true','严格通过'),('strict_indeterminate','严格未确定'),('content_satisfied','内容满足'),('content_not_satisfied','不满足'),('content_uncertain','不确定'),('body_words_min','最少词数'),('body_words_max','最多词数')])}

主实验运行完成21/21（100%），结构及来源编号检查21/21，全部自动约束7/21（33.3%）；14份报告超过字数上限。内容/定制108项中83项满足（76.9%，分母包含7项不确定）、18项不满足、7项不确定；已确定判断中的满足比例为83/101（82.2%），不得以此替代全体分母。

3份补充定制报告全部自动约束通过；15项内容/定制中12项满足（80.0%）、1项不满足、2项不确定。合计123项为95项满足、19项不满足、9项不确定；已复核覆盖率123/123。严格成功要求全部自动项与该报告所有内容/风格项通过：主实验{main['strict_success']['known_true']}/21通过、{main['strict_success']['known_false']}/21不通过；定制{custom['strict_success']['known_true']}/3通过、{custom['strict_success']['known_false']}/3不通过、{custom['strict_success']['pending']}/3未确定。此严格指标不等同全部事实已审计。

来源支持抽样20条中18条支持（90.0%）、0条矛盾、2条证据不足。正文引用编号有效1239/1239，仅证明编号有效。原链接启发式568/620，仅证明对应行有来源线索，不能等同事实蕴含。

## 定制配对与成本

结构配对1391→1296词；简报风格1691→710词；详细深度806→2254词。三种变体的自动约束均通过，但语义质量结论仍受上述复核限制；配对与run ID见customization_pairs.json，不作普遍改善或因果优势结论。

主实验63次模型请求、320587 token、累计382.771秒；定制9次请求、46084 token、累计59.643秒。合计72次请求、366671 token、累计442.414秒，这是各运行耗时之和，不是整项研究墙钟时间。正式工具失败、重试和超时均为0。生成服务费用按用户声明免费记录为0；Astra评估的token、内部调用数、费用未暴露，保持unknown。

## 失败、局限与可写入论文的结论

automatic_failures.csv保留14份字数失败；review_issues.csv保存30条不满足、不确定或证据不足的题号、原run和中文理由。主要问题包括关键业绩遗漏、财期/季度与全年口径混用、分部覆盖不足及缺少支持的解释。不能挑选通过案例代替完整分母。

本实验支持“有界系统能完成所设多来源与定制任务，并保存可追溯证据”，同时显示字数遵循与内容完整性仍有限。单一小规模金融语料、模型版本信息不完整、表格扁平化、偏早段落的来源抽样、同一模型评审会话的顺序影响、作者先看到模型结论，均限制泛化和评价独立性。保留不确定结论是实验结果，不是未完成运行。

## 文件与重建

本目录提供任务配置、语料来源、逐条件/逐run结果、自动检查、作者复核逐项标签、疑点清单、定制配对、number_map.json与全部输入/输出hash。原始报告、证据和完整轨迹仍位于artifacts/runs；没有复制新的模型结果或覆盖旧报告。附录在artifacts/appendix/{freeze.name}，架构图在artifacts/figures。

从项目根目录运行：

```bash
.venv-runtime/bin/python analysis/build_results.py --freeze artifacts/experiment_freezes/{freeze.name}
.venv-runtime/bin/python analysis/finalize_experiment_data.py --freeze artifacts/experiment_freezes/{freeze.name} --author {author.relative_to(ROOT)}
```

原正式生成源码归档与当前维护源码不同，不能在当前树直接重启旧freeze；恢复原归档的方法见README。上述命令只重建统计，不调用LLM、embedding或网页。
"""
    (out/'README_zh.md').write_text(report)
    english="""# Evaluation method and result text

The study comprised 21 first-generation runs across seven task/source conditions
and three single-setting customization runs using matched frozen evidence. The
generator was Qwen3.8-27B; all outputs, failures and input identities were retained.

Content and sampled source support were first assessed item by item by a configured
Astra model with high reasoning effort. The dissertation author subsequently
reported reviewing all 143 items and confirmed agreement with those assessments.
This is model-assisted author review with prior access to model labels, rather
than independent or blinded human annotation. Confirmation was supplied in the
project conversation; no independent item-level annotation timing was recorded.
The review implementation was adopted after formal generation. The original rubric
and automatic thresholds were preserved. Uncertainty was retained explicitly.

All 21 main runs completed, but only 7/21 passed every automatic constraint;
14 exceeded their word limit. Main content/style/depth results were 83 satisfied,
18 not satisfied and seven uncertain among 108 items. Customization results were
12, one and two among 15 items. All 123 items were reviewed; uncertainty is distinct
from missing review. The prespecified four-report source sample contained 18 supported
and two insufficient claims among 20; two weaker candidates were retained, and
17/18 of the remaining candidates were supported. These counts do not establish
overall factual accuracy or independently calibrated model-judge reliability.

Under the frozen conjunction of all automatic and task/style requirements, two
main reports passed and 19 failed; among the customization runs one passed, one
failed and one remained indeterminate. Generation consumed 72 reported model requests,
366671 tokens and 442.414 summed run-seconds. Judge usage and fees were unavailable.
Results are descriptive for this small corpus, with no causal or general-superiority claim.
"""
    (out/'methods_results_en.md').write_text(english)
    # Standalone local read-only results page; the original review UI stays archived.
    page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>论文基础实验数据</title><style>body{font:16px/1.8 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;color:#19364b;background:#f5f7fa;margin:0}main{max-width:1100px;margin:30px auto;padding:24px;background:white;border-radius:14px}h1,h2{color:#115e76}h2{margin-top:32px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f5f9;padding:18px}a{color:#087b94}.table{overflow-x:auto}table{border-collapse:collapse;font-size:14px;min-width:100%}th,td{border:1px solid #d7e1e9;padding:10px;text-align:left}th{background:#edf4f7}td{max-width:280px;overflow-wrap:anywhere}p{margin:14px 0}@media(max-width:600px){main{margin:0;padding:16px}}</style><main><a href="model_review_zh.html">查看原始中文逐题证据包（历史预评页面；其中浏览器确认数不代表本次聊天登记）</a>'+render_markdown(report)+'</main></html>'
    (ROOT/'docs/experiment_results_zh.html').write_text(page)
    (ROOT/'docs/experiment_data_zh.md').write_text(report)
    shutil.copyfile(ROOT/'docs/experiment_results_zh.html',out/'results_zh.html')
    shutil.copyfile(session/'review_zh.html',out/'model_review_zh.html')
    shutil.copyfile(session/'review_bundle.json',out/'model_review_bundle.json')
    for run in rows:
        run_root=ROOT/'artifacts/runs'/run['run_id'];target=out/'runs'/run['run_id'];target.mkdir(parents=True,exist_ok=True)
        for name in ('raw_report.md','report.md','request.json','audit.json','run_manifest.json',
                     'evidence_ledger.json','frozen_evidence.json','trajectory.jsonl','resolved_config.json'):
            source=run_root/name;shutil.copyfile(source,target/name);input_paths.append(source)
        source=run_root/'human_review/review.json'
        if source.exists():shutil.copyfile(source,target/'author_source_review.json');input_paths.append(source)
    for name in read(freeze/'freeze_manifest.json')['files']:
        target=out/'freeze'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(freeze/name,target)
    shutil.copyfile(freeze/'freeze_manifest.json',out/'freeze/freeze_manifest.json')
    provenance={'schema':'dissertation-data-package-v1','freeze_id':freeze.name,
        'review_method':confirmation['review_method'],'author_confirmed_items':len(items),
        'model_labels_preserved':True,'provider_calls_added':0,'independent_blind_review':False,
        'builder_sha256':sha(__file__),'inputs_sha256':{str(p.relative_to(ROOT)):sha(p) for p in input_paths},
        'outputs_sha256':{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p!=out/'manifest.json'}}
    save(out/'manifest.json',provenance)
    archive=out.parent/(freeze.name+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file():z.write(p,arcname=out.name+'/'+str(p.relative_to(out)))
    print(json.dumps({'directory':str(out),'zip':str(archive),'reviewed':len(items),
        'automatic_failures':len(failures),'review_issues':len(issues),'provider_calls_added':0},ensure_ascii=False))
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze',required=True,type=Path);p.add_argument('--author',required=True,type=Path)
    args=p.parse_args();build(args.freeze,args.author)
