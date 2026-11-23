"""Deterministic formatting checks; factual support needs a separate review."""
import re


def check_report(report, package, finish_reason):
    # Ignore code blocks: example headings/citations do not count as report content.
    text = re.sub(r'^```[^\n]*\n.*?^```[^\n]*$', '', report, flags=re.M | re.S)
    headings = re.findall(r'^(#{1,6})[ \t]+([^\n]+?)\s*$', text, re.M)
    required = package['required_headings']
    matches = [(level, title) for level, title in headings if title in required]
    body = re.split(r'^#{1,2}[ \t]+Sources[ \t]*$', text, maxsplit=1, flags=re.M)[0]
    cited = set(re.findall(r'\[S\d+\]', body))
    known = {s['citation'] for s in package['sources']}
    missing = [h for h in required if not any(t == h for _, t in matches)]
    wrong_level = [t for level, t in matches if level != '##']
    duplicate = [h for h in required if sum(t == h for _, t in matches) > 1]
    order_ok = [t for _, t in matches] == required
    result = dict(missing_headings=missing, wrong_heading_levels=wrong_level,
                  duplicate_headings=duplicate, section_order_correct=order_ok,
                  unknown_citations=sorted(cited-known), has_body_citations=bool(cited),
                  body_cited_documents=sorted({s['document_id'] for s in package['sources']
                                               if s['citation'] in cited}),
                  finish_reason=finish_reason, factual_support_review='pending_manual_review')
    result['mechanical_checks_passed'] = (not missing and not wrong_level and not duplicate
        and order_ok and not (cited-known) and bool(cited) and finish_reason == 'stop')
    return result
