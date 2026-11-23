"""Recorded assistant adjudications after reading the flagged reports and sources."""
import json,re
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'artifacts/report_study/system_optimization_05'
def read(p):return json.loads(p.read_text())
def norm(s):return re.sub(r'\s+',' ',s).strip()
edits=read(P/'semantic_adjudications.json');tasks={t['id']:t for t in read(P/'tasks.json')}
decisions={
 ('broadcom_qualcomm_standard','business_A'):(True,'The report separates Q4 AI revenue growth of 74% from the following-quarter $8.2 billion forecast; the flagged quote is a shortened form of the paragraph.'),
 ('broadcom_qualcomm_detailed','business_B'):(True,'The report explicitly attributes 27% Automotive/IoT growth to the full fiscal year, with Q4 and annual detail separately labelled.'),
 ('broadcom_qualcomm_detailed','cross_source_synthesis'):(True,'Both company growth explanations and revenue scale are connected, with the different periods and profitability limits preserved.'),
 ('costco_target_brief','narrative_consistency'):(False,'The report calls Costco 61.97/84.43 consolidated revenue including fees, but those amounts are net sales alone. Total revenue is 63,205/86,156 million. The source passages contradict the stated metric definition.'),
 ('costco_target_standard','narrative_consistency'):(False,'The executive summary and table use net sales 61.97/84.43 as revenue including fees, while the same report later correctly states total revenue 63,205/86,156 million. This is a material internal contradiction.'),
 ('costco_target_detailed','cross_source_synthesis'):(True,'Comparison connects revenue scale and disclosed growth, preserves differing definitions and durations, and does not rank investment quality. Target source Net sales rows include a dollar symbol omitted by the judge.'),
 ('costco_target_detailed','narrative_consistency'):(True,'Displayed consolidated revenue and display-based H2 sums agree with the original rows. The flagged Target quotes omit the dollar symbol; the underlying amounts match.'),
 ('ibm_netflix_brief','period_scope'):(True,'Both companies use aligned calendar quarters; the report does not invent an offset. The Netflix statement header and date are separated by other column headings, so the judge short quote is not contiguous.'),
 ('ibm_netflix_standard','period_scope'):(True,'Both supplied Q3 statements end September 30, 2025 and both Q4 statements end December 31, 2025. Header/date passages support calendar alignment despite the noncontiguous judge quote.'),
 ('ibm_netflix_standard','narrative_consistency'):(False,'The report labels IBM 61.8% as operating (non-GAAP) margin and contrasts gross versus operating margin. In the source this is operating (non-GAAP) gross profit margin; treating it as an operating-profit margin materially mislabels the measure.'),
 ('ibm_netflix_detailed','period_scope'):(True,'The supplied three-month financial statements show identical quarter end dates; annual figures and forecasts are distinguished. The judge combined a header and date across intervening column headings.'),
 ('ibm_netflix_missing','cross_source_synthesis'):(True,'Comparison connects available revenue scale and company growth explanations, explicitly limiting Netflix Q4/H2 because the required release is absent. Numeric-row errors are assessed separately.'),
 ('ibm_netflix_missing','requested_depth'):(True,'The brief report includes requested tables, IBM growth contributors, missing Netflix Q4 disclosure, comparison and limitations. Judge paraphrase is not a verbatim span but the discussed sections are present.'),
}
for (tid,key),(passed,reason) in decisions.items():
    rid=tid+'_report_system_1';folder=P/'runs'/rid;report=(folder/'evaluated_report.md').read_text();ledger=read(folder/'evidence_ledger.json');t=tasks[tid]
    selected=[]
    if key=='period_scope':
        for s in ledger:
            text=norm(s['text']);m=re.search(r'Three Months Ended',text,re.I)
            if m:selected.append(dict(citation=s['citation'],quote=text[max(0,m.start()-70):m.end()+300]))
    elif key=='narrative_consistency' and tid=='ibm_netflix_standard':
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
              'narrative_consistency':r'61\.8|61\.97|84\.43|63\.21|86\.16|net sales|membership|H2 revenue'}
    report_quotes=[l for l in report.splitlines() if re.search(patterns[key],l,re.I)][:12]
    assert selected and report_quotes,(tid,key)
    edits=[e for e in edits if(e['run_id'],e['criterion'])!=(rid,key)]
    edits.append(dict(run_id=rid,criterion=key,passed=passed,reviewer='assistant_source_and_report_adjudication',
                      reason=reason,report_quotes=report_quotes,source_quotes=selected))
(P/'semantic_adjudications.json').write_text(json.dumps(edits,ensure_ascii=False,indent=2)+'\n')
print('Adjudicated',len(decisions),'flagged/misclassified criteria')
