"""Small, explicit revision context after a failed deterministic length check."""
import re
from customization import count_report_words,report_body


def section_budgets(content,target):
    body=report_body(content);heads=list(re.finditer(r'^##[ \t]+([^\n]+)',body,re.M))
    sections=[]
    # Preserve table cells and headings; allocate the remaining narrative budget
    # proportionally. This is a planning aid, never a substitute for recounting.
    prefix=body[:heads[0].start()] if heads else body
    fixed=count_report_words(prefix)
    for i,h in enumerate(heads):
        block=body[h.end():heads[i+1].start() if i+1<len(heads) else len(body)]
        table='\n'.join(l for l in block.splitlines() if l.strip().startswith('|'))
        reserve=count_report_words(h[0]+'\n'+table)
        observed=count_report_words(h[0]+block)
        sections.append(dict(section=h[1].strip(),observed_words=observed,reserved_heading_table_words=reserve))
        fixed+=reserve
    available=max(0,(target or 0)-fixed)
    total=sum(max(1,s['observed_words']-s['reserved_heading_table_words']) for s in sections)
    for s in sections:
        s['draft_budget_words']=s['reserved_heading_table_words']+int(available*max(1,s['observed_words']-s['reserved_heading_table_words'])/max(1,total))
    return dict(target_words=target,reserved_words=fixed,sections=sections,
        note='Keep required facts, qualifications, citations and source identities. Shorten narrative and remove repetition; do not delete required sections or truncate sentences. Recount the actual revision.')


def revision_payload(request,original_input,content,measurement,calculations,sources):
    return dict(operation='revise_current_report_to_explicit_word_limit',
        original_user_input=original_input,task=request.task,
        measured_words=measurement['body_words'],maximum_words=measurement['maximum_words'],
        target_words=measurement['draft_target_words'],section_budget=section_budgets(content,measurement['draft_target_words']),
        latest_draft=content,
        calculation_results=[c['result'] for c in calculations if 'error' not in c['result']],
        source_index=[{k:s.get(k) for k in ('citation','title','source_url','document_id')} for s in sources],
        instruction='Rewrite the latest_draft now. Do not submit the same draft again. Retain its supported numbers and qualifiers, all required business topics, meaningful comparison and required headings. Compress prose within the section budgets. Submit the entire revised report with write_file. No new claims or retrieval are needed for this editing step.')
