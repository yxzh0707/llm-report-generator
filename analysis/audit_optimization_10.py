"""Recorded assistant adjudications after reading the flagged reports and sources."""
import json,re
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'artifacts/report_study/system_optimization_10'
def read(p):return json.loads(p.read_text())
def norm(s):return re.sub(r'\s+',' ',s).strip()
edits=read(P/'semantic_adjudications.json');tasks={t['id']:t for t in read(P/'tasks.json')}
decisions={('broadcom_qualcomm_detailed', 'period_scope'): (False, 'Integrated Findings describes Q4 Automotive +17% and IoT +7% as quarter-over-quarter momentum; the Q4 release table compares FY2025 Q4 with FY2024 Q4. These are year-over-year changes, correctly described earlier but contradicted in the synthesis.'), ('broadcom_qualcomm_detailed', 'business_B'): (False, 'The requested Automotive/IoT topic includes an incorrect comparison period in Integrated Findings: +17%/+7% are called quarter-over-quarter, although source and detailed section identify year-over-year. The annual 27% figure itself is correct.'), ('broadcom_qualcomm_detailed', 'narrative_consistency'): (False, 'Integrated Findings changes the basis of Automotive/IoT growth from year-over-year to quarter-over-quarter, contradicting the detailed analysis and original QCT table.'), ('costco_target_brief', 'narrative_consistency'): (True, 'Requested revenue rows and H2 sums agree with sources. Digital metrics retain their different definitions; no profitability inference is drawn.'), ('costco_target_standard', 'period_scope'): (True, 'The report correctly preserves 12/16-week Costco quarters, three-month Target quarters, and 174/153-day offsets from the source end dates.'), ('costco_target_standard', 'narrative_consistency'): (False, 'Executive Summary says Costco revenue is roughly 2.5x Target in each quarter, whereas Detailed Analysis correctly gives Q4 about 2.8x. The displayed Q4 amounts yield 2.8296, so the summary understates that comparative ratio and conflicts with the detailed comparison.'), ('costco_target_detailed', 'period_scope'): (True, 'Reported durations and end dates establish nonalignment; exact 174/153-day gaps agree with the original periods. Annual versus quarterly comparable-sales figures are separately labelled.'), ('costco_target_detailed', 'requested_depth'): (True, 'The detailed report develops both requested business topics, original table inputs, reported versus adjusted figures, and qualified cross-company comparisons with source evidence.'), ('costco_target_detailed', 'narrative_consistency'): (True, 'Narrative quarterly amounts and H2 sums match the displayed rows. The approximately 2.7 H2 scale ratio is supported and is not treated as profitability superiority.'), ('ibm_netflix_brief', 'period_scope'): (True, 'Both issuers report aligned calendar quarters ending September 30 and December 31; the report correctly states this.'), ('ibm_netflix_standard', 'period_scope'): (True, 'Summary, detailed dates and conclusion consistently describe aligned three-month calendar quarters, supported by all four statements.'), ('ibm_netflix_standard', 'narrative_consistency'): (False, 'Report calls IBM 61.8% an operating (non-GAAP) margin, but the original release places Operating (Non-GAAP): 61.8 percent under Gross Profit Margin. Dropping gross changes the metric and makes the profitability context misleading.'), ('ibm_netflix_detailed', 'period_scope'): (True, 'The report correctly distinguishes calendar-aligned quarters from differing business models, and labels annual results and 2026 forecasts.'), ('costco_target_missing', 'period_scope'): (False, 'Executive Summary calls the Q3 periods overlapping. Costco ends May 11 with a 12-week duration and Target ends November 1 with a three-month duration; these windows do not overlap.'), ('costco_target_missing', 'narrative_consistency'): (False, 'The summary asserts overlapping Q3 periods while the source end dates and durations establish disjoint windows. Required financial values and missing-topic disclosure are nevertheless correct.')}
for (tid,key),(passed,reason) in decisions.items():
    rid=tid+'_report_system_1';folder=P/'runs'/rid;report=(folder/'evaluated_report.md').read_text();ledger=read(folder/'evidence_ledger.json');t=tasks[tid]
    selected=[]
    if key=='period_scope' or (tid in ['ibm_netflix_standard','costco_target_missing'] and key=='narrative_consistency'):
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
    if tid=='broadcom_qualcomm_detailed' and key in ['business_B','period_scope','narrative_consistency']:
        source=next(s for s in ledger if s['document_id']=='qualcomm_q4');t=norm(source['text']);i=t.find('QCT Revenue Streams1');assert i>=0;selected.append(dict(citation=source['citation'],quote=t[i:i+480]))
        report_quotes += [l for l in report.splitlines() if 'more modest quarter-over-quarter momentum' in l]
    assert selected and report_quotes,(tid,key)
    edits=[e for e in edits if(e['run_id'],e['criterion'])!=(rid,key)]
    edits.append(dict(run_id=rid,criterion=key,passed=passed,reviewer='assistant_source_and_report_adjudication',
                      reason=reason,report_quotes=report_quotes,source_quotes=selected))
(P/'semantic_adjudications.json').write_text(json.dumps(edits,ensure_ascii=False,indent=2)+'\n')
print('Adjudicated',len(decisions),'flagged/misclassified criteria')
