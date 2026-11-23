"""Program-selected narrative edits sized to the measured length excess."""
import re
from report_edits import editable_blocks,numeric_tokens

EDIT_SYSTEM=(
    'You are revising selected narrative blocks of an existing report to meet an explicit word limit. '
    'Rewrite each selected block concisely, aiming at or below its target_block_words. '
    'Keep its essential meaning, uncertainty and attribution. Preserve the listed protected_numeric_tokens '
    'and protected_citations exactly. Other report sections and tables are already written and stay intact. '
    'Use compact sentences or bullets. Remove repeated scope explanations and unnecessary wording. '
    'Keep period labels, result versus forecast distinctions, and uncertainty. Do not add facts or figures. '
    'Keep numeric spellings and units: do not change 900 million to 900M. '
    'Call revise_report_text with one replacement for each selected block_id and its shorter new text. '
    'Do not copy the original paragraph unchanged. Word counts are calculated by the tool.')


def focused_edit_payload(request,content,measurement,last_error=None,history=()):
    options=[]
    for b in editable_blocks(content):
        if b['words']<25:continue
        heads=list(re.finditer(r'^##[ \t]+([^\n]+)',content[:b['start']],re.M))
        section=heads[-1][1].strip() if heads else ''
        # Prefer process/scope repetition over the primary findings and topics.
        priority=(0 if 'scope' in section.lower() else 1 if section=='Source Overview' else
                  2 if 'limitation' in section.lower() else 3 if section in ['Executive Summary','Conclusion','Integrated Findings'] else 4)
        attempts=sum(any(b.get('section')==section for b in h.get('selected_blocks',[h])) for h in history)
        options.append((attempts//2,priority,-b['words'],b,section))
    if not options:raise ValueError('No sizeable editable narrative block remains; preserve the required tables and headings')
    options.sort(key=lambda v:(v[0],v[1],v[2],v[3]['block_id']))
    # A large initial overshoot cannot be repaired efficiently one paragraph
    # per model call. Keep the request local, but amortize up to three edits.
    excess=measurement['body_words']-measurement['maximum_words']
    count=3 if excess>60 else 1
    selected=options[:count]
    _,_,_,block,section=selected[0]
    outside=content[:block['start']]+content[block['end']:]
    protected=sorted(numeric_tokens(content)-numeric_tokens(outside))
    cites=lambda s:set(re.findall(r'\[S\d+\]',s))
    packet=dict(operation='shorten_selected_narrative_blocks',
        report_task=request.task.split('. ')[0],section=section,block_id=block['block_id'],
        text=block['text'],current_block_words=block['words'],target_block_words=max(15,int(block['words']*0.45)),
        report_body_words=measurement['body_words'],report_maximum_words=measurement['maximum_words'],
        protected_numeric_tokens=protected,protected_citations=sorted(cites(content)-cites(outside)),
        last_edit_feedback=last_error,
        instruction='Submit shorter replacements for every selected block. All other sections and data tables remain as they are.')
    packet['selected_blocks']=[]
    for _,_,_,b,sec in selected:
        packet['selected_blocks'].append(dict(block_id=b['block_id'],section=sec,text=b['text'],
            current_block_words=b['words'],target_block_words=max(15,int(b['words']*0.4)),
            protected_numeric_tokens=sorted(numeric_tokens(b['text'])),
            protected_citations=sorted(cites(b['text']))))
    # Avoid repeating the first passage in the actual model packet.
    packet.pop('text')
    return packet
