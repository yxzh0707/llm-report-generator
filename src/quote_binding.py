"""Literal quote-to-excerpt binding for explicitly configured report table rows.

Whitespace normalization only; no entailment, date parsing or gold answers.
Unavailable is allowed and remains an incomplete result for evaluation.
"""
import re
from report_validation import normal_label


def validate_quote_config(labels, mode):
    if mode not in {'off','enforce'}:
        raise ValueError('Invalid quote binding mode')
    if not isinstance(labels,list) or len(labels)>20 or any(
            not isinstance(x,str) or not x.strip() or len(x)>120 for x in labels):
        raise ValueError('Quote rows require at most20 nonempty labels')
    if len(set(map(normal_label,labels)))!=len(labels):
        raise ValueError('Duplicate quote row labels')
    if mode=='enforce' and not labels:
        raise ValueError('Quote binding requires explicit row labels')


def normalize(text):
    return re.sub(r'\s+',' ',text).strip()


def validate_quote_bindings(content, sources, labels):
    """Require each available configured row to quote an actually cited excerpt.

    Evidence is the third table cell. Every quoted span must be literally present
    in at least one cited excerpt; candidate citations come only from read text.
    Matching a quote is deliberately not called factual support verification.
    """
    selected={normal_label(x):x for x in labels};rows={k:[] for k in selected}
    for number,line in enumerate(content.splitlines(),1):
        if not line.strip().startswith('|'):continue
        cells=[x.strip() for x in line.strip().strip('|').split('|')]
        if cells and normal_label(cells[0]) in selected:
            rows[normal_label(cells[0])].append((number,cells))
    issues=[];checks=[];by_id={x['citation']:x for x in sources}
    def issue(code,label,**details):
        issues.append({'code':code,'label':label,**details})
    for key,label in selected.items():
        hits=rows[key]
        if len(hits)!=1:
            issue('quote_row_missing_or_duplicate',label,observed_rows=len(hits),
                required_action='Include exactly one requested table row; do not omit an unsupported item. Use Unavailable if evidence is absent.')
            continue
        number,cells=hits[0]
        if len(cells)<3:
            issue('quote_evidence_cell_missing',label,line=number,
                required_action='Provide the requested Item | Value | Evidence table.')
            continue
        if re.fullmatch(r'[*_` ]*(?:Unavailable|N/A)[*_` ]*',cells[1],re.I):
            checks.append({'label':label,'line':number,'status':'abstained','quote_identity_verified':False})
            continue
        evidence=cells[2]
        quotes=[a or b for a,b in re.findall(r'"([^"\n]+)"|“([^”\n]+)”',evidence)]
        citations=re.findall(r'\[S[1-9]\d*\]',evidence)
        if not quotes or any(not 12<=len(normalize(q))<=800 for q in quotes):
            issue('verbatim_quote_required',label,line=number,
                required_action='Include a short supporting verbatim source passage in double quotes in the Evidence cell, followed by its [S#]. Normalize whitespace only; do not invent ellipses or rewrite the passage. Each quote must be12–800characters.')
            continue
        for quote in quotes:
            normalized=normalize(quote)
            candidates=[s['citation'] for s in sources if normalized in normalize(s['text'])]
            matching=[c for c in citations if c in by_id and c in candidates]
            check={'label':label,'line':number,'quote':quote,'cited':citations,
                'matching_cited_excerpts':matching,'quote_identity_verified':bool(matching),
                'factual_entailment_verified':False}
            checks.append(check)
            if not matching:
                issue('quote_excerpt_mismatch',label,line=number,quote=quote,
                    cited=citations,candidate_citations=candidates,
                    required_action='Bind this exact quote to an excerpt that actually contains it. Candidates are from already read text only. If none match, read the needed passage or correct the quotation; do not infer missing content.')
    return {'passed':not issues,'issues':issues,'checks':checks,
        'scope':'Configured table rows: literal quote identity in cited excerpts after whitespace normalization; not value truth or semantic entailment.'}
