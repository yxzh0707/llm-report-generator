"""Record assistant source-audit decisions separately from frozen model scores."""
import json,re
from pathlib import Path
P=Path('artifacts/report_study/system_comparison_02')
read=lambda p:json.loads(p.read_text())
edits=read(P/'semantic_adjudications.json');done={(e['run_id'],e['criterion']) for e in edits}
def para(text,needle):
 hits=[x for x in text.split('\n\n') if needle in x]
 assert hits,needle
 return hits[0]
def section(text,needle):
 i=text.index(needle); start=text.rfind('\n## ',0,i);end=text.find('\n## ',i)
 return text[max(0,start):end if end>=0 else len(text)].strip()
def block(text,needle,before=150,after=150):
 i=text.index(needle);return text[max(0,i-before):i+len(needle)+after]
# Replacements for non-contiguous/paraphrased report quotations, reviewed in actual reports.
report_needles={
 ('broadcom_qualcomm_brief_general_agent_1','business_A'):['Separately, a forecast'],
 ('broadcom_qualcomm_standard_general_agent_1','narrative_consistency'):['The sources do **not** support any inference'],
 ('broadcom_qualcomm_standard_general_agent_2','business_A'):['The same release contains a **forecast**'],
 ('broadcom_qualcomm_standard_report_system_2','period_scope'):['**Broadcom** uses a fiscal year','**Qualcomm** uses a fiscal year'],
 ('broadcom_qualcomm_detailed_general_agent_1','requested_depth'):['Its Q4 release attributes','Its Q4 release highlights'],
 ('broadcom_qualcomm_detailed_report_system_1','business_A'):['The same release contains a forward-looking statement'],
 ('broadcom_qualcomm_detailed_report_system_1','cross_source_synthesis'):["Broadcom's FY2025 second half", "Qualcomm's FY2025 second half"],
 ('broadcom_qualcomm_detailed_report_system_2','cross_source_synthesis'):['The revenue scale difference'],
 ('broadcom_qualcomm_missing_general_agent_1','business_A'):['Forecast: Q1 FY2026'],
 ('costco_target_standard_general_agent_1','narrative_consistency'):['**Costco H2 revenue** ='],
 ('costco_target_detailed_general_agent_2','cross_source_synthesis'):['The metrics are not directly comparable'],
 ('costco_target_missing_report_system_2','requested_depth'):['**Costco Q4 (result):**'],
 ('ibm_netflix_standard_general_agent_1','cross_source_synthesis'):["each company's own results"],
 ('ibm_netflix_standard_general_agent_1','requested_depth'):["each company's own results"],
 ('ibm_netflix_standard_general_agent_2','period_scope'):['**no fiscal-calendar or duration difference**'],
 ('ibm_netflix_standard_report_system_2','requested_depth'):["Netflix's Q4 2025 release attributes"],
}
for u in read(P/'final_summary.json')['unresolved_items']:
 name,key=u['run_id'],u['criterion']; assert(name,key) not in done
 j=read(P/'judge'/name/'validated.json');row=next(x for x in j['results'] if x['id']==key)
 report=(P/'runs'/name/'evaluated_report.md').read_text();ledger={x['citation']:x for x in read(P/'runs'/name/'evidence_ledger.json')}
 evidence=[];quotes=[]
 for f in j['quote_flags']:
  if f['criterion']!=key or f['kind']!='source_quote':continue
  q=f['quote']; s=ledger[q['citation']]['text'];id=ledger[q['citation']]['document_id'];v=q['quote']
  if id.startswith('target_') and 'Net sales' in v: replacement=block(s,'25,270' if id.endswith('q3') else '30,453',220,100)
  elif id.startswith('ibm_') and 'Three Months' in v: replacement=block(s,'Three Months Ended',0,180)
  elif id.startswith('netflix_') and 'Three Months' in v:
   marker='2025'; ix=s.find('Three\tMonths\tEnded'); replacement=s[ix:ix+420]
   assert ix>=0 and marker in replacement
  elif id.startswith('netflix_') and v.startswith('Revenue $'): replacement=block(s,"(in  millions  except  per  share  data)",0,340)
  elif id=='qualcomm_q4' and '27%' in v:replacement=block(s,'Combined QCT Automotive and IoT Fiscal Year Revenues Grew 27%',0,90)
  elif id=='netflix_q3' and ('growth' in v or 'grew' in v):
   # Supplied letter paragraph, not the judge's invented wording.
   ix=s.find('In  Q4’25'); replacement=s[ix:ix+350];assert ix>=0
  else:
   # For ordinary spacing/markup differences, keep verified actual contiguous token span.
   from normalize_system_judge_quotes import actual_quote
   replacement=actual_quote(v,s)
   assert replacement,(name,key,id,v)
  assert replacement in s
  evidence.append({'citation':q['citation'],'document_id':id,'actual_verbatim_span':replacement})
 for needle in report_needles.get((name,key),[]): quotes.append(para(report,needle))
 # Also retain judge's report quotes that are truly present.
 for q in row['report_quotes']:
  if re.sub(r'\s+',' ',q).strip() in re.sub(r'\s+',' ',report).strip():quotes.append(q)
 passed=row['passed'];reason='Assistant checked the flagged passage against the original report and supplied quarter release. The issue is quotation extraction/paragraph layout, not the criterion judgment. Actual source/table context and report passages are retained; other arithmetic and precision checks remain separate.'
 if name=='ibm_netflix_missing_general_agent_2' and key=='narrative_consistency':
  passed=False;quotes=[para(report,'IBM reported higher quarterly revenue')];reason='The executive summary claims IBM exceeded Netflix in BOTH Q3 and Q4, whereas the table and limitations correctly mark Netflix Q4 unavailable. This is a material unsupported Q4 comparison and a narrative/table contradiction.'
 if name.startswith('costco') and 'general_agent' in name and key=='narrative_consistency':
  reason='Verified actual Target table rows and the report. Retain the narrow narrative/table consistency judgment: both report the same H2 value. The judge reason claiming arithmetic correctness is rejected; 63.21+86.16 should be149.37, not149.36. This calculation error is separately failed in deterministic derived scoring.'
 edits.append(dict(run_id=name,criterion=key,passed=passed,reviewer='assistant_source_audit',report_quotes=quotes,source_context=evidence,reason=reason))
# Apply the same date-consistency review to both arms, including unflagged judgments.
for f in (P/'runs').glob('*/evaluated_report.md'):
 t=f.read_text();n=f.parent.name
 if 'roughly one quarter' in t or '13-month fiscal year' in t:
  quotes=[x for x in t.split('\n\n') if 'roughly one quarter' in x or '13-month fiscal year' in x]
  reason='The report states correct quarter-end dates elsewhere but misstates their offset. Broadcom/Qualcomm ends differ by35days, not approximately one quarter; Adobe FY2025 Q4 ends Nov28,2025 vs Salesforce Jan31,2025, about10months. The13-month fiscal-year assertion is unsupported. Period comparability criterion fails.'
  edits=[e for e in edits if(e['run_id'],e['criterion'])!=(n,'period_scope')]
  edits.append(dict(run_id=n,criterion='period_scope',passed=False,reviewer='assistant_source_audit',report_quotes=quotes,reason=reason))
n='ibm_netflix_missing_general_agent_2';t=(P/'runs'/n/'evaluated_report.md').read_text()
edits=[e for e in edits if(e['run_id'],e['criterion'])!=(n,'cross_source_synthesis')]
edits.append(dict(run_id=n,criterion='cross_source_synthesis',passed=False,reviewer='assistant_source_audit',report_quote=para(t,'IBM reported higher quarterly revenue'),reason='The main comparative summary asserts a Q4 revenue ordering despite missing NetflixQ4. It does not constrain the comparison to available evidence as required by the frozen criterion.'))
assert len(edits)==len({(e['run_id'],e['criterion']) for e in edits})
(P/'semantic_adjudications.json').write_text(json.dumps(edits,ensure_ascii=False,indent=2)+'\n');print('Recorded',len(edits),'criterion adjudications')
