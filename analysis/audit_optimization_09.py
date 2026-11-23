"""Recorded assistant adjudications after reading the flagged reports and sources."""
import json,re
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'artifacts/report_study/system_optimization_09'
def read(p):return json.loads(p.read_text())
def norm(s):return re.sub(r'\s+',' ',s).strip()
edits=read(P/'semantic_adjudications.json');tasks={t['id']:t for t in read(P/'tasks.json')}
decisions={('adobe_salesforce_standard', 'business_A'): (True, 'Q4 Digital Media revenue $4.62 billion and 11% growth are source-backed reported results; the report separates annual context and forecasts.'), ('broadcom_qualcomm_detailed', 'business_B'): (True, 'The 27% Automotive/IoT claim explicitly refers to fiscal-year growth, with Q4-only figures separately identified.'), ('broadcom_qualcomm_detailed', 'requested_depth'): (True, 'Both topics receive source-backed context, quarterly versus annual distinctions, and a qualified cross-company comparison.'), ('broadcom_qualcomm_missing', 'business_A'): (True, 'Broadcom Q4 74% AI growth is reported separately from its $8.2 billion Q1 forecast; judge paraphrases billions as B.'), ('costco_target_brief', 'narrative_consistency'): (True, 'Requested revenue rows, H2 sums and digital-growth comparison agree; no unsupported profitability ranking.'), ('costco_target_standard', 'cross_source_synthesis'): (True, 'The report connects growth direction and digital metrics across both companies while explicitly distinguishing metric definitions.'), ('costco_target_standard', 'narrative_consistency'): (True, 'Revenue amounts and H2 sums agree. Rough scale language does not change the comparison or infer profitability; exact amounts remain visible.'), ('ibm_netflix_brief', 'period_scope'): (True, 'Original statements show aligned three-month calendar quarters, correctly described in the report.'), ('ibm_netflix_standard', 'cross_source_synthesis'): (True, 'The report provides a supported revenue-scale and business-driver comparison; it does not rank investment quality.'), ('ibm_netflix_standard', 'period_scope'): (False, 'Executive Summary says fiscal calendars and quarter-end dates differ, contradicting the aligned dates correctly shown later and in the original statements.'), ('ibm_netflix_standard', 'narrative_consistency'): (False, 'Executive Summary contradicts the later calendar-alignment conclusion. The report also calls 61.8% an operating margin, although IBM labels it Operating (Non-GAAP) under Gross Profit Margin.'), ('ibm_netflix_detailed', 'period_scope'): (True, 'Original statements show aligned calendar quarter ends; the judge source quotations combine table headers and date columns.'), ('ibm_netflix_missing', 'period_scope'): (True, 'Calendar alignment is supported by the available statements; Netflix Q4 management explanation is explicitly unavailable and the Q3-letter Q4 forecast is distinguished.'), ('adobe_salesforce_detailed', 'period_scope'): (False, 'Report says both companies use 13-week quarters, which supplied Salesforce statements do not establish; Salesforce Oct 31 to Jan 31 is 92 days, unlike Adobe Aug 29 to Nov 28 (91). Dates are correct but the precise duration claim is unsupported.')}
for (tid,key),(passed,reason) in decisions.items():
    rid=tid+'_report_system_1';folder=P/'runs'/rid;report=(folder/'evaluated_report.md').read_text();ledger=read(folder/'evidence_ledger.json');t=tasks[tid]
    selected=[]
    if key=='period_scope' or (tid=='ibm_netflix_standard' and key=='narrative_consistency'):
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
    report_quotes=[l for l in report.splitlines() if re.search(patterns[key]+r'|61\.8|13-week',l,re.I)][:20]
    if tid=='ibm_netflix_standard' and key=='narrative_consistency':
        source=next(s for s in ledger if s['document_id']=='ibm_q4');t=norm(source['text']);i=t.find('61.8');selected.append(dict(citation=source['citation'],quote=t[i-110:i+75]))
    assert selected and report_quotes,(tid,key)
    edits=[e for e in edits if(e['run_id'],e['criterion'])!=(rid,key)]
    edits.append(dict(run_id=rid,criterion=key,passed=passed,reviewer='assistant_source_and_report_adjudication',
                      reason=reason,report_quotes=report_quotes,source_quotes=selected))
(P/'semantic_adjudications.json').write_text(json.dumps(edits,ensure_ascii=False,indent=2)+'\n')
print('Adjudicated',len(decisions),'flagged/misclassified criteria')
