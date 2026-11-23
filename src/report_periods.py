"""Evidence-bound reporting-date arithmetic, separate from publication dates."""
import re
from datetime import date,datetime
from fact_grounding import normalized
from report_validation import citation_id

PERIOD_TOOL='compare_reporting_dates'
PERIOD_SCHEMA={'type':'object','additionalProperties':False,'required':['periods','comparisons'],'properties':{
    'periods':{'type':'array','minItems':2,'maxItems':16,'items':{'type':'object','additionalProperties':False,
        'required':['id','label','end_date','citation','source_quote'],
        'properties':{k:{'type':'string'} for k in ['id','label','end_date','citation','source_quote']}}},
    'comparisons':{'type':'array','minItems':1,'maxItems':16,'items':{'type':'object','additionalProperties':False,
        'required':['left','right'],'properties':{'left':{'type':'string'},'right':{'type':'string'}}}}}}


def dates_in(text):
    s=normalized(text).replace('Sept.','Sep.').replace('Sept ','Sep ')
    found=set()
    for m in re.finditer(r'\b20\d{2}-\d{2}-\d{2}\b',s):
        try:found.add(date.fromisoformat(m[0]))
        except ValueError:pass
    months=r'Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?'
    for m in re.finditer(r'\b('+months+r')\.?\s+(\d{1,2}),?\s+(20\d{2})\b',s,re.I):
        try:found.add(datetime.strptime(m[1][:3].title()+' '+m[2]+' '+m[3],'%b %d %Y').date())
        except ValueError:pass
    return found


def compare_periods(periods,comparisons,sources):
    if not 2<=len(periods)<=16 or not 1<=len(comparisons)<=16:raise ValueError('Use 2–16 dates and 1–16 comparisons')
    by_id={s['citation']:s for s in sources};nodes={}
    for p in periods:
        if set(p)!={'id','label','end_date','citation','source_quote'}:raise ValueError('Supply the five declared period fields')
        if not all(isinstance(v,str) and v for v in p.values()) or len(p['source_quote'])>2400:raise ValueError('Use bounded text fields')
        if p['id'] in nodes:raise ValueError('Duplicate period ID')
        d=date.fromisoformat(p['end_date']);s=by_id.get(citation_id(p['citation']))
        if not s or normalized(p['source_quote']) not in normalized(s.get('text','')):raise ValueError('Date quotation is not in the cited, already-read source')
        if d not in dates_in(p['source_quote']):raise ValueError('ISO end_date must occur in source_quote; include its year. Use reporting end dates, not release/publication dates.')
        nodes[p['id']]={**p,'date':d}
    result=[]
    for c in comparisons:
        if set(c)!={'left','right'} or c['left'] not in nodes or c['right'] not in nodes:raise ValueError('Comparison requires declared left and right IDs')
        a,b=nodes[c['left']],nodes[c['right']];days=(b['date']-a['date']).days
        result.append(dict(left=a['label'],right=b['label'],left_end_date=a['end_date'],right_end_date=b['end_date'],
            right_minus_left_days=days,absolute_days=abs(days),same_end_date=days==0,
            preferred_description=f"{b['label']} ends {abs(days)} days {'after' if days>=0 else 'before'} {a['label']}.",
            citations=[a['citation'],b['citation']]))
    return dict(periods=periods,comparisons=result,scope='Quoted date identity and exact day differences; caller must choose corresponding reporting periods, not publication dates. Duration comparability also depends on the source period starts.')


def validate_calendar_claims(content,calls):
    # Restrict to quantified relative timing, not quarter labels or durations.
    numbers=r'\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve'
    units=r'days?|weeks?|months?|quarters?'
    gap=r'\b(?:offset|lag|lags|separated|difference|gap|differ|differs|differed)\b'
    # Do not cross a heading, entity name or date to find a number: a heading
    # "Fiscal differences: Alpha Q3 is 12 weeks" describes duration, not a gap.
    modifiers=r'\s+(?:(?:is|are|was|were|of|by|about|approximately|roughly|around|nearly|exactly|only|just)\s+)*'
    patterns=[gap+modifiers+r'('+numbers+r')\s+(?:calendar\s+)?('+units+r')\b',
              r'\b('+numbers+r')\s+(?:calendar\s+)?('+units+r')\s+(?:ahead|behind|earlier|later|apart|before|after)\b']
    names=dict(zip('one two three four five six seven eight nine ten eleven twelve'.split(),range(1,13)))
    comparisons=[c for call in calls if 'error' not in call['result'] for c in call['result'].get('comparisons',[])]
    issues=[]
    for number,line in enumerate(content.splitlines(),1):
        if not re.search(r'fiscal|calendar|quarter|period|date|ended|ending',line,re.I):continue
        for pattern in patterns:
            for m in re.finditer(pattern,line,re.I):
                value=float(names[m[1].lower()]) if m[1].lower() in names else float(m[1]);unit=m[2].lower().rstrip('s')
                scale={'day':1,'week':7,'month':30.436875,'quarter':91.310625}[unit]
                # Labels bind the comparison to the entities named in the line;
                # without an unambiguous pair, request exact dates instead.
                clause_start=max(line.rfind(';',0,m.start()),line.rfind('. ',0,m.start()))+1
                clause_end=min([i for sep in [';','. '] if (i:=line.find(sep,m.end()))>=0] or [len(line)])
                clause=line[clause_start:clause_end]
                named_quarters=set(re.findall(r'\bQ[1-4]\b',clause,re.I))
                before_quarters=re.findall(r'\bQ[1-4]\b',line[clause_start:m.start()],re.I)
                if len(named_quarters)>1 and before_quarters:named_quarters={before_quarters[-1]}
                candidates=[]
                for c in comparisons:
                    if not all(label.split()[0].casefold() in line.casefold() for label in [c['left'],c['right']]):continue
                    common_quarters=set(re.findall(r'\bQ[1-4]\b',c['left'],re.I)) & set(re.findall(r'\bQ[1-4]\b',c['right'],re.I))
                    if named_quarters and common_quarters and not named_quarters & common_quarters:continue
                    candidates.append(c)
                supported=any(abs(c['absolute_days']-value*scale)<=(0 if unit=='day' else scale/2+2) for c in candidates)
                if not supported:issues.append(dict(code='unverified_calendar_gap',line=number,claim=m[0],
                    required_action='Use compare_reporting_dates with quoted period-end dates before quantifying this timing gap. Prefer the returned exact dates and day difference, or state the actual dates without estimating a number of months/quarters.'))
    return issues
