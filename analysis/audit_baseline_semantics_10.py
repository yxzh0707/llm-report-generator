"""Apply the same observed semantic-error checks to frozen Hermes reports.
Original generations, judge outputs and earlier study adjudications stay unchanged.
"""
import json,re
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'artifacts/report_study/system_optimization_10'
def read(p):return json.loads(p.read_text())
def norm(s):return re.sub(r'\s+',' ',s).strip()
edits=read(P/'semantic_adjudications.json');changes=[]
decisions={
 ('adobe_salesforce_brief','period_scope'):('offset by roughly two months','The same-FY2025 Q3/Q4 end dates are 302/301 days apart; a roughly two-month offset mischaracterizes the requested periods.'),
 ('adobe_salesforce_brief','narrative_consistency'):('offset by roughly two months','The asserted two-month timing offset is not supported by the actual same-FY quarter dates, which are approximately ten months apart.'),
 ('adobe_salesforce_standard','period_scope'):('overlap only partially','The report calls the second halves partially overlapping, but Adobe June-November 2025 and Salesforce August 2024-January 2025 are disjoint. It also uses Q4 windows as half-year windows.'),
 ('adobe_salesforce_standard','narrative_consistency'):('overlap only partially','Calendar comparison says the periods overlap although the dates stated in the same paragraph establish nonoverlap.'),
 ('broadcom_qualcomm_detailed','narrative_consistency'):('62% of QCT','The source table reports FY2025 handset revenue 27,793 and total QCT 38,367 million: handset share is about 72.44%, not 62%. The stated percentage appears to use consolidated revenue as denominator while labelling it QCT.'),
 ('costco_target_brief','narrative_consistency'):('2.4x','The stated H2 ratio 2.4x contradicts the displayed 149.37 and 55.72, whose ratio is about 2.68x. The same summary-ratio consistency standard is used for the system report.'),
 ('ibm_netflix_detailed','narrative_consistency'):('61.8','IBM labels 61.8 percent as Operating (Non-GAAP) under Gross Profit Margin. Calling it operating (non-GAAP) margin drops gross and changes the measure, as in the system report.')}
for (task,key),(needle,reason) in decisions.items():
 rid=task+'_hermes_agent_1';f=P/'runs'/rid;report=(f/'evaluated_report.md').read_text();ledger=read(f/'evidence_ledger.json')
 quotes=[l for l in report.splitlines() if needle in l];assert quotes
 sources=[]
 for s in ledger:
  t=norm(s['text'])
  if task.startswith('adobe'):
   for m in list(re.finditer(r'Three Months Ended|quarter ended|October 31, 2024|November 28, 2025',t,re.I))[:2]:sources.append(dict(citation=s['citation'],quote=t[max(0,m.start()-60):m.end()+200]))
  elif task.startswith('broadcom') and s['document_id']=='qualcomm_q4':
   i=t.find('QCT Revenue Streams1');assert i>=0;sources.append(dict(citation=s['citation'],quote=t[i:i+480]))
  elif task.startswith('ibm') and s['document_id']=='ibm_q4':
   i=t.find('61.8');assert i>=0;sources.append(dict(citation=s['citation'],quote=t[i-110:i+75]))
  elif task.startswith('costco'):
   m=re.search(r'Total revenue|Net sales',t,re.I)
   if m:sources.append(dict(citation=s['citation'],quote=t[max(0,m.start()-50):m.end()+150]))
 assert sources
 before=next((e for e in edits if (e['run_id'],e['criterion'])==(rid,key)),None)
 row=dict(run_id=rid,criterion=key,passed=False,reviewer='assistant_symmetric_source_audit',reason=reason,report_quotes=quotes,source_quotes=sources)
 edits=[e for e in edits if(e['run_id'],e['criterion'])!=(rid,key)]+[row];changes.append(dict(prior_adjudication=before,new_adjudication=row))
(P/'semantic_adjudications.json').write_text(json.dumps(edits,ensure_ascii=False,indent=2)+'\n')
(P/'symmetric_source_audit.json').write_text(json.dumps(dict(scope='Same frozen reports and unchanged rubric; supplementary source review of timing, metric labels and comparative ratios in both arms. Earlier studies and raw judge responses untouched. Core numeric/format baseline scores unchanged.',baseline_changes=changes,system_audit='analysis_code/audit_optimization_10.py'),ensure_ascii=False,indent=2)+'\n')
print('Baseline additional source decisions:',len(changes))
