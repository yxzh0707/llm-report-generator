import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from phase1_request_policy import ReportRequest, word_limits
from phase1_document_retrieval import load_documents,lexical_retrieve,build_chunks
from customization import check_customization, count_report_words, measure_report_length, constraints


class RequestCustomizationTests(unittest.TestCase):
    def test_shared_word_count_boundaries_and_sources_exclusion(self):
        req=ReportRequest(task='t', depth='brief',min_words=250,max_words=500)
        text="# Title\n\n## Findings\n\nAI-driven revenue rose 10.5% [S1].\n\n## Sources\n" + 'ignored '*1000
        self.assertEqual(count_report_words(text), 7)
        for count, allowed in [(249, True), (250, True), (425, True), (500, True), (501, False)]:
            report='word '*count
            measured=measure_report_length(report, req)
            self.assertEqual(measured['can_save'], allowed)
            self.assertEqual(measured['body_words'], count)
            self.assertEqual(measured['draft_target_words'], 425)
            self.assertEqual(measured['within_range'], check_customization(report,req)['passed'])
        self.assertFalse(measure_report_length('word '*249,req)['within_range'])

    def test_invalid_requests_are_rejected(self):
        for values in ({'task':''},{'task':'t','language':'Chinese'},
                       {'task':'t','structure':'custom'},{'task':'t','style':'casual'},
                       {'task':'t','depth':'unlimited'},{'task':'t','source_mode':'all'},
                       {'task':'t','output_format':'pdf'}):
            with self.assertRaises(ValueError):ReportRequest(**values).validate()

    def test_empty_unsupported_and_no_result_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with self.assertRaises(ValueError):load_documents(root)
            (root/'input.pdf').write_bytes(b'unsupported')
            with self.assertRaises(ValueError):load_documents(root)
            (root/'input.txt').write_text('Business revenue and reported strategy.')
            chunks=build_chunks(load_documents(root)[0])
            self.assertEqual(lexical_retrieve('unmatchedquux',chunks),[])

    def test_format_and_depth_constraints_do_not_imply_tone_or_facts(self):
        report='\n'.join('- '+('word '*9) for _ in range(30))
        result=check_customization(report,ReportRequest(task='t',style='concise_briefing',depth='brief'))
        self.assertTrue(result['passed']);self.assertIsNone(result['human_tone_score'])
        detailed=check_customization(report,ReportRequest(task='t',depth='detailed',min_words=1500,max_words=2300))
        self.assertFalse(detailed['passed'])
        explanation=('### Evidence\n\n### Interpretation\n\n### Limits\n\n'+'word '*700)
        self.assertTrue(check_customization(explanation,ReportRequest(task='t',style='detailed_explanatory'))['passed'])
        comparison=check_customization('word '*700,ReportRequest(task='t',structure='comparative_analysis'))
        self.assertFalse(comparison['passed'])

    def test_depth_never_implies_numeric_word_limits(self):
        for depth in ('brief','standard','detailed'):
            req=ReportRequest(task='Summarise the annual report',depth=depth)
            self.assertNotIn('body_words',constraints(req))
            for words in (20,3000):
                result=check_customization('word '*words,req)
                self.assertTrue(result['passed'])
                self.assertFalse(result['length_requested'])
                self.assertTrue(measure_report_length('word '*words,req)['can_save'])

    def test_explicit_limits_in_fields_or_task_and_invalid_ranges(self):
        for task,expected in [('Write 250–500 words',(250,500)),('Use at most 500 words',(None,500)),
                              ('报告不超过500个英文单词',(None,500)),('至少300词',(300,None)),
                              ('Exactly 200 words',(200,200)),('Write a 500-word report',(None,500)),
                              ('Use under 500 words',(None,499))]:
            req=ReportRequest(task=task);req.validate();limits=word_limits(req)
            self.assertEqual((limits['min'],limits['max']),expected)
        for fields in ({'max_words':True},{'max_words':0},{'min_words':500,'max_words':300}):
            with self.assertRaises(ValueError):ReportRequest(task='t',**fields).validate()
