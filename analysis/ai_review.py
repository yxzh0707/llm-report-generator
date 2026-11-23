"""Prepare and validate item-by-item model pre-reviews, separate from human grades.

This module never calls a provider. The explicitly requested Astra/high worker
reads one frozen packet at a time and supplies a draft judgment for validation.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
if __package__:
    from .review_validation import evidence_map, original_proposal
else:
    from review_validation import evidence_map, original_proposal

CRITERIA_ZH = {
    'business scope': '是否实质说明公司的业务范围？',
    'data center/AI strategy': '是否说明数据中心与人工智能业务及其战略？',
    'annual performance with correct period/unit': '是否说明年度业绩，并正确区分财年、期间和数字单位？',
    'principal risks or excerpt gaps': '是否说明主要风险，或明确指出所给证据的缺口？',
    'business/AI strategy': '是否说明主要业务与人工智能战略？',
    'annual performance': '是否实质说明年度业绩？',
    'quarterly performance': '是否实质说明季度业绩，并与全年口径区分？',
    'cross-document synthesis and scope distinction': '是否综合两份文档，并区分报告分部、市场平台及材料范围？',
    'segment scope and principal risks': '是否正确说明分部范围及主要风险？',
    'business scope comparison': '是否实质比较两家公司的业务范围？',
    'data center/AI comparison': '是否实质比较两家公司的数据中心与人工智能业务？',
    'annual and quarterly performance': '是否比较两家公司的年度及季度业绩，并区分期间与口径？',
    'risks and period/segment comparability': '是否说明风险以及财年期间、分部定义的可比性限制？',
    'integration of uploaded and opened web evidence': '是否在正文中综合使用上传文档和打开的网页证据？',
    'requested style/tone and semantic depth': '写作语气和解释深度是否符合请求的风格与深度？',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def prepare(freeze, output=None):
    freeze = Path(freeze).resolve()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = Path(output).resolve() if output else ROOT/'artifacts/model_reviews'/(stamp+'_astra_high')
    if output.exists():
        raise ValueError('Use a new session directory; existing pre-reviews are never replaced')
    frozen = json.loads((freeze/'freeze_manifest.json').read_text())
    for name, expected in frozen['files'].items():
        if sha((freeze/name).read_bytes()) != expected:
            raise ValueError('Frozen input changed: '+name)
    rubric = json.loads((freeze/'rubric.json').read_text())
    ledger = json.loads((ROOT/'artifacts/experiments'/freeze.name/'ledger.json').read_text())
    entries = {e['cell']: e for e in ledger['entries']}
    worksheet = ROOT/'artifacts/tables'/freeze.name/'human_content_worksheet.csv'
    content = list(csv.DictReader(worksheet.open()))
    assert len(content) == 123
    tracked = {str(worksheet.relative_to(ROOT)): sha(worksheet.read_bytes()),
               str((freeze/'rubric.json').relative_to(ROOT)): sha((freeze/'rubric.json').read_bytes())}
    cache = {}

    def packet(cell):
        if cell in cache:
            return dict(cache[cell])
        run = ROOT/'artifacts/runs'/Path(entries[cell]['run_dir']).name
        manifest = json.loads((run/'run_manifest.json').read_text())
        original = (run/'raw_report.md').read_text()
        if sha(original.encode()) != manifest['raw_report_sha256']:
            raise ValueError('Raw report changed: '+cell)
        if manifest['code']['sha256'] != frozen['code_sha256']:
            raise ValueError('Generation version differs from freeze')
        for name in ('raw_report.md','report.md','request.json','evidence_ledger.json','run_manifest.json'):
            path = run/name
            tracked[str(path.relative_to(ROOT))] = sha(path.read_bytes())
        sources = evidence_map(run)
        full = json.loads((run/'evidence_ledger.json').read_text())
        titles = {s['citation']: s.get('title', s['document_id']) for s in full}
        source_list = [{**s, 'title':titles[key]} for key, s in sources.items()]
        cache[cell] = {'cell':cell,'run_id':run.name,
            'run_dir':str(run.relative_to(ROOT)),
            'request':json.loads((run/'request.json').read_text()),
            'raw_report_sha256':sha(original.encode()),
            'raw_report':original,'sources':source_list}
        return dict(cache[cell])

    questions = []
    for selected in rubric['human_source_audit']['preselected']:
        cell = f"{selected['condition']}_r{selected['repetition']}"
        p = packet(cell)
        run = ROOT/p['run_dir']
        review = run/'human_review/review.json'
        tracked[str(review.relative_to(ROOT))] = sha(review.read_bytes())
        proposal = original_proposal(run)
        for item in proposal['items']:
            questions.append({**p, 'kind':'source_support', 'item_id':item['id'],
                'criterion':'supported / contradicted / insufficient',
                'question_zh':'所给证据是否支持下面这条原始事实陈述？',
                'exact_claim':item['exact_claim'], 'original_citation_ids':item['citation_ids']})
    assert len(questions) == 20
    for row in content:
        if row['criterion'] not in CRITERIA_ZH:
            raise ValueError('Unmapped criterion: '+row['criterion'])
        p = packet(row['cell'])
        if p['run_id'] != row['run_id']:
            raise ValueError('Worksheet run identity changed')
        questions.append({**p, 'kind':'content', 'criterion':row['criterion'],
                          'question_zh':CRITERIA_ZH[row['criterion']]})
    for n, question in enumerate(questions, 1):
        question['qid'] = f'Q{n:03d}'
        save(output/'questions'/(question['qid']+'.json'), question)
    manifest = {'purpose':'post_hoc_model_assisted_pre_review',
        'created_at':datetime.now(timezone.utc).isoformat(),
        'judge':{'requested_model':'gpt-6-astra','requested_reasoning_effort':'high',
                 'execution':'explicitly requested collaboration worker; one question at a time'},
        'freeze_id':freeze.name,'freeze_manifest_sha256':sha((freeze/'freeze_manifest.json').read_bytes()),
        'items_planned':len(questions),'source_support_planned':20,'content_planned':123,
        'question_order':[q['qid'] for q in questions],
        'question_sha256':{q['qid']:sha((output/'questions'/(q['qid']+'.json')).read_bytes()) for q in questions},
        'original_artifact_sha256':tracked,
        'budget':{'item_judgments':143,'automatic_rejudgments':0,'serial':True,
                  'new_report_generations':0,'web_requests':0,'embedding_requests':0,
                  'judge_tokens':'not exposed by collaboration tool; unknown',
                  'judge_cost':'not exposed; no claim that Astra uses the free Qwen endpoint'},
        'policy':'All model judgments remain separate from actual human scores. No human gate is satisfied by these outputs.',
        'preparer_sha256':sha(Path(__file__).read_bytes())}
    save(output/'manifest.json',manifest)
    save(output/'progress.json',{'planned':143,'accepted':0,'complete':False})
    print(output)
    return output


def accept(session, draft):
    session = Path(session).resolve()
    result = json.loads(Path(draft).read_text())
    qid = result.get('qid')
    manifest = json.loads((session/'manifest.json').read_text())
    if qid not in manifest['question_order']:
        raise ValueError('Unknown question ID')
    path = session/'questions'/(qid+'.json')
    if sha(path.read_bytes()) != manifest['question_sha256'][qid]:
        raise ValueError('Question changed after preparation')
    question = json.loads(path.read_text())
    target = session/'results'/(qid+'.json')
    if target.exists():
        raise ValueError('A judgment already exists; no automatic rejudgment')
    preceding = manifest['question_order'][:manifest['question_order'].index(qid)]
    if any(not (session/'results'/(prior+'.json')).exists() for prior in preceding):
        raise ValueError('Evaluate one question at a time in the frozen order')
    labels = {'supported','contradicted','insufficient'} if question['kind']=='source_support' else {'satisfied','not_satisfied','uncertain'}
    if result.get('judgment') not in labels:
        raise ValueError('Invalid judgment label')
    for key in ('question_zh','rationale_zh','request_summary_zh'):
        if not isinstance(result.get(key), str) or not result[key].strip():
            raise ValueError('Missing Chinese explanation: '+key)
    if not any('\u4e00' <= c <= '\u9fff' for c in result['rationale_zh']):
        raise ValueError('The rationale must be in Chinese')
    if question['kind']=='source_support':
        if not result.get('claim_zh') or result.get('selection_suitability') not in {'material','less_material'}:
            raise ValueError('Source review requires translation and selection suitability')
    if result.get('confidence') not in {'high','medium','low'}:
        raise ValueError('Confidence must be high, medium or low; not a calibrated accuracy estimate')
    sources = {s['citation']:s for s in question['sources']}
    checked = []
    for evidence in result.get('evidence_checks',[]):
        source = sources.get(evidence.get('source_id'))
        quote = evidence.get('quote_en')
        if not source or not isinstance(quote,str) or not quote or quote not in source['text']:
            raise ValueError('Evidence quote must exactly match the saved returned source')
        if not evidence.get('interpretation_zh'):
            raise ValueError('Evidence translation is required')
        start = source['text'].index(quote)
        checked.append({**evidence,'source_kind':source['source_kind'],
            'document_id':source['document_id'],'source_url':source['source_url'],
            'char_start':source['char_start']+start,'char_end':source['char_start']+start+len(quote),
            'returned_char_start':source['char_start'],'returned_char_end':source['char_end'],
            'excerpt_sha256':source['excerpt_sha256']})
    if question['kind']=='source_support' and result['judgment'] in {'supported','contradicted'} and not checked:
        raise ValueError('Supported or contradicted requires exact evidence')
    report_checks = []
    for reference in result.get('report_checks',[]):
        quote = reference.get('quote_en')
        if not isinstance(quote,str) or not quote or quote not in question['raw_report']:
            raise ValueError('Report quote must exactly match the original report')
        if not reference.get('interpretation_zh'):
            raise ValueError('Report translation is required')
        start=question['raw_report'].index(quote)
        report_checks.append({**reference,'char_start':start,'char_end':start+len(quote),
                              'line':question['raw_report'][:start].count('\n')+1})
    if question['kind']=='content' and result['judgment']=='satisfied' and not report_checks:
        raise ValueError('A positive content judgment requires a saved report quote')
    accepted = {**result,'kind':question['kind'],'cell':question['cell'],'run_id':question['run_id'],
        'criterion':question['criterion'],'evidence_checks':checked,'report_checks':report_checks,
        'judgment_type':'model_assisted_pre_review','actual_human_reviewed':False,
        'judge':manifest['judge'],'input_sha256':manifest['question_sha256'][qid],
        'accepted_at':datetime.now(timezone.utc).isoformat(),
        'validator_sha256':sha(Path(__file__).read_bytes())}
    save(target,accepted)
    count = len(list((session/'results').glob('Q*.json')))
    save(session/'progress.json',{'planned':143,'accepted':count,'complete':count==143,'last_qid':qid})
    print(json.dumps({'accepted':qid,'progress':count,'planned':143}))
    return target


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare');prep.add_argument('--freeze',type=Path,required=True);prep.add_argument('--output',type=Path)
    acc=sub.add_parser('accept');acc.add_argument('--session',type=Path,required=True);acc.add_argument('--draft',type=Path,required=True)
    a=p.parse_args()
    if a.command=='prepare':prepare(a.freeze,a.output)
    else:accept(a.session,a.draft)
