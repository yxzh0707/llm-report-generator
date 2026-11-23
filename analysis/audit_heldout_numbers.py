"""Post-run extraction audit; retain frozen parser results and exact gold.

Apply equally to every report in both arms. Resolve equivalent repeated leading
values, parenthetical label annotations, and explanatory raw-million amounts.
No alternative gold, tolerance, missing policy or generation change is allowed.
"""
import re, sys
from decimal import Decimal
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src'), str(ROOT/'analysis')]
import evaluate_heldout_reports as h
from experiments.system_comparison import read, save, now, sha
P = h.P

def observation(hit, expected, ledger, source_id=None):
    value = re.sub(r'\[S\d+\]', '', hit['value']).strip()
    # The leading declared result is distinct from a parenthetical derivation.
    leading = value.split('(', 1)[0]
    missing = bool(re.match(r'(?:unavailable|not available|not provided|n/?a|cannot calculate)\b', leading, re.I))
    m = re.match(r'\$?\s*([+-]?\d[\d,]*(?:\.\d+)?)', leading)
    amount = m.group(1) if m else None
    cites = re.findall(r'\[S\d+\]', hit['line'])
    grounded = expected is None or source_id is None or bool(cites) and all(c in ledger and ledger[c]['document_id'] == source_id for c in cites)
    unit_ok = not re.search(r'\b(?:million|trillion|thousand)s?\b|\d\s*[mMtT]\b', leading)
    correct = missing if expected is None else bool(amount and not missing and unit_ok and Decimal(amount.replace(',', '')) == Decimal(expected))
    precision = expected is None or bool(amount and re.fullmatch(r'[+-]?\d[\d,]*\.\d{2}', amount))
    return dict(line=hit['line'], leading_result=leading, amount=amount,
                correct=bool(correct), grounded=bool(grounded), precision=bool(precision))

def audit():
    h.configure()
    rows = read(P/'adjudicated_rule_results.json')
    changes = []
    for r in rows:
        folder = P/'runs'/r['run_id']
        text = (folder/'evaluated_report.md').read_text()
        ledger = {s['citation']: s for s in read(folder/'evidence_ledger.json')}
        extracted = h.e.extract_rows(h.e.report_body(text))
        for kind in ('facts', 'derived'):
            for f in r[kind]:
                label = f['label'].casefold()
                hits = [x for x in extracted if x['label'] == label or re.fullmatch(re.escape(label)+r'\s*\([^)]*\)', x['label'])]
                obs = [observation(x, f['value'], ledger, f.get('source_id')) for x in hits]
                passed = bool(obs) and all(o['correct'] and o['grounded'] for o in obs)
                if kind == 'derived':
                    company = next(c for c in r['pair'].split('_') if f['label'].startswith(h.NAMES[c]+' H2'))
                    passed = passed and all(d['source_supported'] for d in r['facts'] if d['id'].startswith(company+'_'))
                key = 'source_supported' if kind == 'facts' else 'supported_calculation'
                original = {k: f.get(k) for k in ('passed', key, 'status', 'display_precision_passed')}
                f[key] = passed
                if kind == 'facts':
                    f['display_precision_passed'] = bool(obs) and all(o['precision'] for o in obs)
                f['extraction_observations'] = obs
                if passed != original[key] or (kind == 'facts' and f['display_precision_passed'] != original['display_precision_passed']):
                    changes.append(dict(run_id=r['run_id'], item=f['label'], kind=kind, before=original,
                        after={key: passed, 'display_precision_passed': f.get('display_precision_passed')}, observations=obs,
                        report_sha256=sha(folder/'evaluated_report.md')))
        r['source_numeric_complete'] = r['delivered'] and all(f['source_supported'] for f in r['facts'])
        r['precision_complete'] = r['delivered'] and all(f['display_precision_passed'] for f in r['facts'])
        for company, growth in zip(r['pair'].split('_'), r['growth']):
            growth['dependencies_correct'] = all(f['source_supported'] for f in r['facts'] if f['id'].startswith(company+'_'))
            growth['passed'] = bool(growth['observations']) and all(o['passed'] for o in growth['observations']) and growth['dependencies_correct']
    save(P/'adjudicated_rule_results.json', rows)
    save(P/'numeric_extraction_audit.json', dict(utc=now(), reports_audited=len(rows), changes=changes,
        scope='Post-hoc parser adjudication of all reports in both arms. Frozen rule_results.json unchanged. Strict original gold values and source requirements retained; no alternate headline values accepted.',
        rule='Compare leading declared values, allow parenthetical label explanations, check units on the leading result rather than raw-input annotations, require every repeated declared result to match.'))
    print({'reports': len(rows), 'changed_item_decisions': len(changes)})

if __name__ == '__main__':
    audit()
