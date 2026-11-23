"""Bind monetary calculator inputs to literal, already-read source spans.

This verifies quote identity, numeric identity and unit scale. It does not infer
which financial metric or comparative column the user intended.
"""
import re
from decimal import Decimal, InvalidOperation
from calculation_precision import unit_scale
from report_validation import citation_id


def normalized(text):
    return re.sub(r'\s+',' ',text).strip()


def quote_key(text):
    # Typesetting changes quotation marks, not the words, numbers or their order.
    # One-character substitutions preserve offsets in whitespace-normalized text.
    return normalized(text).translate(str.maketrans({'“':'"','”':'"','‘':"'",'’':"'"}))


def original_span(text,quote):
    start=quote_key(text).find(quote_key(quote))
    return normalized(text)[start:start+len(normalized(quote))] if start>=0 else None


def quoted_numbers(text):
    for match in re.finditer(r'(?<![\w.])[+-]?\d[\d,]*(?:\.\d+)?(?![\w]|\.\d)',text):
        value=Decimal(match[0].replace(',',''))
        if text[:match.start()].rstrip().endswith('(') and text[match.end():].lstrip().startswith(')'):
            value=-abs(value)
        yield value


def validate_fact_inputs(facts,sources):
    by_id={s['citation']:s for s in sources};issues=[];checks=[]
    for fact in facts:
        if fact.get('value') is None:continue
        try:currency,scale=unit_scale(fact.get('unit',''))
        except (ValueError,AttributeError):continue
        label=fact.get('report_label') or fact.get('id')
        def fail(code,action):
            issues.append(dict(code=code,id=fact.get('id'),label=label,required_action=action))
        quote=fact.get('source_quote');unit_quote=fact.get('unit_quote','')
        if not isinstance(quote,str) or not 3<=len(quote)<=2400 or not isinstance(unit_quote,str) or len(unit_quote)>800:
            fail('raw_source_quote_required','Supply source_quote copied verbatim from a cited source around the ORIGINAL number. Use its original value and scale, not a rounded or converted estimate. For tables also provide unit_quote copied from the same source header.');continue
        scale_word={0:None,3:'thousand',6:'million',9:'billion',12:'trillion'}[scale]
        scale_pattern=r'\b'+r'\s*'.join(scale_word)+r's?\b' if scale_word else None
        # A separate table header is needed only when the amount passage lacks
        # its scale. Discard redundant header metadata, never cite it as evidence.
        self_contained=not scale_word or bool(re.search(scale_pattern,quote,re.I))
        used_unit_quote='' if self_contained else unit_quote
        matched=[by_id[c] for raw in fact.get('citations',[]) if (c:=citation_id(raw)) in by_id
                 and original_span(by_id[c].get('text',''),quote) is not None
                 and (not used_unit_quote or original_span(by_id[c].get('text',''),used_unit_quote) is not None)]
        if not matched:
            fail('raw_quote_not_in_cited_source','Copy a contiguous source passage, normalizing whitespace only; do not combine nonadjacent rows, invent ellipses, or use another company/quarter citation.');continue
        try:has_value=Decimal(fact['value']) in set(quoted_numbers(quote))
        except (InvalidOperation,TypeError,ValueError):has_value=False
        if not has_value:
            fail('raw_value_not_in_quote','value must equal the original numeric token in source_quote (remove thousands separators only). Do not pre-round or rescale; normalization will convert and round it.');continue
        text=quote+' '+used_unit_quote
        if scale_word and not re.search(scale_pattern,text,re.I):
            fail('raw_unit_not_in_quote','Include the source scale in source_quote or a separate verbatim unit_quote from the same source (e.g. In millions). Set unit to that ORIGINAL scale; the tool performs conversion.');continue
        explicit=re.findall(r'\b(?:USD|EUR|GBP|JPY|CNY|CAD|AUD)\b',text,re.I)
        if explicit and currency not in {x.upper() for x in explicit}:
            fail('raw_currency_conflict','The stated currency conflicts with the cited source passage. Currency exchange is not performed by normalization.');continue
        checks.append(dict(id=fact['id'],raw_value=fact['value'],raw_unit=fact['unit'],
            citations=[s['citation'] for s in matched],source_quote=original_span(matched[0]['text'],quote),
            unit_quote=original_span(matched[0]['text'],used_unit_quote) if used_unit_quote else '',
            submitted_source_quote=quote,submitted_unit_quote=unit_quote,
            quote_match_rule='whitespace and typographic quotation marks only; words/numbers/order unchanged',
            redundant_unit_quote_ignored=bool(unit_quote and self_contained),
            numeric_identity_verified=True,metric_and_column_entailment_verified=False))
    return dict(passed=not issues,issues=issues,checks=checks)
