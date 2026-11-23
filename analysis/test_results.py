"""Post-processing checks using isolated outputs; no genuine human grades written."""
import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
import shutil
from unittest.mock import patch
from analysis.build_results import build
from analysis.review_validation import original_proposal
from analysis import prepare_reviews


class ResultTests(unittest.TestCase):
    def test_failure_before_report_hash_remains_in_main_denominator(self):
        source=Path(__file__).resolve().parents[1]
        freeze=source/'artifacts/experiment_freezes/20261020T032924986612Z'
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);dest=root/'artifacts/experiments'/freeze.name;dest.mkdir(parents=True)
            ledger=json.loads((source/'artifacts/experiments'/freeze.name/'ledger.json').read_text())
            entry=ledger['entries'][0];entry['status']='failed'
            (dest/'ledger.json').write_text(json.dumps(ledger))
            run=Path(entry['run_dir']);local=root/'artifacts/runs'/run.name
            shutil.copytree(run,local)
            manifest=json.loads((local/'run_manifest.json').read_text())
            manifest.update(status='failed',automatic_passed=False,error_type='IsolatedSetupFailureFixture',
                            usage=None,model_calls=0,elapsed_seconds=0.01)
            manifest.pop('raw_report_sha256')
            (local/'run_manifest.json').write_text(json.dumps(manifest))
            (local/'raw_report.md').write_text('')
            (local/'audit.json').write_text(json.dumps({'status':'not_generated'}))
            (local/'evidence_ledger.json').write_text('[]')
            for name in ('runtime_output.json','enhanced_evidence_audit.json'):
                (local/name).unlink()
            with contextlib.redirect_stdout(io.StringIO()):out=build(root,freeze)
            summary=json.loads((out/'summary.json').read_text())
            self.assertEqual(summary['main']['runtime_completion']['numerator'],20)
            self.assertEqual(summary['main']['runtime_completion']['denominator'],21)
            self.assertEqual(summary['main']['usage_available']['numerator'],20)
            rows=json.loads((out/'per_run.json').read_text())
            self.assertEqual(len(rows),24)
            self.assertEqual(rows[0]['raw_report_integrity'],'empty_failed_run_before_report_hash')
            self.assertIsNone(rows[0]['total_tokens'])
            self.assertFalse(rows[0]['automatic_passed'])
            (local/'raw_report.md').write_text('Unhashed nonempty report')
            with contextlib.redirect_stdout(io.StringIO()),self.assertRaises(ValueError):build(root,freeze)

    def test_completed_source_reviews_flow_into_summary_without_overwriting_input(self):
        source=Path(__file__).resolve().parents[1]
        freeze=source/'artifacts/experiment_freezes/20261020T032924986612Z'
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'docs').mkdir()
            dest=root/'artifacts/experiments'/freeze.name;dest.mkdir(parents=True)
            ledger=json.loads((source/'artifacts/experiments'/freeze.name/'ledger.json').read_text())
            (dest/'ledger.json').write_text(json.dumps(ledger))
            rubric=json.loads((freeze/'rubric.json').read_text())
            unchanged={}
            for sample in rubric['human_source_audit']['preselected']:
                cell=f"{sample['condition']}_r{sample['repetition']}"
                entry=next(e for e in ledger['entries'] if e['cell']==cell)
                run=Path(entry['run_dir']);local=root/'artifacts/runs'/run.name
                shutil.copytree(run,local)
                review=original_proposal(local)
                review.update(actual_reviewer='isolated fixture reviewer',completed=True)
                for item in review['items']:
                    item.update(judgment='insufficient',reason='Isolated parser fixture only.',
                                selection_confirmed_by_actual_reviewer=True)
                path=local/'human_review/review.json';path.write_text(json.dumps(review))
                unchanged[path]=path.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                out=build(root,freeze)
                with patch.object(prepare_reviews,'ROOT',root):prepare_reviews.main(freeze)
            summary=json.loads((out/'summary.json').read_text())
            support=summary['main']['factual_support']
            self.assertEqual(support['status'],'complete')
            self.assertEqual(support['reviewed_claims'],20)
            self.assertEqual(support['insufficient'],20)
            self.assertIn('Actual human source support: complete',(out/'summary.md').read_text())
            self.assertEqual(len(json.loads((out/'source_support_items.json').read_text())),20)
            for path,data in unchanged.items():
                self.assertEqual(path.read_bytes(),data)
                self.assertTrue((path.parent/'evidence_catalog.md').exists())

    def test_duplicate_or_cross_run_human_worksheet_is_rejected_without_discarding_work(self):
        source=Path(__file__).resolve().parents[1]
        freeze=source/'artifacts/experiment_freezes/20261020T032924986612Z'
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);dest=root/'artifacts/experiments'/freeze.name;dest.mkdir(parents=True)
            (dest/'ledger.json').write_bytes((source/'artifacts/experiments'/freeze.name/'ledger.json').read_bytes())
            with contextlib.redirect_stdout(io.StringIO()):out=build(root,freeze)
            worksheet=out/'human_content_worksheet.csv';prior=(out/'summary.json').read_bytes()
            with worksheet.open(newline='') as stream:original=list(csv.DictReader(stream))
            variants=[original+[dict(original[0])],
                      [{**original[0],'run_id':'another-run'},*original[1:]],
                      [*original, {**original[0],'criterion':'unknown criterion'}]]
            for rows in variants:
                with worksheet.open('w',newline='') as stream:
                    writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
                before=worksheet.read_bytes()
                with contextlib.redirect_stdout(io.StringIO()),self.assertRaises(ValueError):build(root,freeze)
                self.assertEqual(worksheet.read_bytes(),before)
                self.assertEqual((out/'summary.json').read_bytes(),prior)

    def test_reconstruction_and_existing_human_input_preservation(self):
        source=Path(__file__).resolve().parents[1]
        freeze=source/'artifacts/experiment_freezes/20261020T032924986612Z'
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            dest=root/'artifacts/experiments'/freeze.name;dest.mkdir(parents=True)
            (dest/'ledger.json').write_bytes((source/'artifacts/experiments'/freeze.name/'ledger.json').read_bytes())
            with contextlib.redirect_stdout(io.StringIO()):out=build(root,freeze)
            summary=(out/'summary.json').read_bytes();table=(out/'per_run.csv').read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):build(root,freeze)
            self.assertEqual(summary,(out/'summary.json').read_bytes())
            self.assertEqual(table,(out/'per_run.csv').read_bytes())
            worksheet=out/'human_content_worksheet.csv'
            with worksheet.open(newline='') as stream:rows=list(csv.DictReader(stream))
            rows[0].update(satisfied='true',reason='isolated test fixture only',actual_reviewer='fixture reviewer')
            with worksheet.open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            with contextlib.redirect_stdout(io.StringIO()):build(root,freeze)
            with worksheet.open(newline='') as stream:restored=list(csv.DictReader(stream))
            self.assertEqual(restored[0]['actual_reviewer'],'fixture reviewer')
            self.assertEqual(restored[0]['satisfied'],'true')

    def test_reviewed_uncertainty_is_not_missing_or_strict_success(self):
        source=Path(__file__).resolve().parents[1]
        freeze=source/'artifacts/experiment_freezes/20261020T032924986612Z'
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);dest=root/'artifacts/experiments'/freeze.name;dest.mkdir(parents=True)
            (dest/'ledger.json').write_bytes((source/'artifacts/experiments'/freeze.name/'ledger.json').read_bytes())
            with contextlib.redirect_stdout(io.StringIO()):out=build(root,freeze)
            cell=next(r['cell'] for r in json.loads((out/'per_run.json').read_text())
                      if r['group']=='main' and r['automatic_passed'])
            worksheet=out/'human_content_worksheet.csv'
            with worksheet.open() as stream:rows=list(csv.DictReader(stream))
            selected=[r for r in rows if r['cell']==cell]
            for row in selected:
                row.update(satisfied='true',reason='Isolated fixture.',actual_reviewer='fixture',
                           review_method='author_review_after_model_pre_review')
            selected[0].update(satisfied='',judgment_type='actual_human_uncertain')
            def rebuild():
                with worksheet.open('w',newline='') as stream:
                    writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
                with contextlib.redirect_stdout(io.StringIO()):build(root,freeze)
                return next(r for r in json.loads((out/'per_run.json').read_text()) if r['cell']==cell)
            result=rebuild()
            self.assertTrue(result['actual_human_review_completed'])
            self.assertIsNone(result['strict_success'])
            coverage=json.loads((out/'summary.json').read_text())['main']['human_task_coverage']
            self.assertEqual(coverage['uncertain_items'],1)
            self.assertEqual(coverage['reviewed_items'],len(selected))
            selected[1]['satisfied']='false'
            self.assertFalse(rebuild()['strict_success'])


if __name__=='__main__':unittest.main()
