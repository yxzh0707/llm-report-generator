"""Package the completed prospective comparison, then seal without regeneration."""
import collections, html, json, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src'), str(ROOT/'analysis')]
from experiments.heldout_report_comparison import P, verify
from experiments.system_comparison import read, save, sha, now

def complete(r):
    return r['combined_completion'] and all(d['supported_calculation'] for d in r['derived']) and all(g['passed'] for g in r['growth'])

def metrics(rows):
    facts = [f for r in rows for f in r['facts']]
    lengths = [x for r in rows for x in r['customization']['items'] if x['id']=='depth_words']
    return [
        ('交付报告', sum(r['delivered'] for r in rows), len(rows)),
        ('季度金额及对应来源', sum(f['source_supported'] for f in facts if f['value'] is not None), sum(f['value'] is not None for f in facts)),
        ('缺失季度如实披露', sum(f['source_supported'] for f in facts if f['value'] is None), sum(f['value'] is None for f in facts)),
        ('H2 合计／缺失依赖', sum(d['supported_calculation'] for r in rows for d in r['derived']), len(rows)*2),
        ('原始金额环比／缺失依赖', sum(g['passed'] for r in rows for g in r['growth']), len(rows)*2),
        ('请求的业务主题', sum(r['semantic'][k] for r in rows for k in ('business_A','business_B')),len(rows)*2),
        ('显式 600 词上限', sum(x['passed'] for x in lengths), len(lengths)),
        ('结构、风格与篇幅同时合规', sum(r['format_passed'] for r in rows),len(rows)),
        ('必需内容、计算与输出约束同时通过',sum(complete(r) for r in rows),len(rows)),
        ('期间解释准确',sum(r['semantic']['period_scope'] for r in rows),len(rows)),
        ('正文无重大矛盾',sum(r['semantic']['narrative_consistency'] for r in rows),len(rows)),
    ]

def package():
    verify()
    summary = read(P/'final_summary.json'); rows = read(P/'final_results.json')
    jobs = read(P/'jobs.json'); reviews = read(P/'reviewed_reports.json')
    assert summary['completed_runs']==24 and summary['unresolved']==0
    assert len(jobs)==len(rows)==len(reviews)==24
    assert {r['run_id'] for r in rows}=={r['run_id'] for r in reviews}=={r['run_id'] for r in jobs}
    assert len(read(P/'judge_results.json'))==24
    for review in reviews:
        assert sha(P/'runs'/review['run_id']/'evaluated_report.md')==review['report_sha256']
    oldchecks=[]
    for name in ['system_repair_03','system_repair_04']+['system_optimization_'+n for n in ('05','06','07','08','09','10')]+['semantic_repair_11','semantic_repair_12','precision_scope_13']:
        folder=P.parent/name
        manifest=read(folder/'analysis_manifest.json')
        bad=[n for n,h in manifest['files'].items() if not(folder/n).is_file() or sha(folder/n)!=h]
        assert not bad,(name,bad)
        oldchecks.append(dict(study=name,files=len(manifest['files']),unchanged=True))
    diagnostics=[]; telemetry=[]
    for r in rows:
        folder=P/'runs'/r['run_id']; m=read(folder/'run_manifest.json')
        checks=read(folder/'validation_checks.json') if(folder/'validation_checks.json').exists() else []
        diagnostics.append(dict(run_id=r['run_id'],save_attempts=len(checks),rejections=sum(not c['passed'] for c in checks),
            issues=dict(collections.Counter(i['code'] for c in checks for i in c.get('issues',[]))),
            delivered=r['delivered'],required_completion=complete(r),narrative_passed=r['semantic']['narrative_consistency']))
        if r['arm']=='report_system':
            events=[json.loads(l) for l in (folder/'trajectory.jsonl').read_text().splitlines()]
            completed=[e for e in events if e['type']=='model_completed']
            total=sum(e['data']['usage']['total_tokens'] for e in completed)
            assert total==r['usage']['total_tokens']
            telemetry.append(dict(run_id=r['run_id'],observed_responses=len(completed),recorded_tokens=total,source='trajectory model_completed events'))
        else:
            usage=read(folder/'hermes_usage.json')
            assert usage['session_total_tokens']==r['usage']['total_tokens']
            telemetry.append(dict(run_id=r['run_id'],observed_responses=usage['session_api_calls'],recorded_tokens=usage['session_total_tokens'],
                native_iteration_limit_reached=usage['session_api_calls']>=16,source='Native Hermes main-loop counters; closing calls not guaranteed included'))
    save(P/'runtime_diagnostics.json',diagnostics)
    save(P/'telemetry_audit.json',dict(utc=now(),runs=telemetry,note='Observed usage, not exact equal billed budget. Native Hermes closing summaries differ from counted main-loop calls.'))
    failures=[r for r in read(P/'semantic_adjudications.json') if not r['passed']]
    save(P/'symmetric_source_audit.json',dict(utc=now(),reviewer='assistant_source_audit',reports=reviews,material_failures=failures,
        method='Complete narrative read for all 24 reports, same frozen criteria in both arms, source-checked quotations. DeepSeek judgments retained separately. This is an assistant audit, not independent human evaluation.'))
    save(P/'verification.json',dict(utc=now(),planned_runs=24,completed_runs=24,unique_tasks=8,issuer_pairs=2,full_report_reviews=24,
        unresolved=0,frozen_inputs_and_runtime_unchanged=True,old_studies=oldchecks,
        exact_numeric_gold_unchanged=True,numeric_parser_adjudication='numeric_extraction_audit.json',
        generator_changes_during_study=False,regenerated_or_substituted_outputs=0,manuscript_changed=False))
    grouped={a:[r for r in rows if r['arm']==a] for a in ('report_system','hermes_agent')}
    def table(first=False):
        ms={a:metrics([r for r in rs if not first or r['repetition']==1]) for a,rs in grouped.items()}
        result='<table><thead><tr><th>指标</th><th>报告系统</th><th>原生 Hermes</th></tr></thead><tbody>'
        for x,y in zip(ms['report_system'],ms['hermes_agent']):
            result+=f'<tr><td>{x[0]}</td><td>{x[1]}/{x[2]}</td><td>{y[1]}/{y[2]}</td></tr>'
        return result+'</tbody></table>'
    repeat_rows=''
    for tid in sorted({r['task_id'] for r in rows if r['repetition']==2}):
        vals=[]
        for a in grouped:
            rs=sorted([r for r in grouped[a] if r['task_id']==tid],key=lambda r:r['repetition'])
            vals.append(' / '.join('通过' if complete(r) else '未通过' for r in rs))
        repeat_rows+=f'<tr><td>{tid}</td><td>{vals[0]}</td><td>{vals[1]}</td></tr>'
    runs=''.join(f'<tr><td><a href="runs/{r["run_id"]}/evaluated_report.md">{r["run_id"]}</a></td><td>{"通过" if complete(r) else "未通过"}</td><td>{"通过" if r["semantic"]["narrative_consistency"] else "有重大矛盾"}</td></tr>' for r in rows)
    s,b=summary['groups']['report_system'],summary['groups']['hermes_agent']
    report=f'''<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>新公司与新期间：同模型 Hermes 对照</title><style>body{{font:16px/1.75 system-ui,sans-serif;max-width:1080px;margin:40px auto;padding:0 24px;color:#193443;background:#f6f8fa}}table{{width:100%;border-collapse:collapse;background:white;margin:20px 0}}th,td{{padding:10px 14px;border-bottom:1px solid #d6e0e6;text-align:left}}th{{background:#e5eef2}}h1{{font-size:29px}}h2{{font-size:23px;margin-top:34px}}a{{color:#146189}}.lead{{background:#e9f3ef;border-left:4px solid #34876b;padding:16px 20px}}.scroll{{overflow:auto}}small{{color:#4d636f}}</style></head><body>
    <h1>新公司与新期间：同模型 Hermes 对照</h1>
    <p class="lead">在 8 个此前未用于系统开发的任务上，报告系统 8/8 满足必需内容、计算口径和输出约束，原生 Hermes 为 3/8。加入事先指定的 4 次重复后，分别为 12/12 和 4/12。优势集中在遵循用户指定的计算口径和严格篇幅控制；两组季度事实与来源均正确。</p>
    <h2>配置与数据</h2><p>生成模型均为内部 Qwen3.8-27B，temperature=0.2，关闭 thinking。基线使用本机原生 Hermes（提交 7d568293f97a8640467303e786583efc19cecd20），保留原生提示词及终端、文件和任务工具；系统使用来源绑定、确定性计算、计数和保存返工流程。两组收到完全相同的用户要求和完整来源文本。</p>
    <p>新增 ServiceNow、Intuit、Home Depot、Lowe’s 四家公司，使用各自 FY2024 Q3、Q4 的 8 份完整季度发布材料，其中 4 份作为上传材料，4 份作为归档网页来源。7 份 PDF 的财务表已逐页定位并视觉核对，另 1 份为完整发布正文 HTML。两组公司各设置简短、标准、详细、缺失材料四类任务；标准与缺失任务各重复一次，共 24 次真实生成。只有简短和缺失任务要求正文不超过 600 词；标准、详细任务没有数字长度上限。</p>
    <p>系统与 Hermes 均设 900 秒上限、每次输出最多 12,000 token，分别限制 16 次模型调用和 16 次原生迭代。原生收尾调用计数不同，因此记录实际用量，不声称总计费预算严格相等。本实验验证固定证据条件下的报告生成；实时检索效果由既有独立实验评价。任务、来源、评分标准及运行代码均在生成前冻结，所有计划运行保留。</p>
    <h2>首次运行：8 个不同任务</h2>{table(True)}
    <h2>全部运行：每组 12 次</h2>{table()}
    <p>“必需内容、计算与输出约束”要求季度金额与来源、缺失披露、两位小数展示、业务主题、H2 合计、环比、结构、风格形式和显式篇幅全部通过。它与“正文无重大矛盾”分开统计。H2 和环比各 24 项中，各包含 20 项可计算结果、4 项应披露为不可计算的缺失依赖。</p>
    <h2>差异来自哪里</h2><p><strong>计算口径执行。</strong>用户要求 H2 按展示后的季度金额求和，环比按原始金额计算。ServiceNow 的展示值为 2.80 和 2.96，因此合计应为 5.76；原始金额合计再舍入得到的 5.75 属于另一种口径。Hermes 的 6 次相关运行都给出 5.75；系统 6 次均遵循展示值口径，同时保持原始金额环比正确。这说明系统能把不同计算的精度规则分别执行，而不是把统一舍入策略套到所有运算。</p>
    <p><strong>显式篇幅控制。</strong>系统 6/6 限长报告满足 600 词上限，Hermes 为 1/6。标准和详细任务没有该上限。运行轨迹显示本批系统限长稿已合规；本批结果体现完整生成流程的约束执行效果，局部改写模块的单独效果见既有失败回放。</p>
    <p><strong>完整材料下的事实整合。</strong>两组均正确提取 44 项可得季度事实，并在 4 个缺失案例中披露不可得。这证明来源组织和报告链路在新公司材料上正常工作；本批事实提取未形成组间差距。</p>
    <h2>预先指定的重复运行</h2><table><tr><th>任务</th><th>报告系统：首次 / 重复</th><th>Hermes：首次 / 重复</th></tr>{repeat_rows}</table>
    <p>以上按“必需内容、计算与输出约束”判定。四个重复任务是事先指定的稳定性检查，不另算四个独立新任务。全部数据来自两个公司配对，不把 24 份报告或数值条目视作独立公司样本，不作总体显著性推断。</p>
    <h2>正文评价与返工诊断</h2><p>匿名 DeepSeek V4 Flash 按冻结标准评价每份报告，随后对两组全部 24 份正文进行助手原文复核，修正引文不连续及漏判。正文无重大矛盾为系统 5/12、Hermes 2/12。主要问题是经营原因跨公司归属、cRPO 与收入的汇率调整方法混用、期间重叠解释及摘要与详细数据冲突。这些结果单列，不能用表格正确率代替正文质量，也不把助手复核称为独立人工评审。</p>
    <p>系统有 5 份报告经历保存拒绝后返工并交付，主要涉及期间间隔依据、百分比单位和季度来源引用。部分业务指标表已在正文说明来源，却因表格行缺少引用再次返工，后续可改进引用作用范围识别。现有英文规则仍会漏掉新的正文表达，后续应将“主体、期间、指标、比较关系和来源”关联检查。此项改进不追溯改变本轮结果。</p>
    <p>记录用量：系统 {s['tokens']:,} token、平均 {s['mean_calls']} 次模型响应和 {s['mean_seconds']} 秒；Hermes 主循环记录 {b['tokens']:,} token、平均 {b['mean_calls']} 次响应和 {b['mean_seconds']} 秒。收尾调用与计量方式不同，以上是实测运行记录，不换算为严格账单成本优势。</p>
    <h2>评分及材料完整性</h2><p>固定数值解析器对重复结果附注、括号标签和原始百万金额说明有误判。已对两组所有报告统一复核，保留原始评分与逐项改判依据，严格参考答案、来源要求和篇幅门槛不变；没有替换报告或择优取样。全部语义争议已落实为具体判定。项目累计覆盖 24 家公司、64 份不同季度材料，属于多项实验累计覆盖；本主对照仍为四家公司、八份材料。</p>
    <p><a href="protocol.json">冻结配置</a> · <a href="tasks.json">任务</a> · <a href="inventory.json">8 份原文清单</a> · <a href="source_gold.json">原始金额及证据</a> · <a href="final_summary.json">结果汇总</a> · <a href="heldout_summary.json">首次及重复结果</a> · <a href="numeric_extraction_audit.json">解析复核</a> · <a href="symmetric_source_audit.json">两组正文复核</a> · <a href="runtime_diagnostics.json">返工轨迹摘要</a> · <a href="verification.json">完整性核验</a></p>
    <h2>逐份输出</h2><div class="scroll"><table><tr><th>运行与原稿</th><th>必需项完成</th><th>正文一致性</th></tr>{runs}</table></div></body></html>'''
    (P/'report.html').write_text(report)
    code=P/'analysis_code'
    for name in ['close_heldout_14.py','audit_heldout_numbers.py','heldout_audit_utils.py','watch_heldout_14.py']:
        shutil.copy2(ROOT/'analysis'/name,code/name)
    print(json.dumps({'reports':24,'old_studies_verified':len(oldchecks),'reviewed':24,'unresolved':0}))

def seal():
    assert not(P/'analysis_manifest.json').exists()
    verify()
    paths=sorted(f for f in P.rglob('*') if f.is_file() and 'checkout' not in f.relative_to(P).parts and '__pycache__' not in f.parts)
    files={str(f.relative_to(P)):sha(f) for f in paths}
    save(P/'analysis_manifest.json',dict(utc=now(),files=files,excluded='Mutable checkout and __pycache__; canonical code archive included.'))
    assert all(sha(P/name)==digest for name,digest in files.items())
    save(P/'seal_verification.json',dict(utc=now(),files=len(files),all_passed=True))
    print('sealed',len(files))

if __name__=='__main__':
    {'package':package,'seal':seal}[sys.argv[1]]()
