"""Recorded assistant adjudications after reading the flagged reports and sources."""
import json,re
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'artifacts/report_study/system_optimization_07'
def read(p):return json.loads(p.read_text())
def norm(s):return re.sub(r'\s+',' ',s).strip()
edits=read(P/'semantic_adjudications.json');tasks={t['id']:t for t in read(P/'tasks.json')}
decisions={('ibm_netflix_brief', 'period_scope'): (True, 'The actual report states aligned calendar-quarter periods and no offset, supported by the original three-month financial statements.'), ('ibm_netflix_brief', 'narrative_consistency'): (True, 'The narrative revenue scale comparison agrees with the quarterly rows and display-based H2 sums; no investment-quality inference is made.'), ('costco_target_brief', 'narrative_consistency'): (False, 'The report attributes higher revenue to a larger warehouse network, but the supplied releases do not establish this cross-company causal explanation. The comparison mixes warehouse and store networks; supported revenue amounts do not establish that cause.'), ('costco_target_detailed', 'narrative_consistency'): (True, 'The Costco totals include membership fees, Target rows use net sales, and displayed H2 sums and narrative agree. Judge quotations omit source table symbols.'), ('ibm_netflix_detailed', 'narrative_consistency'): (True, 'The revenue and growth-rate comparisons agree with source figures; the report explicitly avoids profitability or investment-quality inference.'), ('ibm_netflix_standard', 'period_scope'): (True, 'Both companies use the same calendar quarter ends and three-month duration; the full source headers support alignment.'), ('ibm_netflix_standard', 'requested_depth'): (True, 'Both requested business topics are explained with evidence, supported revenue/growth comparison and relevant qualifications. The judge combined separate passages with ellipses; full sections substantiate the decision.'), ('broadcom_qualcomm_brief', 'business_A'): (True, 'Q4 AI semiconductor growth of 74% is separated from the $8.2 billion following-quarter forecast, with the corresponding Q4 source.'), ('adobe_salesforce_detailed', 'business_A'): (True, 'Adobe Q4 Digital Media revenue of $4.62 billion and 11% reported/constant-currency growth are correctly stated and cited.'), ('broadcom_qualcomm_detailed', 'business_A'): (True, 'The actual paragraph distinguishes Q4 74% growth from the $8.2 billion Q1 forecast; shortened judge quote retains the relevant meaning.'), ('broadcom_qualcomm_detailed', 'business_B'): (True, 'Qualcomm Automotive/IoT 27% growth is explicitly annual FY2025, with separately labelled quarter and annual figures.'), ('broadcom_qualcomm_detailed', 'cross_source_synthesis'): (True, 'The report connects both company revenue scales and growth drivers while preserving differing periods and investment-quality qualifications. The judge ellipsis combines separate supported passages.'), ('broadcom_qualcomm_standard', 'business_A'): (True, 'The report attributes the Q4 AI growth explanation to management and distinguishes the following-quarter forecast.'), ('broadcom_qualcomm_standard', 'requested_depth'): (True, 'The report develops both business topics and the comparison with sufficient evidence and context for the requested standard depth. The judge calls it detailed, but its actual supported content satisfies the standard criterion.')}
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
    patterns={'period_scope':r'calendar|period.*end|three months', 'business_A':r'74%|8\.2|4\.62|Digital Media', 'business_B':r'27%|fiscal year',
              'cross_source_synthesis':r'larger|growth|compare|unavailable', 'requested_depth':r'^##|unavailable|growth',
              'narrative_consistency':r'calendar|network|revenue|growth|61\.8|61\.97|84\.43|63\.21|86\.16|net sales|membership|H2 revenue'}
    report_quotes=[l for l in report.splitlines() if re.search(patterns[key],l,re.I)][:12]
    assert selected and report_quotes,(tid,key)
    edits=[e for e in edits if(e['run_id'],e['criterion'])!=(rid,key)]
    edits.append(dict(run_id=rid,criterion=key,passed=passed,reviewer='assistant_source_and_report_adjudication',
                      reason=reason,report_quotes=report_quotes,source_quotes=selected))
(P/'semantic_adjudications.json').write_text(json.dumps(edits,ensure_ascii=False,indent=2)+'\n')
print('Adjudicated',len(decisions),'flagged/misclassified criteria')
