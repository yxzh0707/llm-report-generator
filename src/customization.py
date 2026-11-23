"""Observable preset/style/depth constraints; tone still requires human review."""
import re
from phase1_request_policy import word_limits

DEPTH_WORDS = {'brief': (250, 500), 'standard': (650, 1400), 'detailed': (1500, 2300)}
STYLE_RULES = {
    'formal_analytical': 'Use formal analytical prose; distinguish reported facts and interpretation.',
    'concise_briefing': 'Use concise briefing bullets; prioritize key facts and avoid repetition.',
    'detailed_explanatory': 'Explain evidence, context and implications in paragraphs with useful subheadings.',
}
DEPTH_RULES = {
    'brief': 'Prioritize the main findings and essential qualifications. Keep explanations concise.',
    'standard': 'Cover the requested topics with enough evidence and explanation to support the conclusions.',
    'detailed': 'Develop the requested topics with evidence, context, qualifications and implications; avoid padding.',
}


def constraints(request):
    result = {'style_instruction': STYLE_RULES[request.style],
            'depth_instruction': DEPTH_RULES[request.depth],
            'comparison_table_required': request.structure == 'comparative_analysis',
            'tone_review': 'requires_actual_human_judgment'}
    limits = word_limits(request)
    if limits:
        result['body_words'] = {**limits, 'excludes': 'Sources section',
            'draft_target': drafting_target(limits),
            'count_includes': 'title, headings, tables; excludes [S#] citation IDs',
            'upper_limit_enforced_on_save': limits['max'] is not None}
    return result


def drafting_target(limits):
    low, high = limits['min'], limits['max']
    return max(low or 0, int(high * 0.85)) if high is not None else low


def report_body(report):
    return re.split(r'^#{1,2}[ \t]+Sources[ \t]*$', report, maxsplit=1, flags=re.M)[0]


def count_report_words(report):
    """Stable project word-count rule shared by tool, save gate and final audit."""
    return len(re.findall(r"\b[\w'-]+\b", re.sub(r'\[S\d+\]', '', report_body(report))))


def measure_report_length(report, request):
    count = count_report_words(report)
    limits = word_limits(request)
    low, high = (limits['min'], limits['max']) if limits else (None, None)
    target = drafting_target(limits) if limits else None
    excess = max(0, count - high) if high is not None else 0
    shortage = max(0, low - count) if low is not None else 0
    return {'body_words': count, 'minimum_words': low, 'maximum_words': high,
            'draft_target_words': target, 'within_range': not excess and not shortage if limits else None,
            'length_requested': bool(limits),
            'can_save': not excess, 'excess_words': excess,
            'words_to_remove_for_target': max(0, count - target) if target is not None else 0,
            'below_minimum_by': shortage,
            'count_rule': 'Includes title/headings/tables; excludes Sources section and [S#] IDs; regex word units.',
            'next_action': ('No numeric length was requested. Follow style and depth preferences; do not enforce a word limit.' if not limits else
                            'Compress repetition toward draft_target_words; preserve facts, qualifications and citations; check again.'
                            if excess else 'Below requested minimum; add supported coverage if available, staying below any maximum.'
                            if shortage else 'Length is within range; submit this text. This does not validate factual quality.')}


def check_customization(report, request):
    body = report_body(report)
    count = count_report_words(report)
    limits = word_limits(request)
    checks = []
    if limits:
        measurement = measure_report_length(report, request)
        checks.append({'id': 'depth_words', 'passed': measurement['within_range'],
                       'observed': count, 'expected': [limits['min'], limits['max']], 'origin': limits['origin']})
    if request.structure == 'comparative_analysis':
        checks.append({'id': 'comparison_table', 'passed': bool(re.search(
            r'^\s*\|?\s*:?-{3,}:?\s*\|', body, re.M))})
    if request.style == 'concise_briefing':
        bullets = re.findall(r'^\s*[-*+]\s+(.+)$', body, re.M)
        checks.append({'id': 'briefing_bullets', 'passed': bool(bullets),
                       'observed': len(bullets)})
    if request.style == 'detailed_explanatory':
        headings = len(re.findall(r'^###\s+\S', body, re.M))
        checks.append({'id': 'explanatory_subheadings', 'passed': headings >= 1, 'observed': headings})
    return {'items': checks, 'passed': all(c['passed'] for c in checks),
            'body_words': count, 'length_requested': bool(limits),
            'human_tone_score': None, 'depth_quality_review': 'requires_semantic_review'}
