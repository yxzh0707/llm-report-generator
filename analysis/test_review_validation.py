"""Human-input fixtures stay in temporary directories; no real scores are assigned."""
import copy
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
import pysbd
from analysis.review_validation import original_proposal, validate_review

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'artifacts/runs/20261020T032924986612Z_T2_uploaded_only_r1_a001'


class ReviewValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.run = Path(self.temporary.name) / RUN.name
        self.run.mkdir()
        for name in ('run_manifest.json', 'raw_report.md', 'evidence_ledger.json', 'frozen_evidence.json'):
            shutil.copyfile(RUN / name, self.run / name)
        self.review = original_proposal(self.run)

    def grade(self, item, label='insufficient'):
        item.update(judgment=label, reason='Isolated schema-validation fixture; not a real human score.',
                    actual_reviewer='fixture reviewer', selection_confirmed_by_actual_reviewer=True)

    def test_pending_and_valid_partial_work_are_not_completed(self):
        self.assertEqual(validate_review(self.run, self.review)['reviewed_claims'], 0)
        self.grade(self.review['items'][0])
        result = validate_review(self.run, self.review)
        self.assertEqual(result['reviewed_claims'], 1)
        self.assertFalse(result['completed'])

    def test_completion_requires_every_original_item(self):
        for item in self.review['items']:
            self.grade(item)
        self.review['completed'] = True
        result = validate_review(self.run, self.review)
        self.assertTrue(result['completed'])
        self.assertEqual(result['reviewed_claims'], 5)
        self.assertEqual(result['actual_reviewers'], ['fixture reviewer'])

    def test_missing_duplicate_or_cross_report_items_cannot_pass(self):
        changes = [lambda r: r['items'].pop(),
                   lambda r: r['items'].__setitem__(1, copy.deepcopy(r['items'][0])),
                   lambda r: r.update(run_id='another-report'),
                   lambda r: r.update(raw_report_sha256='wrong')]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                review = copy.deepcopy(self.review)
                change(review)
                with self.assertRaises(ValueError):
                    validate_review(self.run, review)

    def test_changed_claim_or_evidence_is_not_silently_accepted(self):
        for field in ('claim', 'evidence'):
            review = copy.deepcopy(self.review)
            if field == 'claim':
                review['items'][0]['exact_claim'] = 'Invented factual claim.'
            else:
                review['items'][1]['evidence'][0]['text'] = 'Changed evidence.'
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_review(self.run, review)

    def test_complete_flag_and_confirmation_must_be_booleans(self):
        self.review['completed'] = 'false'
        with self.assertRaises(ValueError):
            validate_review(self.run, self.review)
        self.review['completed'] = False
        self.grade(self.review['items'][0])
        self.review['items'][0]['selection_confirmed_by_actual_reviewer'] = 'true'
        with self.assertRaises(ValueError):
            validate_review(self.run, self.review)

    def test_premature_complete_and_untraceable_support_are_rejected(self):
        self.review['completed'] = True
        self.grade(self.review['items'][0])
        with self.assertRaises(ValueError):
            validate_review(self.run, self.review)
        self.review['completed'] = False
        self.grade(self.review['items'][0], 'supported')
        self.assertEqual(self.review['items'][0]['citation_ids'], [])
        with self.assertRaises(ValueError):
            validate_review(self.run, self.review)
        self.review['items'][0]['reviewed_evidence_ids'] = ['[S2]']
        result = validate_review(self.run, self.review)
        self.assertEqual(result['items'][0]['evidence'][0]['citation'], '[S2]')
        self.review['items'][0]['reviewed_evidence_ids'] = ['[S999]']
        with self.assertRaises(ValueError):
            validate_review(self.run, self.review)

    def test_explicit_same_report_replacement_preserves_original(self):
        body = (self.run / 'raw_report.md').read_text().split('## Sources')[0]
        old = {i['exact_claim'] for i in self.review['items']}
        alternative = next(s.strip() for para in re.split(r'\n\s*\n', body)
                           if not para.strip().startswith('#')
                           for s in pysbd.Segmenter(language='en', clean=False).segment(para)
                           if s.strip() not in old and len(s.strip()) > 40)
        item = self.review['items'][-1]
        initial = item['exact_claim']
        item['selection_change'] = {'original_exact_claim': initial,
                                    'replacement_exact_claim': alternative,
                                    'reason': 'Isolated fixture for a reviewer-selected replacement.'}
        result = validate_review(self.run, self.review)
        self.assertEqual(result['items'][-1]['exact_claim'], alternative)
        self.assertEqual(result['items'][-1]['original_exact_claim'], initial)
        self.assertEqual(item['exact_claim'], initial)
        item['selection_change']['replacement_exact_claim'] = self.review['items'][0]['exact_claim']
        with self.assertRaises(ValueError):
            validate_review(self.run, self.review)


if __name__ == '__main__':
    unittest.main()
