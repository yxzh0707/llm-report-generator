"""Bounded financial API evidence; execution remains in the enhanced worker."""
import copy
import json
from urllib.parse import urlencode

from provenance import digest

FINANCE_TOOLS = frozenset({'sec_filings', 'sec_company_facts', 'tushare_query', 'alpha_vantage'})
API_TOOLS = FINANCE_TOOLS - {'sec_filings'}


def bounded_arguments(name, arguments, *, sec_fact_limit=12):
    def check(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if any(word in key.lower() for word in ('apikey', 'api_key', 'token', 'secret', 'password')):
                    raise ValueError('Credentials must come from the worker environment')
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)
    check(arguments)
    if type(sec_fact_limit) is not int or not 1 <= sec_fact_limit <= 100:
        raise ValueError('SEC fact limit must be between1and100')
    result = copy.deepcopy(arguments)
    if name in {'sec_filings', 'sec_company_facts'}:
        result['limit'] = max(1, min(int(result.get('limit', 5 if name == 'sec_filings' else sec_fact_limit)),
                                    5 if name == 'sec_filings' else sec_fact_limit))
    return result


def financial_snapshot(name, arguments, value, max_chars=6000):
    """Return valid JSON with complete records, preserving field names and units."""
    if not isinstance(value, dict) or not value or value.get('error'):
        raise ValueError('Financial API returned no usable data')
    if name == 'sec_company_facts' and not value.get('facts'):
        raise ValueError('No company facts')
    if name == 'tushare_query' and not (value.get('fields') and value.get('items')):
        raise ValueError('No tabular records')
    if name == 'alpha_vantage' and any(k in value for k in ('Note', 'Information', 'Error Message')):
        raise ValueError('Provider returned a quota or error notice')
    def has_data(item):
        if isinstance(item, dict):
            return any(has_data(v) for v in item.values())
        if isinstance(item, list):
            return any(has_data(v) for v in item)
        return item is not None and item != ''
    if not has_data(value):
        raise ValueError('Empty financial payload')
    packet = {'tool': name, 'arguments': arguments, 'data': copy.deepcopy(value),
              'projection_truncated': False}
    def encode():
        return json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    # Lists are reduced only at complete-record boundaries. Never truncate
    # Tushare columns or a row. Dictionaries in Alpha Vantage time series may
    # be reduced only at complete date-entry boundaries.
    while len(encode()) > max_chars:
        candidates = []
        def visit(obj, key=''):
            if isinstance(obj, dict):
                if name == 'alpha_vantage' and len(obj) > 1 and all(
                        isinstance(v, dict) and str(k)[:4].isdigit() for k, v in obj.items()):
                    candidates.append(obj)
                for k, v in obj.items():
                    visit(v, k)
            elif isinstance(obj, list) and key in {'facts', 'items', 'annualReports', 'quarterlyReports',
                                                  'annualEarnings', 'quarterlyEarnings'} and len(obj) > 1:
                candidates.append(obj)
        visit(packet['data'])
        if not candidates:
            raise ValueError('Financial record exceeds context limit')
        largest = max(candidates, key=lambda x: len(json.dumps(x)))
        if isinstance(largest, list):
            largest.pop()
        else:
            # Retain most recent date entries irrespective of provider ordering.
            del largest[min(largest)]
        packet['projection_truncated'] = True
    return encode(), packet['projection_truncated']


def source_identity(name, arguments, value):
    if name == 'sec_company_facts':
        cik = str(value['cik']).zfill(10)
        url = f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json'
        title = f"SEC {value.get('entity', cik)} — {arguments['concept']}"
    elif name == 'tushare_query':
        url, title = 'https://api.tushare.pro', 'Tushare — '+arguments['api_name']
    else:
        url = 'https://www.alphavantage.co/query?'+urlencode(
            {'function': arguments['function'], **arguments.get('params', {})})
        title = 'Alpha Vantage — '+arguments['function']
    identity = digest(json.dumps({'tool': name, 'arguments': arguments}, sort_keys=True).encode())
    return url, url+'#query='+identity, 'financial:'+identity, title
