"""Audit observed usage and package a completed development batch without regenerating outputs."""
import argparse,hashlib,html,json,shutil,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()

def usage(p):
    rows=read(p/'adjudicated_rule_results.json');audit=[]
    for r in rows:
        if r['arm']!='report_system':continue
        path=p/'runs'/r['run_id']/'trajectory.jsonl'
        if not path.exists():continue
        events=[json.loads(l) for l in path.read_text().splitlines()]
        completed=[e for e in events if e['type']=='model_completed'];usages=[e['data'].get('usage') for e in completed]
        if usages and all(u and u.get('total_tokens') is not None for u in usages):
            total=sum(u['total_tokens'] for u in usages);native=(r.get('usage') or {}).get('total_tokens')
            if native is not None:assert total==native
            else:r['usage']=dict(total_tokens=total,provenance='Sum of all observed model_completed events; native failure omitted aggregate')
            audit.append(dict(run_id=r['run_id'],responses=len(completed),total_tokens=total,recovered=native is None,trajectory_sha256=sha(path)))
    save(p/'adjudicated_rule_results.json',rows)
    save(p/'telemetry_audit.json',dict(records=audit,baseline='Unchanged Hermes main-loop accounting and four unmetered native closing summaries; see system_repair_04/telemetry_audit.json. No exact billed-cost reduction claim.'))

def package(p):
    summary=read(p/'final_summary.json');assert summary['completed_runs']==32 and summary['unresolved']==0
    groups=summary['groups'];system=groups['report_system'];baseline=groups['hermes_agent']
    old=read(ROOT/'artifacts/report_study/system_repair_04/final_summary.json')['groups']['report_system']
    save(p/'repair_comparison.json',dict(before_optimization=old,current=system,fixed_hermes=baseline,
        scope='Same 16 development tasks; independent full batch retained. Hermes rollouts from system_repair_03 reused, not 16 new baseline samples.'))
    diagnostics=[]
    for r in read(p/'final_results.json'):
        if r['arm']!='report_system':continue
        folder=p/'runs'/r['run_id'];manifest=read(folder/'run_manifest.json')
        calc=read(folder/'calculation_calls.json') if(folder/'calculation_calls.json').exists() else []
        lengths=read(folder/'length_checks.json') if(folder/'length_checks.json').exists() else []
        edits=read(folder/'revision_edits.json') if(folder/'revision_edits.json').exists() else []
        diagnostics.append(dict(run_id=r['run_id'],delivered=r['delivered'],origin=manifest.get('report_origin'),
            terminal=manifest.get('terminal',{}).get('error_code'),
            calculation_calls=len(calc),rejected_calculations=sum('error' in c['result'] for c in calc),
            rejected_calculation_issues=[i['code'] for c in calc for i in c['result'].get('issues',[])],
            counts=[c['body_words'] for c in lengths],edits=len(edits),edit_errors=sum('error' in e for e in edits),
            numeric_complete=r['source_numeric_complete'],format_passed=r['format_passed'],combined_completion=r['combined_completion'],semantic=r['semantic']))
    save(p/'runtime_diagnostics.json',diagnostics)
    metrics=[('交付报告','delivered',16),('季度金额及来源','quarter_facts_supported',60),('缺失材料处理','missing_correct',4),
             ('H2 计算','derived_correct',32),('业务主题','business_topics_passed',32),('显式篇幅','word_limit_passed',8),
             ('两位小数展示','precision_complete',16),('核心内容与格式同时通过','combined_completion',16)]
    trs=''.join('<tr><td>'+label+'</td>'+''.join(f'<td>{g[key]}/{den}</td>' for g in [old,system,baseline])+'</tr>' for label,key,den in metrics)
    semantic=''.join(f'<tr><td>{html.escape(k)}</td><td>{system["semantic"][k]}/16</td><td>{baseline["semantic"][k]}/16</td></tr>' for k in system['semantic'])
    diagnosis={
        'system_optimization_05':'第一轮增加原始数值绑定与日期检查。暴露了严格引用反馈不够具体、净销售额替代含会员费收入、日期误拦截等问题，保留为开发诊断。',
        'system_optimization_06':'第二轮提供原文候选与定向返工，并核对明确的收入组成要求。交付报告的必需季度事实全部正确；两份未交付分别来自重复超长稿和引号排版导致的误拦截。',
        'system_optimization_07':'第三轮加入编号段落修改并解决引号排版误拦截。多数任务完成，但整稿修订任务仍会停在微小改写，保留该回退结果用于后续改进。',
        'system_optimization_08':'本轮季度事实、计算和格式全部达标。正文审读仍发现一项缺失业务主题披露遗漏，保留其失败判定；局部篇幅修订已通过程序选段、计数和统一保存门控完成。',
        'system_optimization_10':'本轮在原始金额绑定、指标口径、计算和缺失披露检查之上，按超出字数调整局部返工范围。严重超长时一次修改最多三个段落，接近上限时逐段修改，保留表格与数值并经过原有交付校验。',
        'system_optimization_09':'本轮将原始金额绑定、指标口径、计算、缺失业务主题披露及局部篇幅修订纳入交付流程。校验返回可执行修正信息，Qwen 在原有调用预算内返工，最终仍经相同门控保存。'}[p.name]
    audit_note='<p>本批对两组报告统一补做期间、指标名称和比较比例的原文复核，修正部分自动裁判漏判。Hermes 原始 rollout 与旧批评分保持封存；本页语义分数包含新增复核，见 <a href="symmetric_source_audit.json">两组同标准复核记录</a>。季度事实、计算、格式等基线分数未改。</p>' if (p/'symmetric_source_audit.json').exists() else ''
    document=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><title>报告系统优化复测</title><style>body{{font:16px/1.7 system-ui,sans-serif;max-width:1080px;margin:48px auto;padding:0 24px;color:#162b3b;background:#f7f9fb}}table{{border-collapse:collapse;width:100%;background:white;margin:24px 0}}td,th{{padding:10px 16px;border-bottom:1px solid #d7e0e6;text-align:left}}th{{background:#e5eef4}}a{{color:#125d8a}}small{{color:#50606c}}code{{font-size:14px}}</style><h1>报告系统优化复测</h1><p>{diagnosis}</p><p>内部 Qwen3.8-27B；8 家公司、16 份完整季度材料、16 个任务。Hermes 使用同一内部模型，其原始 16 次 rollout 固定复用。每轮系统运行完整保留。</p><table><tr><th>指标</th><th>优化前系统</th><th>本轮系统</th><th>固定 Hermes</th></tr>{trs}</table><p>核心内容与格式包括季度事实及来源、缺失披露、业务主题、结构、风格形式、显式篇幅和展示精度；H2 计算及以下语义维度分别报告。</p><table><tr><th>语义维度</th><th>本轮系统</th><th>固定 Hermes</th></tr>{semantic}</table><p>语义评价使用匿名 DeepSeek 单报告评审，并核对引用与误判；它不等同于独立人工评审。金额、来源、单位、篇幅和算术由规则及原文复核。全部争议项已落实为具体判定。</p>{audit_note}<p>记录的系统 token 为 {system['tokens']:,}，平均 {system['mean_calls']} 次模型响应、{system['mean_seconds']} 秒。Hermes 原生收尾与计数口径不同，此处不宣称严格的账单成本优势。</p><p>这是一组在既有任务上修复问题后的开发复测，说明具体设计的改进效果；不同轮次没有择优拼接，也不将复用基线计为新样本。</p><p><a href="final_summary.json">结果</a> · <a href="runtime_diagnostics.json">逐任务诊断</a> · <a href="semantic_adjudications.json">判定依据</a> · <a href="protocol.json">配置</a> · <a href="repair_comparison.json">前后对照</a></p></html>'''
    (p/'report.html').write_text(document)

def seal(p):
    assert not(p/'analysis_manifest.json').exists()
    code=p/'analysis_code'
    for name in ['close_optimization_batch.py','watch_'+p.name.replace('system_','')+'.py','audit_'+p.name.replace('system_','')+'.py']:
        source=ROOT/'analysis'/name
        if source.exists():shutil.copy2(source,code/name)
    paths=[f for f in p.rglob('*') if f.is_file() and 'checkout' not in f.relative_to(p).parts and '__pycache__' not in f.parts]
    files={str(f.relative_to(p)):sha(f) for f in sorted(paths)}
    save(p/'analysis_manifest.json',dict(utc=now(),files=files,excluded='Mutable checkout; canonical code_snapshot archive is sealed.'))
    assert all(sha(p/name)==h for name,h in files.items())
    save(p/'seal_verification.json',dict(utc=now(),files=len(files),all_passed=True))
    print(p.name,'sealed',len(files))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('batch',choices=['05','06','07','08','09','10']);ap.add_argument('action',choices=['usage','package','seal']);a=ap.parse_args()
    globals()[a.action](ROOT/'artifacts/report_study'/('system_optimization_'+a.batch))
