"""Import explicit human confirmations (browser export or recorded chat statement).

Defaults to a dry run. Every answer is bound to its frozen question, pre-review
and original report. Model grades alone cannot enter. Chat origin is recorded
without implying browser clicks. Existing human answers are never silently replaced.
"""
import argparse
import copy
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
if __package__:
    from .review_validation import validate_review
else:
    from review_validation import validate_review

ROOT=Path(__file__).resolve().parents[1]
REVIEW_METADATA=('review_method','confirmation_origin','confirmation_record_sha256',
                 'model_review_qid','model_result_sha256')
def sha(data):return hashlib.sha256(data).hexdigest()


def import_confirmations(session,export,*,apply=False,root=ROOT):
    root,session,export=Path(root).resolve(),Path(session).resolve(),Path(export).resolve()
    m=json.loads((session/'manifest.json').read_text());data=json.loads(export.read_text())
    if (data.get('schema')!='actual-human-review-confirmations-v1' or data.get('session')!=session.name
            or data.get('freeze_id')!=m['freeze_id'] or data.get('manifest_sha256')!=sha((session/'manifest.json').read_bytes())):
        raise ValueError('Human export session/freeze/manifest mismatch')
    answers=data.get('answers')
    if not isinstance(answers,list):raise ValueError('answers must be a list')
    reviews={};content=[];seen=set();uncertain=[]
    for answer in answers:
        qid=answer.get('qid')
        if qid not in m['question_order'] or qid in seen:raise ValueError('Unknown or duplicate question')
        seen.add(qid);qp=session/'questions'/(qid+'.json');rp=session/'results'/(qid+'.json')
        if sha(qp.read_bytes())!=m['question_sha256'][qid]:raise ValueError('Question changed')
        q=json.loads(qp.read_text());result=json.loads(rp.read_text())
        if (answer.get('question_sha256')!=m['question_sha256'][qid] or answer.get('result_sha256')!=sha(rp.read_bytes())
                or result['input_sha256']!=m['question_sha256'][qid] or answer.get('raw_report_sha256')!=q['raw_report_sha256']):
            raise ValueError('Human answer input/result/report hash mismatch')
        for field in ('kind','cell','run_id','criterion'):
            if answer.get(field)!=q[field]:raise ValueError('Human answer identity mismatch: '+field)
        for field in ('actual_reviewer','reason','confirmed_at'):
            if not isinstance(answer.get(field),str) or not answer[field].strip():raise ValueError('Human confirmation requires '+field)
        datetime.fromisoformat(answer['confirmed_at'].replace('Z','+00:00'))
        if type(answer.get('accepted_model_pre_review')) is not bool:raise ValueError('Explicit human action type is required')
        run=root/q['run_dir']
        for name in ('raw_report.md','evidence_ledger.json','run_manifest.json','request.json'):
            relative=str((Path(q['run_dir'])/name).as_posix())
            if sha((run/name).read_bytes())!=m['original_artifact_sha256'][relative]:raise ValueError('Original run changed: '+relative)
        reason=answer['reason'].strip()
        if answer['accepted_model_pre_review']:
            if answer['judgment']!=result['judgment']:raise ValueError('Accepted-model action cannot change the suggested label')
            reason+='\n人工明确确认的模型预评理由：'+result['rationale_zh']
        if q['kind']=='source_support':
            if (answer.get('item_id')!=q['item_id'] or answer.get('selection_confirmed') is not True
                    or answer.get('judgment') not in {'supported','contradicted','insufficient'}):
                raise ValueError('Source confirmation requires original item, selection and valid label')
            ids=answer.get('reviewed_evidence_ids')
            known={s['citation'] for s in q['sources']}
            if not isinstance(ids,list) or len(ids)!=len(set(ids)) or any(i not in known for i in ids):raise ValueError('Invalid actually reviewed source IDs')
            if answer['judgment']!='insufficient' and not ids:raise ValueError('Support/contradiction needs reviewed evidence IDs')
            path=run/'human_review/review.json'
            if path not in reviews:reviews[path]=json.loads(path.read_text());validate_review(run,reviews[path])
            item=next(i for i in reviews[path]['items'] if i['id']==q['item_id'])
            changes={'judgment':answer['judgment'],'reason':reason,'actual_reviewer':answer['actual_reviewer'].strip(),
                     'selection_confirmed_by_actual_reviewer':True,'reviewed_evidence_ids':ids}
            if item.get('judgment') is not None and any(item.get(k)!=v for k,v in changes.items()):
                raise ValueError('Refusing to replace an existing human source answer')
            item.update(changes,model_pre_review_reference={'session':session.name,'qid':qid,
                'result_sha256':answer['result_sha256'],'accepted_model_pre_review':answer['accepted_model_pre_review'],
                'human_confirmed_at':answer['confirmed_at']},
                review_method=answer.get('review_method','human_review'),
                confirmation_origin=answer.get('confirmation_origin','explicit_export'),
                confirmation_record_sha256=answer.get('confirmation_record_sha256'),
                model_selection_suitability=result.get('selection_suitability'))
        else:
            if answer['judgment'] not in {'satisfied','not_satisfied','uncertain'}:raise ValueError('Invalid human content label')
            content.append((q,answer,reason))
    writes={}
    for path,review in reviews.items():
        review['completed']=bool(review['items']) and all(i.get('judgment') is not None for i in review['items'])
        validate_review(path.parent.parent,review)
        writes[path]=(json.dumps(review,ensure_ascii=False,indent=2)+'\n').encode()
    if content:
        worksheet=root/'artifacts/tables'/m['freeze_id']/'human_content_worksheet.csv'
        reader=csv.DictReader(io.StringIO(worksheet.read_text()));fields=reader.fieldnames;rows=list(reader)
        fields=list(dict.fromkeys(fields+list(REVIEW_METADATA)))
        for row in rows:
            for field in REVIEW_METADATA:row.setdefault(field,'')
        keyed={(r['cell'],r['criterion']):r for r in rows}
        if len(keyed)!=len(rows):raise ValueError('Duplicate existing content worksheet rows')
        for q,answer,reason in content:
            row=keyed[(q['cell'],q['criterion'])]
            if row['run_id']!=q['run_id']:raise ValueError('Worksheet run differs from question')
            label={'satisfied':'true','not_satisfied':'false','uncertain':''}[answer['judgment']]
            changes={'satisfied':label,'reason':reason,'actual_reviewer':answer['actual_reviewer'].strip()}
            if (row.get('satisfied') or row.get('judgment_type')=='actual_human_uncertain') and any(row.get(k)!=v for k,v in changes.items()):raise ValueError('Refusing to replace an existing human content answer')
            row.update(changes,judgment_type='actual_human' if label else 'actual_human_uncertain',
                review_method=answer.get('review_method','human_review'),
                confirmation_origin=answer.get('confirmation_origin','explicit_export'),
                confirmation_record_sha256=answer.get('confirmation_record_sha256',''),
                model_review_qid=q['qid'],model_result_sha256=answer['result_sha256'])
            if not label:uncertain.append(q['qid'])
        stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
        writes[worksheet]=stream.getvalue().encode()
    record={'schema':'human-confirmation-import-v1','session':session.name,'export_sha256':sha(export.read_bytes()),
        'human_answers':len(answers),'reviewed_but_uncertain_content':uncertain,'apply':apply,
        'input_identity_validated':True,'existing_human_answers_preserved':True,
        'files':[{'path':str(p.relative_to(root)),'before_sha256':sha(p.read_bytes()),'after_sha256':sha(b)} for p,b in writes.items()]}
    if apply and writes:
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');backup=session/'human_imports'/stamp
        before={p:p.read_bytes() for p in writes};written=[]
        for p,b in before.items():
            dest=backup/'before'/p.relative_to(root);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b)
        try:
            for p,b in writes.items():
                with tempfile.NamedTemporaryFile(dir=p.parent,prefix='.human-confirmation-',delete=False) as temporary:
                    temporary.write(b);temp=Path(temporary.name)
                os.replace(temp,p);written.append(p)
        except Exception:
            for p in written:p.write_bytes(before[p])
            raise
        record['backup']=str(backup)
        (backup/'import_record.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
        (backup/'human_export.json').write_bytes(export.read_bytes())
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--session',required=True,type=Path);p.add_argument('--export',required=True,type=Path)
    p.add_argument('--apply',action='store_true');a=p.parse_args()
    print(json.dumps(import_confirmations(a.session,a.export,apply=a.apply),ensure_ascii=False,indent=2))
