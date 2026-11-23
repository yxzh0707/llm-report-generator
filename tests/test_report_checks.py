import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from report_checks import check_report


class ReportChecksTests(unittest.TestCase):
    package = {'required_headings': ['Summary', 'Sources'],
               'sources': [{'citation': '[S1]', 'document_id': 'a'}]}

    def test_valid_report_and_truncation(self):
        text = '## Summary\nFact [S1].\n## Sources\n[S1] a'
        self.assertTrue(check_report(text, self.package, 'stop')['mechanical_checks_passed'])
        self.assertFalse(check_report(text, self.package, 'length')['mechanical_checks_passed'])

    def test_sources_list_alone_is_not_a_body_citation(self):
        c = check_report('## Summary\nFact.\n## Sources\n[S1] a', self.package, 'stop')
        self.assertFalse(c['has_body_citations'])
        self.assertEqual(c['body_cited_documents'], [])

    def test_wrong_level_is_distinct_from_missing_section(self):
        c = check_report('# Summary\nFact [S99].\n# Sources', self.package, 'stop')
        self.assertEqual(c['missing_headings'], [])
        self.assertEqual(c['wrong_heading_levels'], ['Summary', 'Sources'])
        self.assertEqual(c['unknown_citations'], ['[S99]'])

    def test_order_duplicates_and_fenced_examples_fail(self):
        for text in ['## Sources\n## Summary\n[S1]',
                     '## Summary\n[S1]\n## Summary\n## Sources',
                     '```markdown\n## Summary\n[S1]\n## Sources\n```']:
            self.assertFalse(check_report(text, self.package, 'stop')['mechanical_checks_passed'])


if __name__ == '__main__':
    unittest.main()
