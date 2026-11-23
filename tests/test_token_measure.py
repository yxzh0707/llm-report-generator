import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from customization import measure_report_length
from phase1_request_policy import ReportRequest
from token_measure import ReportTokenMeter, add_token_measurement

SETTINGS = {'kind': 'vllm', 'base_url': 'https://example.org/v1',
            'model': 'test-model', 'api_key_env': 'TEST_TOKEN_MEASURE_KEY'}


class TokenMeasureTests(unittest.TestCase):
    def test_exact_tokenizer_excludes_sources_and_caches_identical_body(self):
        def respond(request, timeout):
            self.assertEqual(request.full_url, 'https://example.org/tokenize')
            payload = json.loads(request.data)
            self.assertEqual(payload['prompt'], '# Heading\nrevenue [S1].\n')
            self.assertFalse(payload['add_special_tokens'])
            self.assertEqual(payload['model'], 'test-model')
            self.assertEqual(timeout, 3)
            return io.BytesIO(b'{"count": 9}')
        meter = ReportTokenMeter(SETTINGS)
        with patch('token_measure.urlopen', side_effect=respond) as call:
            a = meter.measure('# Heading\nrevenue [S1].\n## Sources\nA')
            b = meter.measure('# Heading\nrevenue [S1].\n## Sources\nB')
        self.assertEqual(call.call_count, 1)
        self.assertEqual(a, b)
        self.assertEqual(a['count'], 9)
        self.assertTrue(a['exact_for_text'])

    def test_unavailable_tokenizer_does_not_guess_or_allow_overlong_report(self):
        req = ReportRequest(task='t', max_words=100)
        for raw in (b'{"count": true}', b'{"count": -1}', b'{}', b'{"count": 0}'):
            meter = ReportTokenMeter(SETTINGS)
            with patch('token_measure.urlopen', return_value=io.BytesIO(raw)) as call:
                token = meter.measure('word ' * 101)
                meter.measure('another draft')
            self.assertEqual(call.call_count, 1)
            result = add_token_measurement(measure_report_length('word ' * 101, req), token)
            self.assertIsNone(result['body_token_measurement']['count'])
            self.assertIsNone(result['draft_target_tokens_estimate'])
            self.assertFalse(result['can_save'])
        with patch('token_measure.urlopen', side_effect=TimeoutError('private response')):
            result = ReportTokenMeter(SETTINGS).measure('draft')
        self.assertNotIn('private', json.dumps(result))

    def test_conversion_uses_measured_ratio_and_preserves_word_gate(self):
        req = ReportRequest(task='t', min_words=250, max_words=500)
        measured = {'count': 800, 'exact_for_text': True}
        result = add_token_measurement(measure_report_length('word ' * 501, req), measured)
        self.assertEqual(result['draft_target_words'], 425)
        self.assertEqual(result['draft_target_tokens_estimate'], 678)
        self.assertFalse(result['can_save'])
        self.assertAlmostEqual(result['measured_tokens_per_word'], 800 / 501)
        no_limit = add_token_measurement(measure_report_length('word ' * 501,
            ReportRequest(task='t', depth='brief')), measured)
        self.assertIsNone(no_limit['draft_target_tokens_estimate'])
        self.assertTrue(no_limit['can_save'])

    def test_unsupported_provider_never_calls_a_guessed_endpoint(self):
        with patch('token_measure.urlopen') as call:
            token = ReportTokenMeter(dict(SETTINGS, kind='tokenhub_openai')).measure('draft')
        call.assert_not_called()
        self.assertIsNone(token['count'])


if __name__ == '__main__':
    unittest.main()
