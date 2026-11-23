"""Explicit SEC fact-period selection before context projection.

Filing dates, filing fiscal focus and calendar frames are not fact intervals.
This module does not infer an issuer calendar or resolve accounting concepts.
"""
import copy
import hashlib
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation


def iso_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Expected ISO date')
    return date.fromisoformat(value)


def cik(value):
    if not re.fullmatch(r'\d{1,10}', str(value)) or int(value) == 0:
        raise ValueError('Explicit numeric SEC CIK required')
    return str(int(value))


def validate_financial_scope(scope):
    if scope is None:
        return
    if not isinstance(scope, dict) or set(scope) != {'identifier', 'concept', 'unit', 'as_of', 'periods'}:
        raise ValueError('Invalid financial period scope fields')
    cik(scope['identifier'])
    iso_date(scope['as_of'])
    if not isinstance(scope['concept'], str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,159}', scope['concept']):
        raise ValueError('Explicit SEC concept required')
    if not isinstance(scope['unit'], str) or not scope['unit'] or len(scope['unit']) > 40:
        raise ValueError('Explicit unit required')
    if not isinstance(scope['periods'], list) or not 1 <= len(scope['periods']) <= 12:
        raise ValueError('Between one and twelve explicit fact periods required')
    ids, intervals = set(), set()
    for p in scope['periods']:
        if not isinstance(p, dict) or set(p) not in ({'id', 'end'}, {'id', 'start', 'end'}):
            raise ValueError('Periods require id/end and optional duration start')
        if not isinstance(p['id'], str) or not p['id'].strip() or len(p['id']) > 120 or p['id'] in ids:
            raise ValueError('Unique nonempty period labels required')
        ids.add(p['id'])
        end = iso_date(p['end'])
        if 'start' in p and iso_date(p['start']) > end:
            raise ValueError('Period start exceeds end')
        interval = (p.get('start'), p['end'])
        if interval in intervals:
            raise ValueError('Duplicate fact interval')
        intervals.add(interval)


def select_sec_facts(name, arguments, value, scope):
    """Return original selected rows and a complete, separately persisted audit.

For each requested interval, retain the latest filing available at as_of.
Equal-valued duplicates are collapsed; conflicting values on that latest date
are quarantined rather than summed or resolved by an arbitrary accession.
"""
    validate_financial_scope(scope)
    if scope is None or name != 'sec_company_facts':
        raise ValueError('Explicit SEC company-facts scope required; other APIs unsupported')
    if (cik(arguments.get('identifier', '')) != cik(scope['identifier'])
            or cik(value.get('cik', '')) != cik(scope['identifier'])
            or arguments.get('concept') != scope['concept'] or value.get('concept') != scope['concept']):
        raise ValueError('Financial query/payload does not match scoped issuer and concept')
    rows = value.get('facts')
    if not isinstance(rows, list):
        raise ValueError('SEC facts must be a record list')
    decisions, candidates = [], {p['id']: [] for p in scope['periods']}
    for i, row in enumerate(rows):
        decision = {'record_index': i, 'row_sha256': hashlib.sha256(
            json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            'decision': 'exclude', 'reason': 'period_not_requested'}
        decisions.append(decision)
        if not isinstance(row, dict):
            decision.update(decision='quarantine', reason='invalid_record')
            continue
        if row.get('unit') != scope['unit']:
            decision['reason'] = 'unit_not_requested'
            continue
        try:
            end = iso_date(row.get('end'))
            if row.get('start') is not None and iso_date(row['start']) > end:
                raise ValueError('Reversed interval')
            filed = iso_date(row.get('filed'))
            val = Decimal(str(row.get('val')))
            if isinstance(row.get('val'), bool) or not val.is_finite():
                raise ValueError('Invalid value')
            if not isinstance(row.get('accn'), str) or not row['accn']:
                raise ValueError('Missing accession')
        except (ValueError, TypeError, InvalidOperation):
            decision.update(decision='quarantine', reason='invalid_value_or_provenance')
            continue
        if filed > iso_date(scope['as_of']):
            decision['reason'] = 'filed_after_as_of'
            continue
        for p in scope['periods']:
            if row.get('start') == p.get('start') and row['end'] == p['end']:
                decision.update(period_id=p['id'], reason='eligible_candidate')
                candidates[p['id']].append(i)
                break
    selected, availability = [], []
    for p in scope['periods']:
        indices = candidates[p['id']]
        if not indices:
            availability.append({'period_id': p['id'], 'status': 'unavailable', 'reason': 'no_matching_record_in_returned_candidates'})
            continue
        latest = max(rows[i]['filed'] for i in indices)
        recent = [i for i in indices if rows[i]['filed'] == latest]
        for i in indices:
            decisions[i]['reason'] = 'superseded_as_of' if i not in recent else 'duplicate_same_value'
        if len({Decimal(str(rows[i]['val'])) for i in recent}) > 1:
            for i in recent:
                decisions[i].update(decision='quarantine', reason='conflicting_values_same_latest_date')
            availability.append({'period_id': p['id'], 'status': 'unavailable', 'reason': 'conflicting_values_same_latest_date'})
            continue
        chosen = min(recent, key=lambda i: (rows[i]['accn'], i))
        decisions[chosen].update(decision='keep', reason='latest_available_matching_interval')
        selected.append(copy.deepcopy(rows[chosen]))
        availability.append({'period_id': p['id'], 'status': 'available', 'record_index': chosen})
    audit = {'scope': copy.deepcopy(scope), 'input_records': len(rows), 'selected_records': len(selected),
             'decisions': decisions, 'availability': availability,
             'scope_note': 'Exact fact intervals and unit; latest filing as of cutoff. No calendar inference, concept substitution, arithmetic reconstruction or claim-support certification.'}
    result = {**copy.deepcopy(value), 'facts': selected,
              'period_selection': {'as_of': scope['as_of'], 'requested_periods': scope['periods'],
                                   'availability': availability}}
    return result, audit
