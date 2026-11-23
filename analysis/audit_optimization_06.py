"""Recorded assistant adjudications after reading the flagged reports and sources."""
import json,re
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'artifacts/report_study/system_optimization_06'
def read(p):return json.loads(p.read_text())
def norm(s):return re.sub(r'\s+',' ',s).strip()
edits=read(P/'semantic_adjudications.json');tasks={t['id']:t for t in read(P/'tasks.json')}
decisions={('broadcom_qualcomm_standard', 'business_B'): (True, 'The report explicitly describes 27% Automotive/IoT growth as full-year FY2025 rather than a quarterly figure, with management attribution and Q4 source citation.'), ('broadcom_qualcomm_detailed', 'business_A'): (True, 'The 74% Q4 AI semiconductor growth result is distinguished from the $8.2 billion Q1 forecast; the judge quotation shortens the actual sentence.'), ('costco_target_detailed', 'narrative_consistency'): (True, 'Revenue includes Costco membership fees and agrees with source totals; Target net sales and both display-based H2 sums are consistent. Judge source quotes omit table punctuation.'), ('ibm_netflix_brief', 'cross_source_synthesis'): (True, 'The comparison explicitly connects company revenue scale and business models and avoids equating revenue with investment quality; the actual revenue rows support the comparison.'), ('ibm_netflix_brief', 'period_scope'): (False, 'The sentence starts Fiscal calendars differ in duration and then says both use aligned calendar quarters. The sources show aligned three-month periods; the assertion of differing duration is unsupported.'), ('ibm_netflix_brief', 'narrative_consistency'): (False, 'The calendar sentence simultaneously asserts differing duration and aligned calendar periods. This contradicts the supplied three-month statements and its own concluding clause.'), ('ibm_netflix_standard', 'period_scope'): (True, 'Both companies Q3 and Q4 end on the same September 30 and December 31 dates. The judge joined table headings separated by other columns; the full original table context supports alignment.'), ('ibm_netflix_standard', 'narrative_consistency'): (True, 'Revenue figures, sums and narrative comparisons agree with the sources; the report explicitly avoids profitability or investment-quality inference. Judge quotation is a shortened sentence rather than an exact passage.'), ('ibm_netflix_detailed', 'period_scope'): (True, 'The report correctly describes matching three-month periods and distinguishes forecasts. The full table headers support its dates despite noncontiguous judge excerpts.')}
for (tid,key),(passed,reason) in decisions.items():
    rid=tid+'_report_system_1';folder=P/'runs'/rid;report=(folder/'evaluated_report.md').read_text();ledger=read(folder/'evidence_ledger.json');t=tasks[tid]
    selected=[]
    if key=='period_scope':
        for s in ledger:
            text=norm(s['text']);m=re.search(r'Three Months Ended',text,re.I)
            if m:selected.append(dict(citation=s['citation'],quote=text[max(0,m.start()-70):m.end()+300]))
    elif key=='narrative_consistency' and tid=='unused_special_case':
        s=next(s for s in ledger if s['document_id']=='ibm_q4');text=norm(s['text']);i=text.find('61.8');assert i>=0
        selected.append(dict(citation=s['citation'],quote=text[max(0,i-180):i+150]))
    else:
        for ref in t['highlights']:
            s=next((s for s in ledger if s['document_id']==ref['source_id']),None)
            if s and ref['reference_quote'] in norm(s['text']):selected.append(dict(citation=s['citation'],quote=ref['reference_quote']))
        for ref in t['expected']:
            s=next((s for s in ledger if s['document_id']==ref['source_id']),None)
            if s and norm(ref['proof']) in norm(s['text']):selected.append(dict(citation=s['citation'],quote=norm(ref['proof'])))
    patterns={'period_scope':r'calendar|period.*end|three months', 'business_A':r'74%|8\.2', 'business_B':r'27%|fiscal year',
              'cross_source_synthesis':r'larger|growth|compare|unavailable', 'requested_depth':r'^##|unavailable|growth',
              'narrative_consistency':r'calendar|61\.8|61\.97|84\.43|63\.21|86\.16|net sales|membership|H2 revenue'}
    report_quotes=[l for l in report.splitlines() if re.search(patterns[key],l,re.I)][:12]
    assert selected and report_quotes,(tid,key)
    edits=[e for e in edits if(e['run_id'],e['criterion'])!=(rid,key)]
    edits.append(dict(run_id=rid,criterion=key,passed=passed,reviewer='assistant_source_and_report_adjudication',
                      reason=reason,report_quotes=report_quotes,source_quotes=selected))
(P/'semantic_adjudications.json').write_text(json.dumps(edits,ensure_ascii=False,indent=2)+'\n')
print('Adjudicated',len(decisions),'flagged/misclassified criteria')
