"""Artifact-only synthesis of the supplementary study (no manuscript writes)."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import statistics


def read(p): return json.loads(Path(p).read_text())


def build(out):
    plan = read(out/'plan.json')
    runs = {j['id']:read(out/'runs'/j['id']/'result.json') for j in plan}
    items = read(out/'evaluation/items.json') if (out/'evaluation/items.json').exists() else []
    evaluation = read(out/'evaluation/summary.json') if items else {}

    def semantics(jid, stage):
        rr = [x for x in items if x['variant']=='report' and x['run_id']==jid and x['stage']==stage and not x.get('diagnostic')]
        if not rr and stage=='initial' and not runs[jid]['repair_attempted']:
            rr = [x for x in items if x['variant']=='report' and x['run_id']==jid and x['stage']=='final' and not x.get('diagnostic')]
        c = Counter(x['label'] for x in rr)
        return {'planned':len(rr),'yes':c['YES'],'no':c['NO'],'unknown':c['UNKNOWN'],'invalid':c['INVALID'],
                'lower':c['YES']/len(rr) if rr else None,'all_yes':bool(rr) and c['YES']==len(rr)}

    conditions=[]
    for cid in dict.fromkeys(j['condition'] for j in plan if j['group']=='main'):
        row={'condition':cid}
        for arm,stage,label in [('direct','initial','direct'),('system','initial','system_initial'),('system','final','system_final')]:
            jj=[j for j in plan if j['condition']==cid and j['group']=='main' and j['arm']==arm]
            rr=[runs[j['id']] for j in jj]
            sem=[semantics(j['id'],stage) for j in jj]
            row[label]={'n':len(jj),'automatic_pass':sum(r[stage]['audit']['automatic_passed'] for r in rr),
                'words':[r[stage]['audit']['body_words'] for r in rr],
                'semantic_yes':sum(s['yes'] for s in sem),'semantic_n':sum(s['planned'] for s in sem),
                'all_automatic_and_judge_requirements':sum(r[stage]['audit']['automatic_passed'] and s['all_yes'] for r,s in zip(rr,sem)),
                'meaning':'automatic plus same-model requirement checks, not historical human-confirmed strict success'}
        conditions.append(row)
    repairs=[]
    for j in plan:
        r=runs[j['id']]
        if not r['repair_attempted']: continue
        old=semantics(j['id'],'initial');new=semantics(j['id'],'final')
        ri={x['id']:x for x in items if x['variant']=='report' and x['run_id']==j['id'] and x['stage']=='initial' and not x.get('diagnostic')}
        rf={x['id']:x for x in items if x['variant']=='report' and x['run_id']==j['id'] and x['stage']=='final' and not x.get('diagnostic')}
        transitions=[{'id':k,'before':ri[k]['label'],'after':rf[k]['label']} for k in ri if k in rf and ri[k]['label']!=rf[k]['label']]
        repairs.append({'id':j['id'],'group':j['group'],'initial_words':r['initial']['audit']['body_words'],
            'final_words':r['final']['audit']['body_words'],'final_pass':r['final']['audit']['automatic_passed'],
            'initial_semantic':old,'final_semantic':new,'label_transitions':transitions})
    paired=[]
    for j in plan:
        if j['group'] not in ('customization','evidence_repair'): continue
        base=runs[j['base']];variant=runs[j['id']]
        paired.append({'id':j['id'],'base':j['base'],'group':j['group'],'axis':j.get('axis','evidence'),
            'base_words':base['final']['audit']['body_words'],'variant_words':variant['final']['audit']['body_words'],
            'base_auto':base['final']['audit']['automatic_passed'],'variant_auto':variant['final']['audit']['automatic_passed'],
            'base_semantic':semantics(j['base'],'final'),'variant_semantic':semantics(j['id'],'final')})
    resource=[]
    for j in plan:
        r=runs[j['id']];u=r['initial'].get('usage') or {};v=r['final'].get('usage') or {}
        resource.append({'id':j['id'],'group':j['group'],'arm':j['arm'],
            'initial_tokens':u.get('total_tokens'),
            'repair_tokens':v.get('total_tokens') if r['repair_attempted'] else 0,
            'initial_seconds':r['initial'].get('elapsed_seconds'),
            'repair_seconds':r['final'].get('elapsed_seconds') if r['repair_attempted'] else 0,
            'initial_calls':r['initial'].get('model_calls'), 'repair_calls':int(r['repair_attempted'])})
    summary={'conditions':conditions,'repairs':repairs,'paired':paired,'resources':resource,
        'generation_tokens_known_sum':sum((r['initial_tokens'] or 0)+(r['repair_tokens'] or 0) for r in resource),
        'generation_usage_unknown':sum(r['initial_tokens'] is None or r['repair_tokens'] is None for r in resource),
        'generation_model_calls':sum((r['initial_calls'] or 0)+r['repair_calls'] for r in resource),
        'evaluation_tokens':evaluation.get('usage'),'calibration_gate_passed':evaluation.get('calibration_gate_passed'),
        'analysis_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out/'comparison_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    esc=lambda x:html.escape(str(x))
    def table(head,rows):
        return '<table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(c)+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table>'
    main=[]
    for c in conditions:
        main.append([c['condition']]+[f"{c[a]['automatic_pass']}/{c[a]['n']}" for a in ('direct','system_initial','system_final')]+[f"{c[a]['semantic_yes']}/{c[a]['semantic_n']}" for a in ('direct','system_initial','system_final')])
    main_totals={a:{'automatic_pass':sum(c[a]['automatic_pass'] for c in conditions),'n':sum(c[a]['n'] for c in conditions),
                   'semantic_yes':sum(c[a]['semantic_yes'] for c in conditions),'semantic_n':sum(c[a]['semantic_n'] for c in conditions)} for a in ('direct','system_initial','system_final')}
    main.append(['合计']+[f"{main_totals[a]['automatic_pass']}/{main_totals[a]['n']}" for a in main_totals]+[f"{main_totals[a]['semantic_yes']}/{main_totals[a]['semantic_n']}" for a in main_totals])
    components=[]
    for arm,stage,label in [('direct','initial','直接生成'),('system','initial','系统首次'),('system','final','系统最终')]:
        rr=[runs[j['id']][stage]['audit'] for j in plan if j['group']=='main' and j['arm']==arm]
        counts=Counter()
        for a in rr:
            for item in a['items']:
                if item['passed']:counts[item['id']]+=1
        components.append([label,len(rr),counts['mechanical'],counts['depth_words'],counts['source_mode'],counts['selected_documents']])
    page='''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>补充实验结果总览</title><style>
body{max-width:1280px;margin:40px auto;padding:0 24px;font:16px/1.7 system-ui;color:#182631;background:#fafbfc}h1{font-size:30px}h2{margin-top:36px;font-size:22px}table{border-collapse:collapse;width:100%;background:white;font-size:14px}td,th{border:1px solid #cbd3da;padding:9px;text-align:left;vertical-align:top}th{background:#e8eff3}a{color:#176b87}.note{padding:16px;background:#edf4f7;border-left:4px solid #357b99}code{word-break:break-word}details{margin:20px 0}pre{white-space:pre-wrap}</style>
<h1>第5、6章补充实验结果</h1><p>本轮新增69次首次生成：42次主对照、21次定制变体、6次截断片段补全验证。系统输出允许最多一次有界修订，原始报告和修订报告分别保存。原21+3次实验和论文文件保持不变。</p>
<p><a href="protocol.json">实验协议</a> · <a href="plan.json">运行计划</a> · <a href="comparison_summary.json">可复核统计</a> · <a href="report.html">逐次生成结果</a> · <a href="evaluation/report.html">逐项自动评审</a></p>
<div class="note">主要基线比较为“直接生成首次输出”与“系统首次输出”：相同模型、任务、来源片段和评分门槛。“系统最终输出”包含额外修订开销，单独衡量修复效果。语义分数来自同模型自动评审，不等同于独立事实准确率，也不替换原论文的人工确认评分。</div>
<h2>一、同材料主对照</h2>'''
    page+=table(['条件','直接生成自动通过','系统首次自动通过','系统最终自动通过','直接生成要求YES','系统首次要求YES','系统最终要求YES'],main)
    if evaluation and not evaluation.get('calibration_gate_passed'):
        page=page.replace('<h2>一、同材料主对照</h2>', '<div class="note"><strong>评审校验未通过：</strong>评审器接受了“60÷100＝42%”的错误计算。下列语义YES统计仅保留为诊断数据，不能据此推断内容质量提升或事实准确率。程序可检查的格式、长度和来源类别结果仍可独立解释。<a href="evaluation/calibration_review.json">校验解释及风险题歧义</a></div><h2>一、同材料主对照</h2>')
    page+='<p>分项通过数（保持原门槛）：标题级别错误、超长与内容遗漏分别解释，不能将自动合规优势直接视为语义质量优势。</p>'
    page+=table(['方案','报告数','结构及引用机械检查','字数范围','来源类别','选定文档覆盖'],components)
    format_path=out/'format_diagnostic/summary.json'
    if format_path.exists():
        fmt=read(format_path)
        page+='<p><strong>事后格式诊断：</strong>只调整准确匹配的规定标题级别，正文词序与词数不变。这是用于解释标题错误影响的额外分析，未替换上面的原始通过率。</p>'
        page+=table(['方案','报告数','原始通过','只修标题后通过'],[[a,v['planned'],v['original_pass'],v['heading_normalized_pass']] for a,v in fmt['groups'].items()])
    page+='<h2>二、修订是否修好长度、是否损失内容</h2><p>修订触发'+str(len(repairs))+'次；修订后自动通过'+str(sum(r['final_pass'] for r in repairs))+'次。以下语义标签变化只是自动评审观察，需要结合原报告核对。</p>'
    page+=table(['报告','首次词数','修订词数','修订自动通过','首次YES/条目','修订YES/条目','标签变化'],[[r['id'],r['initial_words'],r['final_words'],r['final_pass'],f"{r['initial_semantic']['yes']}/{r['initial_semantic']['planned']}",f"{r['final_semantic']['yes']}/{r['final_semantic']['planned']}",'; '.join(x['id']+': '+x['before']+' → '+x['after'] for x in r['label_transitions'])] for r in repairs])
    page+='<h2>三、重复定制与片段补全配对</h2><p>每种条件三次；配对共享来源，单独改变结构、风格或深度。片段补全仅是AMD已知截断问题的定向验证，新增内容约1,400字符以内，不能据此推断通用检索改进。</p>'
    page+=table(['变体','基准词数','变体词数','基准自动通过','变体自动通过','基准YES/条目','变体YES/条目'],[[r['id'],r['base_words'],r['variant_words'],r['base_auto'],r['variant_auto'],f"{r['base_semantic']['yes']}/{r['base_semantic']['planned']}",f"{r['variant_semantic']['yes']}/{r['variant_semantic']['planned']}"] for r in paired])
    if (out/'list_repair_audit.json').exists():
        page+='<p><strong>片段补全的具体效果：</strong>补入同一文档后续1,194字符后，六份报告都能以该来源支持四个分部名称，五份还完整解释了四个分部范围；一份简洁报告遗漏Embedded范围。另有一份将Q1展望误写为Q4，说明局部证据补全没有保证全文正确。这是助手针对该已知问题的核对，未替换自动评审标签。<a href="list_repair_audit.json">逐对原文与依据</a></p>'
    page+='<h2>四、评审器校验和资源</h2><p>已预设六类正确/错误样例，涵盖计算、期间、单位、分部遗漏、无依据解释和风险遗漏。校验门槛通过：'+esc(evaluation.get('calibration_gate_passed'))+'。行号引用核验只验证引用存在；所有无效结果仍计入分母。</p>'
    page+=table(['类型','应判','实际判断','理由'],[[r['case'],r['expected'],r['label'],r.get('reason','')] for r in evaluation.get('calibration',[])])
    page+='<p>生成及修订共 '+str(summary['generation_model_calls'])+' 次模型请求；已记录 '+str(summary['generation_tokens_known_sum'])+' token。评审 token：'+esc(evaluation.get('usage',{}).get('total_tokens','未完成'))+'。完整用量逐次保存在结构化统计中。</p>'
    refinement_path=out/'length_refinement/summary.json'
    if refinement_path.exists():
        ref=read(refinement_path)
        page+='<h2>五、明确词数及分节预算的后续开发验证</h2><p>从仍超长的报告中，按预先固定的字母顺序规则，每个深度取最多三份；每份最多两次重写。样本按失败选择，结果只能说明这些案例是否修好，不能当作新任务的成功率。初轮失败完整保留。</p>'
        rr=[]
        for r in ref['runs']:
            sc=Counter(i['label'] for i in r['semantic_items'])
            rr.append([r['run_id'],r['original_audit']['body_words'],r['final_audit']['body_words'],len(r['attempts']),r['final_audit']['automatic_passed'],dict(sc)])
        page+=table(['报告','修复前词数','新词数','重写次数','自动通过','语义判断（含深度诊断）'],rr)
        page+='<p><a href="length_refinement/protocol.json">开发验证协议</a> · <a href="length_refinement/summary.json">全部尝试与判断</a></p>'
        ref_calls=[a['call'] for r in ref['runs'] for a in r['attempts']]+[r['semantic_call'] for r in ref['runs']]
        ref_tokens=sum((c.get('usage') or {}).get('total_tokens',0) for c in ref_calls)
        all_calls=summary['generation_model_calls']+len(list((out/'evaluation/calls').glob('*/result.json')))+len(ref_calls)
        all_tokens=summary['generation_tokens_known_sum']+(evaluation.get('usage',{}).get('total_tokens') or 0)+ref_tokens
        page+='<p>连同全部自动评审和本节开发验证，本轮合计 '+str(all_calls)+' 次实际模型请求，记录 '+str(all_tokens)+' token。费用沿用项目已声明的免费服务设置。</p>'
        summary.update(all_model_calls=all_calls,all_tokens=all_tokens,refinement_calls=len(ref_calls),refinement_tokens=ref_tokens)
    audits=[]
    for p in (out/'assistant_spot_audit').glob('*.json'):
        a=read(p)
        if a.get('completed'):
            for i in a['items']:audits.append({'run_id':a['run_id'],**i})
    if audits:
        page+='<h2>六、单独的助手来源核对</h2><p>预先选定T2、T4、仅网络比较及混合比较，每组两个方案各取第一次输出的前五个候选事实句。由当前助手检查实际证据，未作为人工评分，也未覆盖全文。自动候选中的自述等较弱条目单独标记；以下判断不覆盖或替换模型评审。</p>'
        counts=Counter(i['judgment'] for i in audits)
        page+='<p>已核对 '+str(len(audits))+' 条；'+esc(dict(counts))+'；较弱候选 '+str(sum(i.get('weak_candidate',False) for i in audits))+' 条。</p>'
        page+='<details><summary>查看逐条核对</summary>'+table(['报告','条目','原句','判断','依据'],[[i['run_id'],i['id'],i['claim'],i['judgment'],i['reason_zh']] for i in audits])+'</details>'
    page+='<h2>报告与证据入口</h2><ul>'
    for j in plan:
        page+='<li>'+esc(j['id'])+'：<a href="runs/'+j['id']+'/final_report.md">最终报告</a> · <a href="runs/'+j['id']+'/initial/raw_report.md">首次报告</a> · <a href="runs/'+j['id']+'/sources.json">实际证据</a></li>'
    page+='</ul></html>'
    (out/'comparison.html').write_text(page)
    (out/'comparison_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'main':main_totals,'repairs':len(repairs),'repair_pass':sum(r['final_pass'] for r in repairs),
        'generation_tokens':summary['generation_tokens_known_sum'],'calibration_gate_passed':summary['calibration_gate_passed']},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();build(a.out.resolve())
