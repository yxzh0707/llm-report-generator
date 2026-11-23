"""Bounded link discovery and retry policy; links never become fact evidence."""
import json,re
from urllib.parse import urlparse

def useful_links(value,limit=8):
    seen=set();ranked=[]
    for item in value.get('links',[]):
        if not isinstance(item,dict):continue
        url=item.get('url','');p=urlparse(url)
        if p.scheme not in {'http','https'} or not p.hostname or p.username or p.password or len(url)>2048 or url in seen:continue
        title=str(item.get('title',''))[:256];s=(url+' '+title).lower()
        score=4*bool(re.search(r'\.pdf(?:[?#]|$)',url,re.I))+3*bool(re.search(r'earnings|financial.result|quarter|exhibit.?99|press.release',s))
        score+=6*bool(re.search(r'earnings.release|press.release|exhibit.?99',s))
        score-=3*bool(re.search(r'transcript|presentation',s))
        if not score:continue
        seen.add(url);ranked.append((score,{'url':url,'title':title,'evidence_role':'discovery_only'}))
    return [x for _,x in sorted(ranked,key=lambda x:-x[0])[:limit]]

def grant_observed_links(path,links):
    """Retain invocation grants; worker still performs DNS/public-IP checks."""
    try:hosts=set(json.loads(path.read_text()))
    except (OSError,ValueError,TypeError):hosts=set()
    hosts.update(urlparse(x['url']).hostname.lower() for x in links)
    path.write_text(json.dumps(sorted(hosts)))

def retryable(value):
    if not isinstance(value,dict):return False
    error=str(value.get('error','')).lower()
    return bool(re.search(r'timeout|timed out|429|500|502|503|504|worker exited|connection|temporar',error))

ACQUISITION_INSTRUCTION=(
 'For live financial research, search the requested fiscal year and quarter explicitly. '
 'Inspect candidate titles and snippets before spending fetch calls; prefer the requested issuer release. '
 'SEC-hosted issuer exhibits and issuer-linked CDN/PDF copies are permitted primary-source routes; do not restrict discovery to one investor-relations domain. '
 'If broad results favor recent years, refine with a quoted fiscal year and quarter or the issuer domain. '
 'Search results, link titles and release landing pages are discovery only, not numerical evidence. '
 'web_fetch returns bounded discovery_links; if the body only links to a release PDF, fetch that observed PDF URL before declaring evidence missing. '
 'Never invent PDF URLs. Verify issuer, fiscal period and the actual financial figures in opened text. '
 'If a source is inaccessible, try another observed primary copy within the existing call budget. '
 'Finish retrieval before submitting one calculation plan. Preserve enough calls to calculate and save. ')
