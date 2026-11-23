"""A narrow editor request: one program-selected paragraph, one replacement."""
import re
from report_edits import editable_blocks,numeric_tokens

EDIT_SYSTEM=(
    'You are revising one narrative block of an existing report to meet an explicit word limit. '
    'Rewrite the selected block concisely, aiming at or below target_block_words. '
    'Keep its essential meaning, uncertainty and attribution. Preserve the listed protected_numeric_tokens '
    'and protected_citations exactly. Other report sections and tables are already written and stay intact. '
    'Remove repeated scope explanations and unnecessary wording. Do not add facts or figures. '
    'Call revise_report_text with exactly one replacement: the given block_id and your shorter new text. '
    'Do not copy the original paragraph unchanged. Word counts are calculated by the tool.')


def focused_edit_payload(request,content,measurement,last_error=None):
    options=[]
    for b in editable_blocks(content):
        if b['words']<25:continue
        heads=list(re.finditer(r'^##[ \t]+([^\n]+)',content[:b['start']],re.M))
        section=heads[-1][1].strip() if heads else ''
        # Prefer process/scope repetition over the primary findings and topics.
        priority=(0 if 'scope' in section.lower() else 1 if section=='Source Overview' else
                  2 if 'limitation' in section.lower() else 3 if section in ['Executive Summary','Conclusion','Integrated Findings'] else 4)
        options.append((priority,-b['words'],b,section))
    if not options:raise ValueError('No sizeable editable narrative block remains; preserve the required tables and headings')
    _,_,block,section=min(options,key=lambda v:(v[0],v[1],v[2]['block_id']))
    outside=content[:block['start']]+content[block['end']:]
    protected=sorted(numeric_tokens(content)-numeric_tokens(outside))
    cites=lambda s:set(re.findall(r'\[S\d+\]',s))
    return dict(operation='shorten_one_narrative_block',
        report_task=request.task.split('. ')[0],section=section,block_id=block['block_id'],
        text=block['text'],current_block_words=block['words'],target_block_words=max(15,int(block['words']*0.45)),
        report_body_words=measurement['body_words'],report_maximum_words=measurement['maximum_words'],
        protected_numeric_tokens=protected,protected_citations=sorted(cites(content)-cites(outside)),
        last_edit_feedback=last_error,
        instruction='Submit one shorter replacement for this block_id. All other sections and data tables remain as they are.')
