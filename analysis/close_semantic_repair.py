"""Archive targeted development repairs, independently of the main comparison."""
import argparse,difflib,html,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from experiments.system_comparison import read,save,sha,now
from provenance import source_version

def package(p):
    summary=read(p/'final_summary.json');assert summary['completed_runs']==4 and summary['unresolved']==0
    g=summary['groups']['report_system'];old=ROOT/'artifacts/report_study/system_optimization_10'
    records=[];audits={r['run_id']:r for r in read(p/'targeted_source_audit.json')['records']}
    for j in read(p/'jobs.json'):
        folder=p/'runs'/j['run_id'];before=old/'runs'/j['run_id']/'evaluated_report.md';after=folder/'evaluated_report.md'
        m=read(folder/'run_manifest.json');checks=read(folder/'validation_checks.json')
        diff=''.join(difflib.unified_diff(before.read_text().splitlines(True),after.read_text().splitlines(True),fromfile='original',tofile='repaired'))
        (folder/'changes.diff').write_text(diff)
        records.append(dict(task_id=j['task_id'],expected_code=j['expected_code'],delivered=m['delivered'],
            checks_passed=bool(m['delivered'] and checks[-1]['passed']),repair_confirmed=audits[j['run_id']]['passed'],model_calls=m.get('model_calls'),
            terminal=m.get('terminal',{}).get('error_code'),report_sha256=sha(after),
            before_sha256=sha(before),validation_attempts=len(checks)-1,
            lengths=read(folder/'length_checks.json') if(folder/'length_checks.json').exists() else []))
    save(p/'repair_results.json',records)
    frozen=read(p/'freeze.json');inputs={name:sha(ROOT/name)==h for name,h in frozen['inputs'].items()}
    assert all(inputs.values())
    archive=Path(frozen['snapshot']['archive']);assert sha(archive)==frozen['snapshot']['archive_sha256']
    oldchecks=[]
    for n in range(5,11):
        folder=ROOT/'artifacts/report_study'/f'system_optimization_{n:02d}'
        manifest=read(folder/'analysis_manifest.json')
        checks={name:sha(folder/name)==h for name,h in manifest['files'].items()}
        assert all(checks.values()),folder
        oldchecks.append(dict(batch=folder.name,files=len(checks),unchanged=True))
    offline=read(p/'offline_results.json');normal=[x for x in offline if not x['known_failure']]
    verification=dict(utc=now(),frozen_input_files=len(inputs),all_inputs_unchanged=True,
        frozen_archive_verified=True,old_studies=oldchecks,
        known_errors_detected=sum(r['known_failure'] and r['detection_matches'] for r in offline),
        normal_controls=len(normal),normal_controls_passed=sum(r['full_validation']['passed'] for r in normal),
        repaired_deliveries=sum(r['repair_confirmed'] for r in records),unresolved=summary['unresolved'],
        independent_source_audit='targeted_source_audit.json',
        source_matches_current=source_version(ROOT)['sha256']==frozen['source']['sha256'])
    save(p/'verification.json',verification)
    labels={'narrative_growth_basis':'同比／环比口径','narrative_period_overlap':'期间关系','narrative_ratio':'摘要收入比例','narrative_metric_label':'完整指标名称'}
    rows=''.join(f'<tr><td>{labels[r["expected_code"]]}</td><td>{"修复并交付" if r["repair_confirmed"] else "已交付，但新增计算错误" if r["delivered"] else "未交付"}</td><td>{r["model_calls"]}</td><td><a href="runs/{r["task_id"]}_report_system_1/changes.diff">改动</a> · <a href="runs/{r["task_id"]}_report_system_1/initial_feedback.json">依据</a></td></tr>' for r in records)
    prev='<p>首轮 semantic_repair_11 为 3/4 交付。本轮调整计算返工计数：成功计算不占用下一条错误链的三次额度；16 次模型、24 次工具的总预算不变。四份原始问题稿全部重新验证，没有拼接两轮最佳结果。</p>' if p.name.endswith('12') else '<p>本轮三份问题稿修复并交付；同比／环比案例尝试补算环比，两个不完整计算计划与此前一次成功计算合计触发三次调用上限，保留为失败。</p>'
    document=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>正文一致性修复验证</title><style>body{{font:16px/1.7 system-ui,sans-serif;max-width:1000px;margin:48px auto;padding:0 24px;color:#183344;background:#f5f8fa}}table{{border-collapse:collapse;background:white;width:100%}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #d7e1e8}}a{{color:#14668c}}h1{{font-size:28px}}</style><h1>正文一致性修复验证</h1><p>系统把正文中的比较口径、指标名称、期间关系和收入比例与原文及已核验数据对应。发现矛盾时，将具体句子、来源和计算依据返回 Qwen；修订稿再次通过统一保存检查。</p><p><strong>已知错误检出 4/4，正常稿门控检查 12/12 通过；本轮真实 Qwen 返工交付 {g['delivered']}/4。</strong></p>{prev}<table><tr><th>问题</th><th>结果</th><th>模型调用</th><th>记录</th></tr>{rows}</table><p>独立结果核验：季度金额及来源 {g['quarter_facts_supported']}/{g['quarter_facts_available']}；缺失项披露 {g['missing_correct']}/{g['missing_items']}；H2 计算 {g['derived_correct']}/{g['derived_items']}；业务主题 {g['business_topics_passed']}/{g['business_topics']}；格式 {g['format_passed']}/4。匿名 DeepSeek 评审另经引文与来源复核。</p><p>这组结果验证已知错误的拦截和返工能力；12 份对照为原稿检查，不是新增生成。它与主对照分开统计。识别器目前覆盖明确英文金融句式，下一项优先验证新公司、新期间和不同表达上的表现。</p><p><a href="protocol.json">实验配置</a> · <a href="targeted_source_audit.json">逐例原文复核</a> · <a href="final_summary.json">结果</a> · <a href="offline_results.json">16 份原稿检查</a> · <a href="verification.json">完整性核验</a></p></html>'''
    (p/'report.html').write_text(document)
    code=p/'analysis_code';code.mkdir(exist_ok=True)
    for name in ['close_semantic_repair.py','evaluate_system_comparison.py','adjudicate_system_comparison.py','normalize_system_judge_quotes.py']:
        shutil.copy2(ROOT/'analysis'/name,code/name)

def seal(p):
    assert not(p/'analysis_manifest.json').exists()
    assert(p/'targeted_source_audit.json').exists()
    paths=sorted(f for f in p.rglob('*') if f.is_file() and '__pycache__' not in f.parts)
    files={str(f.relative_to(p)):sha(f) for f in paths}
    save(p/'analysis_manifest.json',dict(utc=now(),files=files))
    assert all(sha(p/name)==h for name,h in files.items())
    save(p/'seal_verification.json',dict(utc=now(),files=len(files),all_passed=True))
    print(p.name,'sealed',len(files))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('batch',choices=['11','12']);ap.add_argument('action',choices=['package','seal']);a=ap.parse_args()
    globals()[a.action](ROOT/'artifacts/report_study'/('semantic_repair_'+a.batch))
