"""Measure draft text with the generator's tokenizer, never an LLM estimate."""
import hashlib
import json
import math
import os
from urllib.request import Request, urlopen

from customization import report_body
from runtime_config import provider_settings


class ReportTokenMeter:
    """Per-report cache and bounded failure handling; no generation or judge calls."""

    def __init__(self, settings=None, timeout=3):
        self.settings = settings
        self.timeout = timeout
        self.cache = {}
        self.unavailable_reason = None

    def measure(self, report):
        body = report_body(report)
        identity = hashlib.sha256(body.encode('utf-8')).hexdigest()
        if identity in self.cache:
            return dict(self.cache[identity])
        result = {'count': None, 'exact_for_text': False, 'method': 'unavailable',
                  'scope': 'Body text including Markdown and citation IDs; excludes Sources and chat/tool framing.',
                  'text_sha256': identity}
        if self.unavailable_reason is None:
            try:
                settings = self.settings or provider_settings(role='generator')
                result['model'] = settings['model']
                if settings['kind'] != 'vllm':
                    self.unavailable_reason = 'provider_tokenizer_not_configured'
                else:
                    endpoint = settings['base_url'].rstrip('/').removesuffix('/v1') + '/tokenize'
                    headers = {'Content-Type': 'application/json'}
                    key = os.getenv(settings['api_key_env'])
                    if key:
                        headers['Authorization'] = 'Bearer ' + key
                    payload = {'model': settings['model'], 'prompt': body,
                               'add_special_tokens': False}
                    request = Request(endpoint, data=json.dumps(payload).encode(), headers=headers, method='POST')
                    with urlopen(request, timeout=self.timeout) as response:
                        data = json.load(response)
                    count = data.get('count')
                    if type(count) is not int or count < 0 or (body and count == 0):
                        raise ValueError('Invalid tokenizer count')
                    result.update(count=count, exact_for_text=True, method='generator_tokenizer')
            except Exception:
                # Do not leak provider response bodies, URLs or credentials. An outage
                # must not bypass the deterministic word gate or consume every retry.
                self.unavailable_reason = 'tokenizer_unavailable_or_invalid_response'
        if self.unavailable_reason:
            result['unavailable_reason'] = self.unavailable_reason
        if len(self.cache) >= 32:
            self.cache.pop(next(iter(self.cache)))
        self.cache[identity] = result
        return dict(result)


def add_token_measurement(length, token_measurement):
    """Convert the word target using the measured draft ratio, not a 1:1 claim."""
    result = dict(length, body_token_measurement=token_measurement)
    words, tokens = length['body_words'], token_measurement['count']
    ratio = tokens / words if tokens is not None and words else None
    target = length['draft_target_words']
    result.update(measured_tokens_per_word=ratio,
                  draft_target_tokens_estimate=math.floor(target * ratio)
                  if target is not None and ratio is not None else None,
                  token_budget_note='Target tokens are a planning estimate from this draft ratio, not a hard output cap or a word-limit guarantee. The deterministic word count controls acceptance.')
    return result
