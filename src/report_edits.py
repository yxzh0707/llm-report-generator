"""Apply explicit shortening edits, then use the normal full-report save gate."""
import re
from customization import report_body,count_report_words

EDIT_TOOL='revise_report_text'
EDIT_SCHEMA={'type':'object','additionalProperties':False,'required':['replacements'],'properties':{
    'replacements':{'type':'array','minItems':1,'maxItems':16,'items':{'type':'object','additionalProperties':False,
        'required':['block_id','new'],'properties':{'block_id':{'type':'integer'},'new':{'type':'string'}}}}}}


def editable_blocks(content):
    blocks=[];body=report_body(content);offset=0;start=None
    def flush(end):
        nonlocal start
        if start is not None:
            text=body[start:end].rstrip('\r\n')
            if text:blocks.append(dict(block_id=len(blocks)+1,text=text,words=count_report_words(text),start=start,end=start+len(text)))
            start=None
    for line in body.splitlines(keepends=True):
        if not line.strip() or re.match(r'^\s*(?:#{1,6}\s|\|)',line):flush(offset)
        elif start is None:start=offset
        offset+=len(line)
    flush(offset)
    return blocks


def structure(text):
    return [line for line in report_body(text).splitlines() if re.match(r'^\s*(?:#{1,6}\s|\|)',line)]


def numeric_tokens(text):
    return set(re.findall(r'(?<![\w])(?:[<>≤≥+-]\s*)?\d[\d,]*(?:\.\d+)?(?:%|[BbMm])?',report_body(text)))


def apply_edits(content,replacements):
    if not isinstance(replacements,list) or not 1<=len(replacements)<=16:raise ValueError('Provide 1–16 exact text replacements')
    result=content
    blocks={b['block_id']:b for b in editable_blocks(content)};seen=set();resolved=[]
    for edit in replacements:
        if not isinstance(edit,dict) or not isinstance(edit.get('new'),str):raise ValueError('Each edit needs a block_id and new text')
        if set(edit)=={'block_id','new'}:
            identity=edit['block_id']
            if type(identity)is not int or identity not in blocks or identity in seen:raise ValueError('Use each displayed editable block_id at most once')
            seen.add(identity);b=blocks[identity];resolved.append((b['start'],b['end'],edit['new']))
        elif set(edit)=={'old','new'} and isinstance(edit['old'],str):
            # Compatibility for local callers; model-facing schema uses IDs.
            old=edit['old']
            if not old or content.count(old)!=1:raise ValueError('old must match exactly once')
            start=content.index(old);resolved.append((start,start+len(old),edit['new']))
        else:raise ValueError('Use the displayed block_id and new text only')
    for start,end,new in sorted(resolved,reverse=True):result=result[:start]+new+result[end:]
    if len(result.encode())>64000:raise ValueError('Revised text exceeds artifact size')
    if structure(result)!=structure(content):raise ValueError('Preserve every heading and table row unchanged; shorten narrative paragraphs and bullets only')
    if numeric_tokens(result)!=numeric_tokens(content):raise ValueError('Preserve distinct numeric tokens. Missing: '+str(sorted(numeric_tokens(content)-numeric_tokens(result)))+'; added: '+str(sorted(numeric_tokens(result)-numeric_tokens(content)))+'. Shorten prose, not numbers or percent qualifiers.')
    if set(re.findall(r'\[S\d+\]',report_body(result)))!=set(re.findall(r'\[S\d+\]',report_body(content))):raise ValueError('Preserve the body citation identities')
    if count_report_words(result)>=count_report_words(content):raise ValueError('The edits must reduce the actual body word count; repeating the draft is not a revision')
    return result
