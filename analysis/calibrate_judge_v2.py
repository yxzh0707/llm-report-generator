"""New-role calibration pilot. Preserves historical experiments and raw responses."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
from experiments.closure_evaluation import calibration, validate, JUDGE_SYSTEM
from llm_adapter import chat_completion
from runtime_config import load_project_environment, provider_settings
from provenance import write_json, snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=False)
    load_project_environment(role='judge')
    settings = provider_settings(role='judge')
    cases = calibration()
    # Remove an ambiguous "substantively discuss" label before running any call.
    # The positive fixture names the risks but does not explain their mechanisms.
    for case in cases:
        if case['case'] == 'risks':
            question = "Does the report identify both competition and export restrictions as principal business risks, consistent with the source?"
            case['packet']['request']['task'] = question
            case['packet']['questions'][0]['question'] = question
    protocol = {'version': 'judge-role-calibration-v2', 'provider': settings,
        'scope': '12-case pilot; one call per fixture, no retries; not a full benchmark or proof of general reliability',
        'gate': 'All six negative cases NO and at least five of six positive cases YES; otherwise diagnostic only.',
        'temperature': 0, 'max_tokens': 2000,
        'fixture_change': 'Risk question explicitly asks for identification, matching the positive fixture; historical fixtures unchanged.',
        'cases': cases, 'system': JUDGE_SYSTEM,
        'source_snapshot': snapshot(ROOT, ROOT/'artifacts/versions/project')}
    write_json(out/'protocol.json', protocol)
    protocol_hash = hashlib.sha256((out/'protocol.json').read_bytes()).hexdigest()
    results = []
    for index, case in enumerate(cases):
        started = time.monotonic()
        record = {'case': case['case'], 'expected': case['expected']}
        try:
            response = chat_completion(role='judge', system=JUDGE_SYSTEM,
                user=json.dumps(case['packet'], ensure_ascii=False), temperature=0, max_tokens=2000)
            write_json(out/f'{index:02d}_response.json', response)
            choice = response['choices'][0]
            items = validate(choice['message'].get('content') or '', case['packet']) if choice.get('finish_reason') == 'stop' else [{'label':'INVALID','error':'unfinished_response'}]
            record.update(label=items[0]['label'], items=items, response_model=response.get('model'),
                          finish_reason=choice.get('finish_reason'), usage=response.get('usage'))
        except Exception as exc:
            record.update(label='INVALID', error_type=type(exc).__name__)
        record['elapsed_seconds'] = round(time.monotonic()-started, 3)
        results.append(record)
        write_json(out/'results.json', results)
        print(json.dumps({k:record[k] for k in ('case','expected','label')},ensure_ascii=False), flush=True)
    negatives = sum(r['expected']=='NO' and r['label']=='NO' for r in results)
    positives = sum(r['expected']=='YES' and r['label']=='YES' for r in results)
    assert hashlib.sha256((out/'protocol.json').read_bytes()).hexdigest() == protocol_hash
    write_json(out/'summary.json', {'provider':settings, 'negative_correct':negatives, 'negative_total':6,
        'positive_correct':positives, 'positive_total':6, 'labels':dict(Counter(r['label'] for r in results)),
        'pilot_gate_passed': negatives==6 and positives>=5, 'protocol_sha256':protocol_hash,
        'limitation':'Small one-repeat calibration pilot; expanded controls and source-level spot review remain necessary.'})


if __name__ == '__main__':
    main()
