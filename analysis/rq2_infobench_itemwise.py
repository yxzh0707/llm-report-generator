"""Explicit post-hoc failure-containment analysis; never reruns or changes labels."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re

from analysis.rq2_infobench_pilot import read, save, sha, validate_answer, verify


def extract(packet, raw):
    """Retain bad-quote judgments as INVALID, not NO; valid neighbors survive."""
    items = {}
    global_error = None
    try:
        choice = raw['choices'][0]
        if choice.get('finish_reason') != 'stop':
            raise ValueError('Unfinished response')
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', choice['message']['content'].strip())
        decoded = json.loads(text)['items']
        expected = [q['id'] for q in packet['questions']]
        if len(decoded) != len(expected) or sorted(x.get('id','') for x in decoded) != sorted(expected):
            raise ValueError('Wrong item identities')
        items = {x['id']:x for x in decoded}
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        global_error = type(exc).__name__ + ': invalid response structure'
    rows = []
    for q in packet['questions']:
        item = items.get(q['id'])
        error = global_error
        if not error:
            try:
                validate_answer(json.dumps({'items':[item]}), {**packet, 'questions':[q]})
            except (ValueError, KeyError, TypeError) as exc:
                error = str(exc)
        rows.append({**q, 'label':'INVALID' if error else item['label'],
                     'raw_label':item.get('label') if item else None,
                     'validation_error':error, 'judgment':item})
    return rows


def analyze(session, output):
    manifest = verify(session)
    output.mkdir(parents=True, exist_ok=False)
    records=[]
    response_hashes={}
    for job in manifest['jobs']:
        path=session/'responses'/f"{job['job']}.json"
        raw=read(path) if path.exists() else {}
        if path.exists(): response_hashes[str(path)]=sha(path.read_bytes())
        packet=read(session/'packets'/f"{job['job']}.json")
        records.extend({**job, **row} for row in extract(packet,raw))
    originals=[r for r in records if r['variant']=='original' and not r['diagnostic']]
    def score(rows):
        c=Counter(x['label'] for x in rows)
        n=len(rows)
        return {'n':n,'counts':dict(c),'lower':c['YES']/n,
                'upper':(c['YES']+c['UNKNOWN']+c['INVALID'])/n}
    reports={}
    for job in manifest['jobs']:
        if job['variant']!='original':continue
        rows=[r for r in originals if r['job']==job['job']]
        mechanics=read(session/'mechanical'/f"{job['job']}.json")
        reports[job['condition']]={**score(rows),'mechanical':mechanics,
            'depth_diagnostic':next(r['label'] for r in records if r['job']==job['job'] and r['diagnostic'])}
    repeats=[]
    for r in records:
        if r['variant']!='repeat':continue
        base=next(b for b in records if b['condition']==r['condition'] and b['variant']=='original' and b['id']==r['id'])
        repeats.append({'condition':r['condition'],'id':r['id'],
                        'first':base['label'],'repeat':r['label'],
                        'valid':base['label']!='INVALID' and r['label']!='INVALID',
                        'same':base['label']==r['label']})
    controls=[r for r in records if r['variant']=='empty_body_control' and r['category']=='content']
    summary={'method':'Post-hoc itemwise validation of the same frozen InFoBench-inspired pilot responses',
        'created_at':datetime.now(timezone.utc).isoformat(),
        'change':'Primary v1 validator invalidates an entire report when any quote fails. This secondary analysis isolates failures per item, without changing any model label, accepting approximate quotes, or making model calls.',
        'primary_summary':str(session/'summary.json'), 'response_sha256':response_hashes,
        'originals_verified':True,'new_model_calls':0,
        'micro':score(originals),'reports':reports,
        'macro_lower':sum(x['lower'] for x in reports.values())/len(reports),
        'macro_upper':sum(x['upper'] for x in reports.values())/len(reports),
        'categories':{c:score([x for x in originals if x['category']==c]) for c in ('content','style')},
        'repeats':{'planned':len(repeats),'valid':sum(x['valid'] for x in repeats),
                   'same':sum(x['same'] for x in repeats if x['valid']),'details':repeats},
        'controls':{'content_items':len(controls),'NO':sum(x['label']=='NO' for x in controls),
                    'YES':sum(x['label']=='YES' for x in controls),
                    'unresolved':sum(x['label'] in ('INVALID','UNKNOWN') for x in controls)},
        'invalid_explicit_items':[{'condition':r['condition'],'id':r['id'],'error':r['validation_error']} for r in originals if r['label']=='INVALID'],
        'limitations':read(session/'protocol.json')['limits']}
    save(output/'summary.json',summary)
    save(output/'items.json',records)
    save(output/'analysis_identity.json',{'code_sha256':sha(Path(__file__).read_bytes()),
        'parent_manifest_sha256':sha((session/'manifest.json').read_bytes())})
    rows=''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in [c,s['counts'],f"{s['lower']:.1%}–{s['upper']:.1%}",f"{sum(x['passed'] for x in s['mechanical'])}/{len(s['mechanical'])}",s['depth_diagnostic']])+'</tr>' for c,s in reports.items())
    details=''.join('<tr>'+''.join('<td>'+html.escape(str(v or ''))+'</td>' for v in [r['condition'],r['variant'],r['id'],r['label'],(r['judgment'] or {}).get('reason'),r['validation_error']])+'</tr>' for r in records)
    micro=summary['micro']; rep=summary['repeats']; con=summary['controls']
    page='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>RQ2 InFoBench 试验结果</title>
    <style>body{max-width:1180px;margin:40px auto;padding:0 24px;font:16px/1.65 system-ui;color:#202830}table{border-collapse:collapse;width:100%;margin:24px 0}td,th{border:1px solid #ccd3da;padding:9px;text-align:left;vertical-align:top}pre{white-space:pre-wrap}h1{font-size:28px}.note{background:#fff4db;padding:16px}</style>
    <h1>RQ2：InFoBench 逐项指令评估试验</h1>
    <p>采用 Qin 等（2024）的要求分解思路，评估本地六份报告（三组定制配对）。这是方法适配，不是官方 500 条 InFoBench 的基准分数。</p>
    <p class="note">当前结论：自动流程已运行，但评审模型的引句可靠性需要改进。Qwen3.8-27B 同时是历史生成模型的部署名称，因此本轮只能支持探索性分析，不能作为独立质量验证。无需用户逐条评分。</p>
    <h2>真实执行与校验</h2><p>共 12 次真实评审：6 份原报告、3 次重复、3 份空正文负对照。原始报告与历史评分均未改动。主分析采用整份响应严格校验；本页是额外明确标记的逐条失败隔离分析：只隔离不合格条目，不修复引句、不改标签、不重新调用模型。</p>'''
    page+=f"<p>六份原报告共有 {micro['n']} 项明确语义要求：{html.escape(str(micro['counts']))}。满足率界限 {micro['lower']:.1%}–{micro['upper']:.1%}。这是由无效／不确定条目造成的界限，不是置信区间或事实准确率。空正文控制 {con['NO']}/{con['content_items']} 项被判 NO；重复评价在两次均有效的 {rep['valid']} 项中，有 {rep['same']} 项标签相同（计划比较 {rep['planned']} 项）。</p>"
    page+='''<p>内容要求来自任务文本；风格要求来自原始风格指令。字数、标题、引用标识和项目符号由程序检查。语义深度是事后操作化的探索性诊断，未计入明确指令满足率。三种定制使用不同任务，不能据表中高低判断哪种定制效果最好。</p>
    <table><tr><th>报告条件</th><th>明确语义要求标签</th><th>满足率界限</th><th>程序检查通过</th><th>语义深度诊断</th></tr>'''+rows+'</table>'
    page+='''<h2>对 RQ2 的用途</h2><p>新增工作包括请求分解、确定性／语义检查分工、完整模型响应与用量记录、引句回查、重复稳定性及负对照。当前适合写为评估方法试验；正式扩展宜先引入不同模型的 judge，并预先固定逐项无效处理。直接生成基线未在本轮运行。</p>
    <p><a href="../report.html">初始严格整份校验结果</a> · <a href="summary.json">逐条汇总 JSON</a> · <a href="items.json">全部逐条记录</a> · <a href="https://aclanthology.org/2024.findings-acl.772/">InFoBench 论文</a></p>
    <h2>逐项记录</h2><table><tr><th>条件</th><th>版本</th><th>条目</th><th>有效标签</th><th>模型理由</th><th>校验问题</th></tr>'''+details+'</table><h2>协议限制及数值明细</h2><pre>'+html.escape(json.dumps(summary,ensure_ascii=False,indent=2))+'</pre></html>'
    (output/'report.html').write_text(page)
    print(json.dumps({k:summary[k] for k in ('micro','macro_lower','macro_upper','categories','controls')},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();analyze(args.session,args.out)
