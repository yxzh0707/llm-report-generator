"""Source-only repair hints and explicit revenue-basis constraints.

No answer keys, expected values, company lists or study IDs are consulted.
Hints retain surrounding headers because choosing the financial period/column
still requires reading the source. They never silently replace an input.
"""
import re
from fact_grounding import normalized,quoted_numbers
from report_validation import citation_id


def required_revenue_basis(task):
    subjects=[]
    for m in re.finditer(r'\bfor\s+([A-Za-z][A-Za-z0-9 &.-]{0,60}?)\s+include\s+membership fees\b',task,re.I):
        subjects.append(m[1].strip().casefold())
    for m in re.finditer(r'\binclude membership fees in\s+([A-Za-z][A-Za-z0-9 &.-]{0,60}?)\s+revenue\b',task,re.I):
        if not re.search(r'\b(?:not|never)\s*$',task[max(0,m.start()-12):m.start()],re.I):subjects.append(m[1].strip().casefold())
    return subjects


def includes_fees(fact,task):
    label=(fact.get('report_label') or '').casefold()
    return bool(re.search(r'\brevenues?\b',label) and any(re.search(r'\b'+re.escape(s)+r'\b',label) for s in required_revenue_basis(task)))


def validate_requested_basis(facts,task):
    issues=[]
    for f in facts:
        if f.get('value') is None or not includes_fees(f,task):continue
        quote=f.get('source_quote','') or ''
        rows=list(re.finditer(r'\btotal\s+revenues?(?:\s+(?:of|was|were))?\s*[:$]?([\s$()+−\d,.\-]+)',quote,re.I))
        values=set(quoted_numbers(str(f.get('value',''))))
        if not rows or not any(values & set(quoted_numbers(m[1])) for m in rows):
            issues.append(dict(code='requested_revenue_basis',id=f['id'],label=f.get('report_label'),
                required_action='The user explicitly includes membership fees in this company revenue. Use the consolidated Total revenue row, including the fees, rather than the Net sales component. Copy that original row and its unit header; do not change to an easier-to-quote metric.'))
    return issues


def source_candidates(fact,sources,task=''):
    """Find literal candidate rows with column/scale context in cited sources."""
    ids={citation_id(c) for c in fact.get('citations',[])}
    selected=[s for s in sources if s['citation'] in ids]
    values=set(quoted_numbers(str(fact.get('value',''))))
    output=[]
    terms=r'\b(?:total\s+revenues?|revenues?|net\s+sales|membership\s+fees|operating\s+(?:income|profit)|net\s+income)\b'
    for s in selected:
        text=normalized(s.get('text',''));rows=[]
        for m in re.finditer(terms,text,re.I):
            after=text[m.end():m.end()+50]
            # Table rows or disclosed amounts, not discussion of growth rates.
            if not re.match(r'\s*(?:of\s+|was\s+|were\s+)?(?:USD\s*)?\$?\s*[\d(]',after,re.I):continue
            end=text.find(' ',min(len(text),m.start()+350))
            if end<0:end=len(text)
            quote=text[m.start():end]
            prefix=text[max(0,m.start()-500):m.start()]
            scales=list(re.finditer(r'\([^()]{0,70}\b(?:thousands|millions|billions)\b[^()]{0,70}\)',prefix,re.I))
            units=scales[-1][0] if scales else ''
            score=10+int(bool(values & set(quoted_numbers(quote))))*10
            if 'total' in m[0].casefold():score+=5
            if includes_fees(fact,task) and re.match(r'total\s+revenue',m[0],re.I):score+=50
            if 'consolidated' in prefix.casefold():score+=5
            rows.append((score,m.start(),dict(citation=s['citation'],document_id=s.get('document_id'),
                row_start_normalized=m.start(),source_quote=quote,unit_quote=units,
                preceding_context=prefix,note='Copy a contiguous row span, choose the requested period column, and preserve the original unit. Candidate amounts are not automatically selected.')))
        output.extend(r[2] for r in sorted(rows,key=lambda r:(-r[0],r[1]))[:5])
    return output


def repair_context(original_input,request,call,sources):
    return dict(operation='repair_calculation_inputs_from_exact_source_spans',original_user_input=original_input,
        task=request.task,attempted_plan=call['arguments'],validation_feedback=call['result'],
        source_index=[{k:s.get(k) for k in ['citation','document_id','title','source_url']} for s in sources],
        instruction='Repair the complete facts/metrics plan now using the quoted source candidates in the feedback. Keep the requested metric, company and period. If your quote was wrong, locate the correct row; do not substitute a different metric. Table quotes must include intervening columns, not join nonadjacent cells. Copy original numeric tokens without commas, with their original scale; normalization does conversion. Keep valid facts and missing-input disclosures. Call calculate_report_metrics with the repaired complete plan.')
