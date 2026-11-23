"""Recorded assistant adjudications after reading the flagged reports and sources."""
import json,re
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'artifacts/report_study/system_optimization_08'
def read(p):return json.loads(p.read_text())
def norm(s):return re.sub(r'\s+',' ',s).strip()
edits=read(P/'semantic_adjudications.json');tasks={t['id']:t for t in read(P/'tasks.json')}
decisions={('ibm_netflix_brief', 'cross_source_synthesis'): (True, 'The report connects both revenue scale and growth drivers, with correct values and explicit limits on profitability inference.'), ('ibm_netflix_brief', 'period_scope'): (True, 'Original three-month statements show aligned September/December quarter ends; the judge combines headers across intervening columns.'), ('ibm_netflix_brief', 'requested_depth'): (True, 'The brief report covers the two requested topics, supported comparison and qualifications with specific evidence. Judge excerpts are shortened combinations of real passages.'), ('ibm_netflix_brief', 'narrative_consistency'): (True, 'Narrative revenue totals and comparisons agree with the source-backed displayed rows, without a profitability-ranking inference.'), ('costco_target_detailed', 'cross_source_synthesis'): (True, 'The report compares revenue scale and growth measures while retaining different definitions and fiscal periods; the approximately 2.8 Q4 ratio is consistent with the displayed amounts.'), ('costco_target_detailed', 'narrative_consistency'): (True, 'Costco includes membership fees and Target uses net sales; narrative, quarterly rows and display-based sums agree.'), ('ibm_netflix_detailed', 'period_scope'): (True, 'Both companies use aligned three-month calendar quarters. Reported results and forecasts are distinguished; full statement context resolves the noncontiguous judge source quote.'), ('ibm_netflix_standard', 'period_scope'): (True, 'The report correctly says the sources do not show a calendar offset; all four period end dates and durations match their statements.'), ('adobe_salesforce_detailed', 'business_A'): (True, 'Adobe Q4 Digital Media revenue of $4.62 billion and 11% growth are correctly identified as a reported quarterly result with its own release citation.'), ('broadcom_qualcomm_missing', 'business_A'): (True, 'Broadcom Q4 AI semiconductor growth of 74% is distinguished from the $8.2 billion Q1 forecast and attributed to the Q4 release.'), ('costco_target_standard', 'period_scope'): (True, 'The report preserves Costco 12/16-week quarters, Target three-month quarters, and correct 174/153-day offsets with the quoted end dates.'), ('costco_target_standard', 'narrative_consistency'): (True, 'The narrative, tables and H2 sums agree with original total revenue/net sales rows and retain the relevant period and metric qualifications.'), ('broadcom_qualcomm_detailed', 'business_B'): (True, 'The 27% Automotive/IoT growth claim explicitly refers to the fiscal year and is not presented as single-quarter growth.'), ('broadcom_qualcomm_detailed', 'cross_source_synthesis'): (True, 'The report compares revenue scale, growth and different growth drivers. Its approximate scale language is supported by the tables and is not used for an investment-quality ranking.'), ('broadcom_qualcomm_standard', 'business_B'): (True, 'The report explicitly states annual FY2025 combined Automotive/IoT growth of 27% with source citation and reported-result attribution.'), ('ibm_netflix_missing', 'period_scope'): (True, 'The report distinguishes the Q3-letter Q4 forecast from an actual Q4 update, and calendar alignment is supported by the available statements.'), ('adobe_salesforce_standard', 'period_scope'): (True, 'The actual quarter dates correctly distinguish Adobe FY2025 from Salesforce FY2025; the report does not treat the quarters as contemporaneous.'), ('costco_target_missing', 'period_scope'): (False, 'The report calls the Q3 comparison an overlapping Q3 window, but Costco ends May 11 and Target ends November 1, with 12-week/three-month durations; these windows are not overlapping. Elsewhere it correctly notes nonalignment.'), ('costco_target_missing', 'narrative_consistency'): (False, 'Integrated Findings calls the Q3 windows overlapping, while Limitations says the periods are not aligned. Source dates and durations support nonoverlap; the contemporaneous-window description is a material inconsistency.')}
for (tid,key),(passed,reason) in decisions.items():
    rid=tid+'_report_system_1';folder=P/'runs'/rid;report=(folder/'evaluated_report.md').read_text();ledger=read(folder/'evidence_ledger.json');t=tasks[tid]
    selected=[]
    if key=='period_scope' or (tid=='costco_target_missing' and key=='narrative_consistency'):
        for s in ledger:
            text=norm(s['text']);m=re.search(r'Three Months Ended|third quarter \(twelve weeks\)|16-week fourth quarter',text,re.I)
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
    patterns={'period_scope':r'calendar|period.*end|three months', 'business_A':r'74%|8\.2|4\.62|Digital Media', 'business_B':r'27%|fiscal year',
              'cross_source_synthesis':r'larger|growth|compare|unavailable', 'requested_depth':r'^##|unavailable|growth',
              'narrative_consistency':r'overlapping|calendar|period|revenue|growth|net sales|membership|H2 revenue'}
    report_quotes=[l for l in report.splitlines() if re.search(patterns[key],l,re.I)][:12]
    assert selected and report_quotes,(tid,key)
    edits=[e for e in edits if(e['run_id'],e['criterion'])!=(rid,key)]
    edits.append(dict(run_id=rid,criterion=key,passed=passed,reviewer='assistant_source_and_report_adjudication',
                      reason=reason,report_quotes=report_quotes,source_quotes=selected))
(P/'semantic_adjudications.json').write_text(json.dumps(edits,ensure_ascii=False,indent=2)+'\n')
print('Adjudicated',len(decisions),'flagged/misclassified criteria')
