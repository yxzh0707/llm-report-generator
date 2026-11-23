"""Rebuild dissertation tables solely from a frozen plan and saved run artifacts.

Post-processing provenance is hashed separately from the frozen generation code.
No model/provider calls, score imputation, threshold changes or report revisions.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
if __package__:
    from .review_validation import validate_review
else:
    from review_validation import validate_review


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')


def csv_table(path, rows):
    if not rows: return
    with path.open('w', newline='') as stream:
        writer=csv.DictWriter(stream, fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def fraction(n,d):
    return {'numerator':n,'denominator':d,'ratio':n/d if d else None}

REVIEW_METADATA=('review_method','confirmation_origin','confirmation_record_sha256',
                 'model_review_qid','model_result_sha256')


def build(root, freeze):
    root,freeze=Path(root).resolve(),Path(freeze).resolve()
    plan=json.loads((freeze/'run_plan.json').read_text())
    freeze_manifest=json.loads((freeze/'freeze_manifest.json').read_text())
    for name,expected in freeze_manifest['files'].items():
        if sha((freeze/name).read_bytes())!=expected:
            raise ValueError('Frozen input changed: '+name)
    ledger=json.loads((root/'artifacts/experiments'/freeze.name/'ledger.json').read_text())
    rubric=json.loads((freeze/'rubric.json').read_text())
    out=root/'artifacts/tables'/freeze.name;out.mkdir(parents=True,exist_ok=True)
    worksheet=out/'human_content_worksheet.csv'
    prior_human={}
    human_input_sha256=sha(worksheet.read_bytes()) if worksheet.exists() else None
    if worksheet.exists():
        with worksheet.open(newline='') as stream:
            for row in csv.DictReader(stream):
                key=(row['cell'],row['criterion'])
                if key in prior_human:
                    raise ValueError('Duplicate human worksheet item: '+str(key))
                prior_human[key]=row
    rows=[];items=[];citations=[];human=[];audits=[]
    for cfg in plan:
        cell=f"{cfg['condition_id']}_r{cfg['repetition']}"
        entry=next((e for e in ledger['entries'] if e['cell']==cell),None)
        run_dir=None
        if entry:
            local=root/'artifacts/runs'/Path(entry['run_dir']).name
            run_dir=local if local.exists() else Path(entry['run_dir'])
        m=json.loads((run_dir/'run_manifest.json').read_text()) if run_dir and (run_dir/'run_manifest.json').exists() else {}
        audit=json.loads((run_dir/'audit.json').read_text()) if run_dir and (run_dir/'audit.json').exists() else {}
        original=(run_dir/'raw_report.md').read_text() if run_dir and (run_dir/'raw_report.md').exists() else ''
        raw_integrity='not_available'
        if m:
            if m['code']['sha256']!=freeze_manifest['code_sha256'] or m['runtime']['sha256']!=freeze_manifest['runtime']['sha256']:
                raise ValueError('Run generation code differs from freeze: '+cell)
            if m.get('raw_report_sha256') is not None:
                if sha(original.encode())!=m['raw_report_sha256']:
                    raise ValueError('Saved raw report changed: '+cell)
                raw_integrity='hash_verified'
            elif m['status']=='failed' and not original:
                raw_integrity='empty_failed_run_before_report_hash'
            else:
                raise ValueError('Nonempty or successful report lacks saved hash: '+cell)
            if m['frozen_evidence_sha256']!=cfg['frozen_evidence_sha256']:
                raise ValueError('Run evidence differs from plan: '+cell)
        evidence=json.loads((run_dir/'evidence_ledger.json').read_text()) if run_dir and (run_dir/'evidence_ledger.json').exists() else []
        native=json.loads((run_dir/'runtime_output.json').read_text()) if run_dir and (run_dir/'runtime_output.json').exists() else {}
        linked=json.loads((run_dir/'enhanced_evidence_audit.json').read_text()) if run_dir and (run_dir/'enhanced_evidence_audit.json').exists() else {}
        complete=bool(m) and m.get('status')=='succeeded'
        mode=cfg['request']['source_mode']; permitted={'uploaded','web'} if mode=='hybrid' else {'web' if mode=='web_only' else 'uploaded'}
        closure=set(json.loads((run_dir/'resolved_config.json').read_text()).get('tool_closure',[])) if m else set()
        calls=native.get('tool_calls',[])
        violation=any(s['source_kind'] not in permitted for s in evidence) or any(t['name'] not in closure for t in calls)
        body=re.split(r'^#{1,6} Sources\s*$',original,maxsplit=1,flags=re.M)[0]
        body=re.sub(r'^```[^\n]*\n.*?^```[^\n]*$', '', body, flags=re.M|re.S)
        ids=re.findall(r'\[S\d+\]',body);known={s['citation'] for s in evidence}
        for identity in sorted(set(ids)):
            citations.append({'cell':cell,'run_id':m.get('run_id'),'citation_id':identity,
                'occurrences':ids.count(identity),'known':identity in known})
        a=audit.get('automatic',{}); custom=audit.get('customization',{})
        custom_items={i['id']:i for i in custom.get('items',[])}
        check_items=[('runtime_completed',complete),
            ('preset_heading_presence_level_order_unique',bool(a) and not a['missing_headings'] and not a['wrong_heading_levels'] and not a['duplicate_headings'] and a['section_order_correct']),
            ('body_citations_present_and_known',bool(ids) and all(i in known for i in ids)),
            ('source_mode_body_coverage',audit.get('source_mode_passed',False)),
            ('selected_document_body_coverage',audit.get('selected_document_body_coverage',False)),
            ('depth_word_range',custom_items.get('depth_words',{}).get('passed',False))]
        if cfg['request']['style']=='concise_briefing':
            check_items.append(('style_observable_format',all(custom_items.get(k,{}).get('passed',False) for k in ['briefing_bullets','briefing_bullet_words'])))
        elif cfg['request']['style']=='detailed_explanatory':
            check_items.append(('style_observable_format',custom_items.get('explanatory_subheadings',{}).get('passed',False)))
        if cfg['request']['structure']=='comparative_analysis':
            check_items.append(('comparison_table_when_requested',custom_items.get('comparison_table',{}).get('passed',False)))
        for identity,passed in check_items:
            items.append({'cell':cell,'run_id':m.get('run_id'),'item':identity,'passed':passed,
                          'numerator':int(passed),'denominator':1,'judgment_type':'automatic'})
        group='customization' if cfg.get('customization_pair') else 'main'
        tokens=(m.get('usage') or {}).get('total_tokens')
        rows.append({'cell':cell,'group':group,'condition':cfg['condition_id'],'repetition':cfg['repetition'],
            'run_id':m.get('run_id'),'runtime_status':m.get('status','not_run'),
            'raw_report_integrity':raw_integrity,
            'runtime_completed':complete,'report_nonempty':bool(original),
            'mechanical_passed':a.get('mechanical_checks_passed',False),
            'automatic_passed':complete and audit.get('automatic_passed',False),
            'strict_success':None if complete and audit.get('automatic_passed') else False,
            'source_mode':mode,'source_mode_violation':violation,
            'required_source_classes_cited':audit.get('source_mode_passed',False),
            'valid_citation_occurrences':sum(i in known for i in ids),'citation_occurrences':len(ids),
            'constraints_satisfied':sum(v for _,v in check_items),'constraints_total':len(check_items),
            'native_claim_lines_linked':linked.get('claim_lines_with_local_reference'),
            'native_claim_lines_total':linked.get('claim_lines'),
            'body_word_count':custom_items.get('depth_words',{}).get('observed'),
            'model_attempts':m.get('model_calls'), 'tool_requests':len(calls),
            'tool_failures':sum(t['status']!='succeeded' for t in calls),
            'retry_events':sum(e['type']=='retry_started' for e in native.get('trajectory',[])),
            'timeout_terminal':m.get('status')=='timed_out','total_tokens':tokens,
            'elapsed_seconds':m.get('elapsed_seconds'),'actual_human_review_completed':False,
            'code_sha256':m.get('code',{}).get('sha256'),'corpus_sha256':m.get('corpus_sha256'),
            'frozen_evidence_sha256':cfg['frozen_evidence_sha256']})
        task=cfg.get('customization_pair',{}).get('base_condition',cfg['condition_id']).split('_')[0]
        criteria=list(rubric['content_coverage']['criteria_per_task'][task])
        if criteria and criteria[0]=='same as T5':
            criteria=list(rubric['content_coverage']['criteria_per_task']['T5'])+criteria[1:]
        for criterion in criteria+['requested style/tone and semantic depth']:
            row={'cell':cell,'run_id':m.get('run_id'),'criterion':criterion,
                'satisfied':'','reason':'','actual_reviewer':'','judgment_type':'pending_actual_human'}
            old=prior_human.get((cell,criterion),{})
            if old and old.get('run_id') != m.get('run_id'):
                raise ValueError('Human worksheet run identity differs from plan: '+cell)
            for key in ('satisfied','reason','actual_reviewer')+REVIEW_METADATA:
                row[key]=old.get(key,'')
            if row['satisfied']:
                if row['satisfied'].lower() not in {'true','false'} or not row['actual_reviewer'].strip() or not row['reason'].strip():
                    raise ValueError('Human scores require true/false, actual reviewer and reason: '+cell)
                row['judgment_type']='actual_human'
            elif old.get('judgment_type')=='actual_human_uncertain':
                if not row['actual_reviewer'].strip() or not row['reason'].strip():
                    raise ValueError('Reviewed uncertainty requires reviewer and reason: '+cell)
                row['judgment_type']='actual_human_uncertain'
            human.append(row)
    unknown=set(prior_human)-{(h['cell'],h['criterion']) for h in human}
    if unknown:
        raise ValueError('Unknown human worksheet item; refusing to discard input: '+str(sorted(unknown)))
    for row in rows:
        judgments=[h for h in human if h['cell']==row['cell']]
        complete=bool(judgments) and all(h['judgment_type'] in {'actual_human','actual_human_uncertain'} for h in judgments)
        row['actual_human_review_completed']=complete
        if row['automatic_passed']:
            if any(h['satisfied'].lower()=='false' for h in judgments):
                row['strict_success']=False
            elif complete and all(h['satisfied'].lower()=='true' for h in judgments):
                row['strict_success']=True
            # Explicit uncertainty remains indeterminate, never an imputed pass.
    assert len(rows)==24 and sum(r['group']=='main' for r in rows)==21
    summaries={}
    for group in ['main','customization']:
        selected=[r for r in rows if r['group']==group];n=len(selected)
        def metric(key):return fraction(sum(bool(r[key]) for r in selected),n)
        known_tokens=[r['total_tokens'] for r in selected if r['total_tokens'] is not None]
        summaries[group]={'planned':n,'attempted':sum(r['runtime_status']!='not_run' for r in selected),
            'runtime_completion':metric('runtime_completed'),'report_nonempty':metric('report_nonempty'),
            'mechanical_checks':metric('mechanical_passed'),'automatic_all_constraints':metric('automatic_passed'),
            'mode_violations':metric('source_mode_violation'),
            'required_source_classes_cited':metric('required_source_classes_cited'),
            'citation_validity':fraction(sum(r['valid_citation_occurrences'] for r in selected),sum(r['citation_occurrences'] for r in selected)),
            'constraint_items':fraction(sum(r['constraints_satisfied'] for r in selected),sum(r['constraints_total'] for r in selected)),
            'native_linkage_heuristic':fraction(sum(r['native_claim_lines_linked'] or 0 for r in selected),sum(r['native_claim_lines_total'] or 0 for r in selected)),
            'native_linkage_available_runs':sum(r['native_claim_lines_total'] is not None for r in selected),
            'model_attempts':sum(r['model_attempts'] or 0 for r in selected),
            'tool_requests':sum(r['tool_requests'] for r in selected),'tool_failures':sum(r['tool_failures'] for r in selected),
            'retry_events':sum(r['retry_events'] for r in selected),'timeout_terminals':sum(r['timeout_terminal'] for r in selected),
            'known_total_tokens':sum(known_tokens),'usage_available':fraction(len(known_tokens),n),
            'elapsed_sum_seconds':sum(r['elapsed_seconds'] or 0 for r in selected),
            'elapsed_range_seconds':[min(r['elapsed_seconds'] for r in selected if r['elapsed_seconds'] is not None),max(r['elapsed_seconds'] for r in selected if r['elapsed_seconds'] is not None)],
            'factual_support':{'status':'pending_actual_human','numerator':None,'denominator':None},
            'human_task_coverage':{'status':'pending_actual_human','numerator':None,'denominator':len([h for h in human if h['cell'] in {r['cell'] for r in selected}])}}
        judged=[h for h in human if h['cell'] in {r['cell'] for r in selected} and h['judgment_type']=='actual_human']
        uncertain=[h for h in human if h['cell'] in {r['cell'] for r in selected} and h['judgment_type']=='actual_human_uncertain']
        total=summaries[group]['human_task_coverage']['denominator']
        reviewed=len(judged)+len(uncertain)
        satisfied=sum(h['satisfied'].lower()=='true' for h in judged)
        summaries[group]['human_task_coverage'].update(
            status=('complete_with_uncertainty' if uncertain else 'complete') if reviewed==total else 'pending_actual_human',
            judged_items=len(judged),satisfied_judged_items=satisfied,
            reviewed_items=reviewed,uncertain_items=len(uncertain),unreviewed_items=total-reviewed,
            not_satisfied_items=len(judged)-satisfied,
            numerator=satisfied if reviewed==total else None,
            review_coverage=fraction(reviewed,total),
            satisfied_over_all_items=fraction(satisfied,total),
            judgment_coverage=fraction(len(judged),total),
            satisfaction_among_judged=fraction(satisfied,len(judged)))
        summaries[group]['strict_success']={
            'known_true':sum(r['strict_success'] is True for r in selected),
            'known_false':sum(r['strict_success'] is False for r in selected),
            'pending':sum(r['strict_success'] is None for r in selected),'planned':n}
    pairs=[]
    for cfg in plan:
        if not cfg.get('customization_pair'):continue
        pair=cfg['customization_pair'];base=next(r for r in rows if r['condition']==pair['base_condition'] and r['repetition']==pair['base_repetition']);variant=next(r for r in rows if r['condition']==cfg['condition_id'])
        assert base['frozen_evidence_sha256']==variant['frozen_evidence_sha256']
        pairs.append({'pair':cfg['condition_id'],'change':pair['change'],'base_run_id':base['run_id'],
            'variant_run_id':variant['run_id'],'same_evidence_sha256':base['frozen_evidence_sha256'],
            'base_words':base['body_word_count'],'variant_words':variant['body_word_count'],
            'base_automatic_passed':base['automatic_passed'],'variant_automatic_passed':variant['automatic_passed'],
            'interpretation':'descriptive paired observation only; no general causal improvement claim'})
    source_items=[]
    for sample in rubric['human_source_audit']['preselected']:
        selected=next(r for r in rows if r['condition']==sample['condition'] and r['repetition']==sample['repetition'])
        package_path=root/'artifacts/runs'/selected['run_id']/'human_review/review.json' if selected['run_id'] else None
        review=json.loads(package_path.read_text()) if package_path and package_path.exists() else {}
        validated=validate_review(package_path.parent.parent,review) if review else {
            'items':[],'expected_claims':0,'actual_reviewers':[],'completed':False}
        reviewed=[i for i in validated['items'] if i['judgment'] is not None]
        source_items.extend({'cell':selected['cell'],'run_id':selected['run_id'],**i}
                            for i in validated['items'])
        audits.append({'cell':selected['cell'],'run_id':selected['run_id'],
            'report_status':selected['runtime_status'],'expected_claims':5,
            'available_proposed_claims':validated['expected_claims'],
            'review_package':str(root/'artifacts/runs'/selected['run_id']/'human_review') if selected['run_id'] else None,
            'actual_reviewer':review.get('actual_reviewer'),
            'actual_reviewers':validated['actual_reviewers'],'completed':validated['completed'],
            'reviewed_claims':len(reviewed),'supported':sum(i['judgment']=='supported' for i in reviewed),
            'contradicted':sum(i['judgment']=='contradicted' for i in reviewed),
            'insufficient':sum(i['judgment']=='insufficient' for i in reviewed),
            'review_file_sha256':sha(package_path.read_bytes()) if package_path and package_path.exists() else None})
    judged_claims=sum(a['reviewed_claims'] for a in audits)
    summaries['main']['factual_support']={
        'status':'complete' if all(a['completed'] for a in audits) else 'pending_actual_human',
        'prespecified_reports':len(audits),'planned_claims':sum(a['expected_claims'] for a in audits),
        'reviewed_claims':judged_claims,
        'supported':sum(a['supported'] for a in audits) if judged_claims else None,
        'contradicted':sum(a['contradicted'] for a in audits) if judged_claims else None,
        'insufficient':sum(a['insufficient'] for a in audits) if judged_claims else None,
        'support_among_judged':fraction(sum(a['supported'] for a in audits),judged_claims),
        'review_coverage':fraction(judged_claims,sum(a['expected_claims'] for a in audits))}
    summaries['customization']['factual_support']={'status':'not_in_prespecified_source_audit','numerator':None,'denominator':None}
    save(out/'per_run.json',rows);csv_table(out/'per_run.csv',rows);csv_table(out/'automatic_items.csv',items)
    csv_table(out/'citation_items.csv',citations);csv_table(out/'human_content_worksheet.csv',human)
    save(out/'summary.json',summaries);save(out/'customization_pairs.json',pairs);save(out/'human_audit_selection.json',audits)
    save(out/'source_support_items.json',source_items)
    provenance={'generation_freeze':str(freeze),'generation_freeze_sha256':sha((freeze/'freeze_manifest.json').read_bytes()),
        'rubric_sha256':sha((freeze/'rubric.json').read_bytes()),'postprocessor':str(Path(__file__).resolve()),
        'postprocessor_sha256':sha(Path(__file__).read_bytes()),
        'human_content_input_sha256':human_input_sha256,
        'postprocessing_files_sha256':{p.name:sha(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('*.py'))},
        'notes':['All planned cells retained; main and customization denominators separate.',
                 'Raw report checks, display rendering, runtime completion and factual support are distinct.',
                 'Native linkage is a line heuristic over saved raw report, including reference-like lines; it is not entailment.',
                 'Citation validity counts occurrences in body, excluding Sources and fenced code.',
                 'Missing usage is unknown; sums include known usage only with availability denominator.',
                 'Review method and confirmation origin distinguish model-assisted author review from independent annotation.',
                 'Explicit human uncertainty counts as reviewed, but never as satisfied or a strict pass; binary resolved denominators exclude it.',
                 'Review report hashes, original item IDs, evidence and any explicit selection changes are validated before accepting grades.']}
    save(out/'provenance.json',provenance)
    lines=['# Frozen formal results','', '| Group | Runtime complete | Mechanical | All automatic constraints | Mode violations | Known tokens |', '|---|---|---|---|---|---|']
    for group,s in summaries.items():
        def display(name):v=s[name];return f"{v['numerator']}/{v['denominator']}"
        lines.append(f"| {group} | {display('runtime_completion')} | {display('mechanical_checks')} | {display('automatic_all_constraints')} | {display('mode_violations')} | {s['known_total_tokens']} |")
    support=summaries['main']['factual_support']
    lines+=['',f"Actual human source support: {support['status']} ({support['reviewed_claims']}/{support['planned_claims']} prespecified claims graded)."]
    for group,s in summaries.items():
        coverage=s['human_task_coverage'];strict=s['strict_success']
        lines.append(f"Human task/style judgments ({group}): {coverage['status']} ({coverage['reviewed_items']}/{coverage['denominator']} reviewed; {coverage['uncertain_items']} uncertain). Strict success: {strict['known_true']} true, {strict['known_false']} false, {strict['pending']} indeterminate.")
    lines+=['',
            'See summary.json for explicit numerators/denominators, per_run.csv and automatic_items.csv for every outcome, and provenance.json for generation and analysis code hashes.']
    (out/'summary.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'output':str(out),'summary':summaries},indent=2))
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path.cwd());p.add_argument('--freeze',required=True,type=Path)
    args=p.parse_args();build(args.root,args.freeze)
