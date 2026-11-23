"""Bounded original-byte persistence and extraction for task evidence.

Network access reuses the financial worker's public URL and host grants. The
CLI runs in a killable process; PDF extraction is not performed on the agent
event loop. Complete means all bounded pages extracted, never OCR coverage.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urljoin
from pypdf import PdfReader
from autoresearch_frontier_finance._vendor.fflow.tools import _public_url, _client, _HTMLTextExtractor

MAX_BYTES=20_000_000
MAX_PAGES=200
MAX_CHARS=2_000_000
def sha(data):return hashlib.sha256(data).hexdigest()

def persist_extract(data, url, folder, content_type='application/pdf'):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    if not data or len(data)>MAX_BYTES:raise ValueError('Original byte limit exceeded or empty response')
    pdf=data.startswith(b'%PDF')
    raw=folder/('original.pdf' if pdf else 'original.html' if 'html' in content_type else 'original.txt')
    raw.write_bytes(data)
    failures=[];pages=[];links=[];complete=True;page_count=None
    if pdf:
        reader=PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(''):raise ValueError('Password protected PDF')
        page_count=len(reader.pages);parts=[];characters=0
        for number,page in enumerate(reader.pages[:MAX_PAGES],1):
            try:text=page.extract_text() or ''
            except Exception:
                text='';failures.append(number)
            if not text.strip() and number not in failures:failures.append(number)
            part=f'\n--- Page {number} ---\n{text}';parts.append(part);characters+=len(part)
            pages.append(dict(page=number,characters=len(text),extractable=bool(text.strip())))
            if characters>=MAX_CHARS:break
        text=''.join(parts).strip()
        complete=not failures and len(pages)==page_count and len(text)<=MAX_CHARS
    elif 'html' in content_type or b'<html' in data[:500].lower():
        parser=_HTMLTextExtractor();parser.feed(data.decode('utf-8',errors='replace'));text=parser.text();links=parser.source_links(url)
        complete=len(text)<=MAX_CHARS
    elif any(kind in content_type for kind in ('text','json','xml')):
        text=data.decode('utf-8',errors='replace');complete=len(text)<=MAX_CHARS
    else:raise ValueError('Unsupported original format')
    text=text[:MAX_CHARS];(folder/'extracted.txt').write_text(text,encoding='utf-8')
    record=dict(url=url,raw_file=raw.name,text_file='extracted.txt',raw_sha256=sha(data),raw_bytes=len(data),text_sha256=sha(text.encode()),text_characters=len(text),content_type=content_type,page_count=page_count,pages=pages,failed_pages=failures,complete_extraction=complete,limits=dict(bytes=MAX_BYTES,pages=MAX_PAGES,characters=MAX_CHARS),limitation='No OCR or semantic/table fidelity guarantee; empty/unreadable pages and extraction limits remain explicit.')
    (folder/'record.json').write_text(json.dumps(record,indent=2)+'\n')
    return dict(url=url,text=text,truncated=not complete,content_type=content_type,links=links,
                original_archive={**record,'raw_file':str(raw.resolve()),'text_file':str((folder/'extracted.txt').resolve())})

def download(url,folder):
    target=_public_url(url)
    with _client(follow_redirects=False) as client:
        for _ in range(6):
            with client.stream('GET',target) as response:
                if response.status_code in {301,302,303,307,308}:
                    target=_public_url(urljoin(str(response.url),response.headers['location']));continue
                response.raise_for_status();parts=[];length=0
                for block in response.iter_bytes():
                    length+=len(block)
                    if length>MAX_BYTES:raise ValueError('Original byte limit exceeded')
                    parts.append(block)
                return persist_extract(b''.join(parts),str(response.url),folder,response.headers.get('content-type','').lower())
    raise ValueError('Too many redirects')

def verified_original(value,out):
    """Reject non-task files and mismatched bytes/text before exposing reads."""
    record=value.get('original_archive')
    if not isinstance(record,dict):raise ValueError('Full-original fetch requires persisted original metadata')
    root=Path(out).resolve()
    for key,hashkey in [('raw_file','raw_sha256'),('text_file','text_sha256')]:
        file=Path(record[key])
        if file.is_symlink() or not file.resolve().is_relative_to(root):raise ValueError('Original archive must remain within this task')
        if sha(file.read_bytes())!=record[hashkey]:raise ValueError('Original archive integrity mismatch')
    if sha(value['text'].encode())!=record['text_sha256'] or record['url']!=value['url']:
        raise ValueError('Original text or URL mismatch')
    return {k:record[k] for k in ['raw_sha256','raw_bytes','text_sha256','page_count','complete_extraction','failed_pages','limitation']}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    try:print(json.dumps(download(args.url,args.output)))
    except Exception as exc:print(json.dumps({'error':'Original acquisition failed','error_type':type(exc).__name__}))
