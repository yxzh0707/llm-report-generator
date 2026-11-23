"""All artificial confirmations are isolated fixtures, never actual human grades."""
import copy
import csv
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from analysis.ai_review import accept, sha
from analysis.import_ai_review import import_confirmations
from analysis.review_validation import original_proposal

ROOT=Path(__file__).resolve().parents[1]
SESSION=ROOT/'artifacts/model_reviews/20261020T062642477399Z_astra_high'


class AIReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.manifest=json.loads((SESSION/'manifest.json').read_text())
        self.session=self.root/'model_review'/SESSION.name
        for name in ('manifest.json','questions/Q001.json','questions/Q002.json','questions/Q021.json',
                     'results/Q001.json','results/Q002.json','results/Q021.json'):
            dest=self.session/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(SESSION/name,dest)
        self.export={'schema':'actual-human-review-confirmations-v1','session':SESSION.name,
            'freeze_id':self.manifest['freeze_id'],'manifest_sha256':sha((SESSION/'manifest.json').read_bytes()),'answers':[]}
        self.export_path=self.root/'isolated_confirmation_fixture.json'

    def answer(self,qid,label=None):
        q=json.loads((SESSION/'questions'/(qid+'.json')).read_text())
        r=json.loads((SESSION/'results'/(qid+'.json')).read_text())
        run=self.root/q['run_dir'];run.mkdir(parents=True,exist_ok=True)
        for name in ('raw_report.md','evidence_ledger.json','run_manifest.json','request.json','frozen_evidence.json'):
            shutil.copyfile(ROOT/q['run_dir']/name,run/name)
        if q['kind']=='source_support':
            (run/'human_review').mkdir(exist_ok=True)
            (run/'human_review/review.json').write_text(json.dumps(original_proposal(run)))
        else:
            path=self.root/'artifacts/tables'/self.manifest['freeze_id']/'human_content_worksheet.csv'
            path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/path.relative_to(self.root),path)
            with path.open() as stream:rows=list(csv.DictReader(stream))
            for row in rows:row.update(satisfied='',reason='',actual_reviewer='',judgment_type='pending_actual_human')
            with path.open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        return {'qid':qid,'kind':q['kind'],'cell':q['cell'],'run_id':q['run_id'],'item_id':q.get('item_id'),'criterion':q['criterion'],
            'question_sha256':self.manifest['question_sha256'][qid],'result_sha256':sha((SESSION/'results'/(qid+'.json')).read_bytes()),
            'raw_report_sha256':q['raw_report_sha256'],'judgment':label or r['judgment'],
            'reason':'仅供临时目录中的导入器测试，不是真实人工评分。','actual_reviewer':'isolated fixture reviewer',
            'selection_confirmed':q['kind']=='source_support','reviewed_evidence_ids':list(dict.fromkeys(e['source_id'] for e in r['evidence_checks'])),
            'accepted_model_pre_review':False,'confirmed_at':'2026-10-20T00:00:00Z'}

    def run_import(self,apply=False):
        self.export_path.write_text(json.dumps(self.export))
        return import_confirmations(self.session,self.export_path,apply=apply,root=self.root)

    def test_model_outputs_do_not_automatically_become_human_scores(self):
        r=self.run_import(apply=True)
        self.assertEqual(r['human_answers'],0);self.assertEqual(r['files'],[])

    def test_dry_run_and_partial_actual_confirmation_preserve_selection_and_other_items(self):
        self.export['answers']=[self.answer('Q001')]
        q=json.loads((SESSION/'questions/Q001.json').read_text());path=self.root/q['run_dir']/'human_review/review.json';before=path.read_bytes()
        report=self.run_import();self.assertFalse(report['apply']);self.assertEqual(path.read_bytes(),before)
        self.run_import(apply=True);after=json.loads(path.read_text())
        self.assertFalse(after['completed']);self.assertIsNotNone(after['items'][0]['judgment'])
        self.assertTrue(all(i['judgment'] is None for i in after['items'][1:]))
        original=json.loads(before);self.assertEqual(after['items'][0]['exact_claim'],original['items'][0]['exact_claim'])

    def test_identity_mismatch_duplicate_and_missing_selection_fail_without_writes(self):
        answer=self.answer('Q001');q=json.loads((SESSION/'questions/Q001.json').read_text());path=self.root/q['run_dir']/'human_review/review.json';before=path.read_bytes()
        variants=[[{**answer,'result_sha256':'wrong'}],[answer,answer],[{**answer,'selection_confirmed':False}]]
        for answers in variants:
            self.export['answers']=answers
            with self.subTest(answers=len(answers)),self.assertRaises(ValueError):self.run_import(apply=True)
            self.assertEqual(path.read_bytes(),before)

    def test_uncertain_content_is_reviewed_not_satisfied_and_prior_answers_are_preserved(self):
        answer=self.answer('Q021','uncertain');self.export['answers']=[answer]
        self.run_import(apply=True)
        worksheet=self.root/'artifacts/tables'/self.manifest['freeze_id']/'human_content_worksheet.csv'
        with worksheet.open() as stream:rows=list(csv.DictReader(stream))
        first=next(r for r in rows if r['cell']==answer['cell'] and r['criterion']==answer['criterion'])
        self.assertEqual(first['satisfied'],'');self.assertEqual(first['judgment_type'],'actual_human_uncertain')
        before=worksheet.read_bytes()
        self.export['answers'][0]['judgment']='satisfied'
        with self.assertRaises(ValueError):self.run_import(apply=True)
        self.assertEqual(worksheet.read_bytes(),before)
        first.update(satisfied='false',reason='Existing isolated human fixture.',actual_reviewer='previous fixture reviewer')
        stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows);worksheet.write_text(stream.getvalue());before=worksheet.read_bytes()
        self.export['answers'][0]['judgment']='satisfied'
        with self.assertRaises(ValueError):self.run_import(apply=True)
        self.assertEqual(worksheet.read_bytes(),before)

    def test_accept_rejects_untraceable_quotes_and_out_of_order_questions(self):
        session=self.root/'model_session';(session/'questions').mkdir(parents=True)
        shutil.copyfile(SESSION/'manifest.json',session/'manifest.json')
        for qid in ('Q001','Q002'):shutil.copyfile(SESSION/'questions'/(qid+'.json'),session/'questions'/(qid+'.json'))
        draft=copy.deepcopy(json.loads((SESSION/'results/Q001.json').read_text()));draft['evidence_checks'][0]['quote_en']='Invented quote that does not exist.'
        path=self.root/'draft.json';path.write_text(json.dumps(draft))
        with self.assertRaises(ValueError):accept(session,path)
        draft=json.loads((SESSION/'results/Q002.json').read_text());path.write_text(json.dumps(draft))
        with self.assertRaises(ValueError):accept(session,path)
        self.assertFalse((session/'results').exists())


if __name__=='__main__':unittest.main()
