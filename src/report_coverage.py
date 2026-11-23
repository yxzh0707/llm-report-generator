"""Explicit missing-period business-topic disclosure, from the user's request.

The recognizer supports a declared English company/topic list tied to a quarter.
It does not infer an arbitrary task checklist or score prose semantically.
"""
import re
from customization import report_body
from report_validation import fiscal_period,source_period


def business_topics(task):
    match=re.search(r'\bbusiness topics from (?:the )?Q([1-4]) releases?:\s*([^\n]+)',task,re.I)
    if not match:return []
    block=re.split(r'\.\s+(?:Retain|If|Compare|Cite)\b',match[2],maxsplit=1,flags=re.I)[0].rstrip('.')
    result=[]
    for clause in block.split(';'):
        if ':' not in clause:continue
        company,topic=clause.split(':',1);company=company.strip();topic=topic.strip()
        if company and topic and len(company)<=80 and len(topic)<=300:result.append(dict(company=company,topic=topic,quarter=int(match[1])))
    return result


def validate_missing_topics(content,task,calls,sources):
    facts=[f for c in calls if 'error' not in c['result'] for f in c['result'].get('facts',[])];issues=[]
    for topic in business_topics(task):
        company=topic['company'];q=topic['quarter'];missing=[]
        for f in facts:
            period=fiscal_period(f.get('period',''))
            if (f.get('status')=='unavailable' and period and period[1]==q
                    and re.match(re.escape(company)+r'\b',f.get('report_label',''),re.I)):
                available=any(company.casefold() in s.get('title','').casefold() and source_period(s)==period for s in sources)
                if not available:missing.append(period)
        if not missing:continue
        terms=set(re.findall(r'[a-z]{3,}|\d+',topic['topic'].casefold()))-set('the and from with its reported stated reporting period distinguishing'.split())
        heading='';found=False
        for line in report_body(content).splitlines():
            clean=re.sub(r'[*_`]','',line)
            if re.match(r'^#{1,6}\s',clean):heading=clean;continue
            combined=heading+' '+clean
            if company.casefold() not in combined.casefold() or not re.search(r'\bQ'+str(q)+r'\b',combined,re.I):continue
            if not re.search(r'\bunavailable\b|cannot (?:be )?(?:establish|established|assess|confirm)|cannot determine|not available|\b(?:absent|missing)\b',clean,re.I):continue
            topical=bool(re.search(r'\b(?:update|updates|topic|topics)\b',combined,re.I)) or len(terms & set(re.findall(r'[a-z]{3,}|\d+',combined.casefold())))>=2
            if topical:found=True;break
        if not found:issues.append(dict(code='missing_business_topic_disclosure',company=company,quarter=q,topic=topic['topic'],
            required_action=f"Explicitly state that {company}'s Q{q} {topic['topic']} update cannot be established because its own-quarter release is absent. Earlier-quarter context may be separately labelled but must not replace this requested update or its disclosure."))
    return issues
