import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from phase1_report_pipeline import build_prompt_package, render_report_sources
from phase1_request_policy import ReportRequest


class PipelineTests(unittest.TestCase):
    def test_selection_excludes_unselected_document_and_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'a.md').write_text('# UniqueTitle\n\nSource URL: https://example.com\n\n---\n\n' + 'Revenue growth. ' * 150)
            (root / 'b.md').write_text('UniqueTitle unrelated private material')
            p = build_prompt_package(ReportRequest(task='UniqueTitle revenue'), root, document_ids=['a'])
            self.assertTrue(p['sources'])
            self.assertTrue(all(s['document_id'] == 'a' for s in p['sources']))
            self.assertTrue(all(s['char_end'] > 100 for s in p['sources']))
            with self.assertRaises(ValueError):
                build_prompt_package(ReportRequest(task='summary'), root, document_ids=['a', 'absent'])

    def test_queries_share_fixed_budget_without_duplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'a.txt').write_text('strategy platform ' * 200)
            (root / 'b.txt').write_text('revenue earnings ' * 200)
            p = build_prompt_package(ReportRequest(task='analysis'), root, top_k=4,
                                     retrieval_queries=['strategy', 'revenue'])
            self.assertEqual(len(p['retrieval']['child_hits']), 4)
            self.assertEqual(len(p['sources']), 2)
            self.assertEqual(len({s['chunk_id'] for s in p['sources']}), 2)
            self.assertEqual(p['retrieval']['represented_documents'], ['a', 'b'])

    def test_source_rendering_preserves_body_and_unknown_citations(self):
        source = dict(citation='[S1]', title='Report', document_id='a', chunk_id='a:0001',
                      char_start=10, char_end=100, source_url=None)
        result = render_report_sources('## Findings\nFact [S1]. Unknown [S99].\n\n# Sources\nInvented URL', [source])
        self.assertIn('Fact [S1]. Unknown [S99].', result)
        self.assertIn('characters [10, 100)', result)
        self.assertNotIn('Invented URL', result)

    def test_txt_source_uses_document_identity_without_inventing_filename(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'earnings.txt').write_text('Revenue increased with data center demand. ' * 90)
            package = build_prompt_package(ReportRequest(task='Revenue demand'), root,
                                           document_ids=['earnings'])
            source = package['sources'][0]
            raw = f"## Findings\nRevenue increased {source['citation']}."
            rendered = render_report_sources(raw, package['sources'])
            self.assertIn('document ID `earnings`', rendered)
            self.assertNotIn('earnings.md', rendered)
            self.assertTrue(rendered.startswith(raw))
            self.assertIn(f"characters [{source['char_start']}, {source['char_end']})", rendered)


if __name__ == '__main__':
    unittest.main()
