"""Task-local, read-only access to archived worker text, not arbitrary files.

Archives are explicitly worker responses: upstream extraction/truncation remains
visible. Only admitted documents can be opened. Offsets count Unicode characters.
"""
import re
from pathlib import Path
from provenance import digest, write_json

WORKSPACE_TOOLS = {'search_evidence', 'read_evidence'}
WORKSPACE_INSTRUCTION = (
    'Opened web pages expose a workspace_document_id for archived worker text. '
    'The initial excerpt is only a prefix. If a required fact is absent, use search_evidence '
    'with a literal phrase, then read_evidence around the returned character offsets as needed. '
    'For reporting-period dates, inspect period-ended prose or consolidated financial-statement '
    'headers (e.g. Three Months Ended); distinguish current from comparative columns, publication '
    'dates, and operating metrics measured on different calendars. Cite the returned excerpt [S#]. '
    'Search is whitespace-tolerant and case-insensitive; paginate with next_start. '
    'The archive may itself be truncated upstream; never assume unobserved text exists. '
)
SCHEMAS = {
    'search_evidence': {
        'description': 'Search an opened document archived in this task. Returns up to three citable context windows, offsets, and pagination. Literal phrase, case-insensitive, whitespace-tolerant. No network access.',
        'parameters': {'type':'object','properties':{
            'document_id':{'type':'string'}, 'query':{'type':'string'},
            'start':{'type':'integer','minimum':0,'default':0}},
            'required':['document_id','query'],'additionalProperties':False}},
    'read_evidence': {
        'description': 'Read an exact range of archived worker text from an opened document. Returns a citable excerpt. Offsets are zero-based Unicode characters. At most 6000 characters per read. No arbitrary paths or network.',
        'parameters': {'type':'object','properties':{
            'document_id':{'type':'string'}, 'start':{'type':'integer','minimum':0},
            'length':{'type':'integer','minimum':1,'maximum':6000,'default':4000}},
            'required':['document_id','start'],'additionalProperties':False}},
}


class EvidenceWorkspace:
    def __init__(self, out):
        self.root = Path(out) / 'evidence_workspace'
        self.documents = {}

    def archive(self, source, text, *, upstream_truncated, original=None):
        sha = digest(text.encode())
        key = 'doc_' + digest((source['source_url']+'\n'+sha).encode())
        if key not in self.documents:
            self.root.mkdir(exist_ok=True)
            (self.root / (key+'.txt')).write_text(text, encoding='utf-8')
            self.documents[key] = {'document_id':key, 'text_sha256':sha,
                'characters':len(text), 'upstream_truncated':bool(upstream_truncated),
                'archive_scope':'persisted_original_extracted_text' if original else 'worker_returned_text', 'offset_unit':'unicode_characters',
                'source':dict(source)}
            if original:self.documents[key]['original']=original
            write_json(self.root/'index.json', self.documents)
        return {k:v for k,v in self.documents[key].items() if k!='source'}

    def access(self, name, args):
        allowed = {'document_id','query','start'} if name=='search_evidence' else {'document_id','start','length'}
        if name not in WORKSPACE_TOOLS or set(args)-allowed:
            raise ValueError('Invalid workspace operation or arguments')
        doc = self.documents.get(args.get('document_id'))
        if doc is None:
            raise ValueError('Unknown task document; use workspace_document_id from web_fetch')
        text = (self.root/(doc['document_id']+'.txt')).read_text(encoding='utf-8')
        if digest(text.encode()) != doc['text_sha256']:
            raise ValueError('Archived evidence integrity mismatch')
        start = args.get('start',0)
        if type(start) is not int or not 0 <= start <= len(text):
            raise ValueError('Invalid character offset')
        spans = []
        next_start = None
        if name=='read_evidence':
            if 'start' not in args: raise ValueError('Read requires start')
            length = args.get('length',4000)
            if type(length) is not int or not 1 <= length <= 6000:
                raise ValueError('Read length must be 1 to 6000 characters')
            if start < len(text): spans=[(start,min(len(text),start+length))]
        else:
            query = args.get('query','')
            if not isinstance(query,str) or not query.strip() or len(query)>120:
                raise ValueError('Supply a literal query of 1 to 120 characters')
            pattern = re.compile(r'\s+'.join(re.escape(x) for x in query.split()),re.I)
            for hit in pattern.finditer(text,start):
                if spans and hit.start() < spans[-1][1]: continue
                if len(spans)==3:
                    next_start=hit.start();break
                spans.append((max(start,hit.start()-400),min(len(text),hit.start()+1600)))
        public = {k:v for k,v in doc.items() if k!='source'}
        return public, doc['source'], [(a,b,text[a:b]) for a,b in spans], next_start
