import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from customization import report_body,count_report_words
from report_validation import report_rows,source_policy

class SourceSectionBoundaryTests(unittest.TestCase):
    def test_own_company_quarter_request_is_recognized(self):
        self.assertTrue(source_policy("Each row must cite that company's own release for that quarter.")['own_quarter_release'])
    def test_nested_sources_heading_keeps_subsequent_body_and_tables(self):
        report='## Scope\n### Sources\nUploaded releases [S1].\n## Findings\n| Revenue | 12.34 | [S1] |\n\n## Sources\nReference list excluded.'
        self.assertIn('| Revenue |',report_body(report))
        self.assertNotIn('Reference list excluded',report_body(report))
        self.assertEqual(report_rows(report)[0]['label'],'revenue')
        self.assertGreater(count_report_words(report),count_report_words('## Scope'))

    def test_top_level_source_appendix_still_excluded(self):
        for heading in ['# Sources','## Sources']:
            self.assertEqual(report_body('Body.\n'+heading+'\nReferences.'),'Body.\n')

if __name__=='__main__':unittest.main()
