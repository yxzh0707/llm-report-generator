"""Source-backed checks for explicit financial comparison statements.

This is a bounded English recognizer, not a general prose truth classifier.
Only unambiguous source rows, named calculator results and period bounds trigger
rejections. Every issue carries the observed claim and reproducible evidence.
No issuer names, answer-key values, model calls or external evaluation inputs.
"""
import re
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from customization import report_body
from fact_grounding import normalized
from report_periods import dates_in
from report_validation import source_period


def clean(text):
    return re.sub(r'[*_`]', '', text).replace('’', "'").replace('−', '-')


def nodes(calls):
    found={}
    for call in calls:
        result=call.get('result',{})
        if 'error' in result:continue
        for node in result.get('facts',[])+result.get('metrics',[]):
            m=re.fullmatch(r'(.+?)\s+(Q[1-4]|H[12])\s+(.+)',node.get('report_label',''),re.I)
            if m and node.get('status')=='available':
                found[node['report_label']]=dict(node,company=m[1],quarter=m[2].upper(),metric=m[3].lower())
    return list(found.values())


def mentioned(company,text):
    return bool(re.search(r'(?<!\w)'+re.escape(company)+r'(?!\w)',text,re.I))


def lines(content):
    heads={}
    for number,raw in enumerate(report_body(content).splitlines(),1):
        text=clean(raw)
        h=re.match(r'^(#{1,6})\s+(.+)',text)
        if h:
            level=len(h[1]);heads={k:v for k,v in heads.items() if k<level};heads[level]=h[2];continue
        if text.strip() and not text.lstrip().startswith('|'):
            yield number,text,' '.join(heads.values())


def source_owners(values):
    owners={}
    for n in values:
        for cite in n.get('citations',[]):owners.setdefault(cite,set()).add(n['company'])
    return {k:next(iter(v)) for k,v in owners.items() if len(v)==1}


def issue(code,number,claim,evidence,action):
    return dict(code=code,line=number,claim=claim,evidence=evidence,required_action=action)


def margin_records(sources,owners):
    for s in sources:
        owner=owners.get(s['citation'])
        if not owner:continue
        t=normalized(s['text'])
        for m in re.finditer(r'Gross (?:Profit )?Margin\s*:\s*GAAP\s*:[^;]{1,100};\s*Operating\s*\(Non-GAAP\)\s*:\s*(\d+(?:\.\d+)?)\s*(?:percent|%)',t,re.I):
            yield dict(company=owner,value=m[1],citation=s['citation'],source_quote=m[0],metric='non-GAAP gross profit margin')


def growth_records(sources,owners):
    """Read a current/prior-year table row only when its header and math agree."""
    for s in sources:
        owner=owners.get(s['citation']);period=source_period(s)
        if not owner or not period:continue
        text=s['text'];offset=0
        for raw in text.splitlines(keepends=True):
            line=normalized(raw)
            m=re.fullmatch(r'([A-Za-z][A-Za-z &()/\-]{0,70}?)\s+\$?([\d,]+(?:\.\d+)?)\s+\$?([\d,]+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)%.*',line)
            context=normalized(text[max(0,offset-700):offset]);offset+=len(raw)
            if not m:continue
            headers=list(re.finditer(r'(20\d{2})\s+(?:Q[1-4]\s+Fiscal\s+)?(20\d{2})\s+Change',context,re.I))
            if not headers:continue
            h=headers[-1]
            if int(h[1])-int(h[2])!=1:continue
            if not re.search(r'(?:first|second|third|fourth)\s+quarter|Q[1-4]\s+Fiscal',context,re.I):continue
            a,b,pct=(Decimal(m[i].replace(',','')) for i in (2,3,4))
            if b<=0 or abs((a-b)/b*100-pct)>Decimal('0.51'):continue
            label=re.sub(r'\s*\([^)]*\)','',m[1]).strip()
            if len(label)<3:continue
            yield dict(company=owner,quarter='Q'+str(period[1]),fiscal_year=period[0],label=label,value=str(pct),current_value=str(a),prior_year_value=str(b),
                       citation=s['citation'],source_quote=line,header_quote=context[h.start():],basis='year-over-year')


def period_records(sources,owners):
    """Conservative bounds: three calendar months are at most 93 days.

The bound can establish definite nonoverlap without inventing a fiscal start
for an issuer whose statement says months rather than a precise week count.
"""
    months=r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+20\d{2}'
    duration=r'(\d+|three|twelve|sixteen|thirteen)\s*[- ]\s*(weeks?|months?)'
    words={'three':3,'twelve':12,'sixteen':16,'thirteen':13}
    for s in sources:
        owner=owners.get(s['citation']);period=source_period(s)
        if not owner or not period:continue
        t=normalized(s['text']);candidates=[]
        for m in re.finditer(duration,t,re.I):
            count=words.get(m[1].lower(),int(m[1]) if m[1].isdigit() else 0)
            if not 1<=count<=16:continue
            unit=m[2].lower();days=count*7 if unit.startswith('week') else count*31
            if days>120:continue
            tail=t[m.end():m.end()+230]
            # A table may put a year-to-date header before its first date.
            if not re.search(r'\bended\b',tail,re.I):continue
            dm=re.search(months,tail,re.I)
            if not dm:continue
            end=next(iter(dates_in(dm[0])),None)
            if end is None:continue
            candidates.append(dict(company=owner,quarter='Q'+str(period[1]),end=end,
                earliest_start=end-timedelta(days=days-1),citation=s['citation'],source_quote=t[m.start():m.end()+dm.end()],bound_days=days))
        # Multiple statement sections must agree on the current period end.
        if candidates:
            first=candidates[0]
            yield first


def validate_narrative(content,calls,sources):
    values=nodes(calls);owners=source_owners(values);companies=sorted({n['company'] for n in values})
    margins=list(margin_records(sources,owners));growth=list(growth_records(sources,owners));periods=list(period_records(sources,owners))
    issues=[]
    for number,text,head in lines(content):
        context=text+' '+head
        for record in margins:
            if not mentioned(record['company'],context):continue
            for m in re.finditer(r'\boperating\s*(?:\(non-GAAP\)\s*)?margin\b[^.;\n]{0,45}?(\d+(?:\.\d+)?)\s*%',text,re.I):
                if Decimal(m[1])!=Decimal(record['value']):continue
                prefix=text[max(0,m.start()-25):m.start()]
                if re.search(r'\b(?:not|isn.t|rather than)\s*$',prefix,re.I):continue
                # Only use the cited source when the sentence specifies one.
                cited=re.findall(r'\[S\d+\]',text)
                if cited and record['citation'] not in cited:continue
                issues.append(issue('narrative_metric_label',number,text,[record],
                    'Preserve the full source metric: '+record['metric']+'. Correct this label wherever repeated; do not describe a gross margin as an operating margin.'))
        for qoq in re.finditer(r'\bquarter[- ]over[- ]quarter\b|\bQoQ\b|\bsequential(?:ly)?\b',text,re.I):
            # Restrict the predicate to its clause; another clause may correctly
            # discuss a different year-over-year observation.
            start=max(text.rfind(';',0,qoq.start()),text.rfind(' but ',0,qoq.start()),text.rfind('. ',0,qoq.start()))
            start=0 if start<0 else start+1
            end=min([i for sep in [';', '. ', ' but '] if (i:=text.find(sep,qoq.end()))>=0] or [len(text)])
            clause=text[start:end]
            if re.search(r'year[- ]over[- ]year|YoY',clause,re.I):continue
            quarters=set(re.findall(r'\bQ[1-4]\b',clause+' '+head,re.I))
            for record in growth:
                if not mentioned(record['company'],context) or (quarters and record['quarter'] not in quarters):continue
                pat=r'\b'+re.escape(record['label'])+r'\b[^,;().%]{0,55}?([+-]?\d+(?:\.\d+)?)\s*%'
                for m in re.finditer(pat,clause,re.I):
                    if Decimal(m[1])!=Decimal(record['value']):continue
                    q=int(record['quarter'][1]);prior_q='Q'+str(q-1 if q>1 else 4);prior_year=record['fiscal_year']-(q==1)
                    previous=[r for r in growth if r['company']==record['company'] and r['label']==record['label'] and r['quarter']==prior_q and r['fiscal_year']==prior_year]
                    # A YoY and QoQ percentage can legitimately coincide. A
                    # contradictory sequential claim needs actual prior-quarter
                    # inputs, not just a matching percentage in a YoY table.
                    if len(previous)!=1 or Decimal(previous[0]['current_value'])<=0:continue
                    actual=(Decimal(record['current_value'])/Decimal(previous[0]['current_value'])-1)*100
                    digits=len(m[1].split('.')[1]) if '.' in m[1] else 0
                    if actual.quantize(Decimal(1).scaleb(-digits),rounding=ROUND_HALF_UP)==Decimal(m[1]):continue
                    proof=dict(previous[0],computed_quarter_over_quarter_percent=str(actual))
                    issues.append(issue('narrative_growth_basis',number,text,[record,proof],
                        'This source percentage is year-over-year. The actual prior-quarter input gives a different sequential change. Correct the comparison basis wherever repeated, or use a correctly calculated sequential figure.'))
        if re.search(r'\boverlap(?:ping|s)?\b',text,re.I) and re.search(r'\bQ[1-4]\b|quarters?|periods?|windows?',text,re.I):
            if not re.search(r'\b(?:not|never|no)\s+(?:\w+\s+){0,2}overlap|non[- ]overlap',text,re.I):
                named=[c for c in companies if mentioned(c,context)]
                if not named and len(companies)==2:named=companies
                qs=set(q.upper() for q in re.findall(r'\bQ[1-4]\b',text,re.I))
                explicit=re.search(r'\boverlap(?:ping|s)?\s+(Q[1-4])\b',text,re.I)
                if explicit:qs={explicit[1].upper()}
                if len(named)==2 and len(qs)==1:
                    pair=[]
                    for company in named:
                        matches=[p for p in periods if p['company']==company and p['quarter'] in qs]
                        if len(matches)==1:pair.append(matches[0])
                    if len(pair)==2 and (pair[0]['end']<pair[1]['earliest_start'] or pair[1]['end']<pair[0]['earliest_start']):
                        proof=[{k:(v.isoformat() if k in ['end','earliest_start'] else v) for k,v in p.items()} for p in pair]
                        issues.append(issue('narrative_period_overlap',number,text,proof,
                            'The quoted end dates and duration bounds establish disjoint periods. Remove the overlap claim; state the actual reporting dates and explain that like-labelled fiscal quarters are not contemporaneous.'))
        if 'revenue' not in text.lower() and 'sales' not in text.lower():continue
        for ratio in re.finditer(r'(?<![\w.])(\d+(?:\.\d+)?)\s*(?:x\b|times\b)',text,re.I):
            named=sorted([(m.start(),c) for c in companies for m in re.finditer(r'(?<!\w)'+re.escape(c)+r'(?!\w)',text,re.I)])
            left=[c for pos,c in named if pos<ratio.start()];right=[c for pos,c in named if ratio.end()<=pos<ratio.end()+60]
            if not left:continue
            b=right[0] if right else None
            a=next((c for c in reversed(left) if c!=b),None) if b else left[-1]
            if a is None:continue
            if b is None:
                unique=list(dict.fromkeys(c for _,c in named))
                if len(unique)!=2:continue
                a,b=unique
            before=text[:ratio.start()]
            clause_start=max(before.rfind('. '),before.rfind(';'),before.rfind(':'),before.rfind(', and '))
            local_q=re.findall(r'\b(?:Q[1-4]|H[12])\b',before[max(0,clause_start):],re.I)
            if len(set(local_q))==1:qs={local_q[-1].upper()}
            elif re.search(r'each quarter|both quarters',text,re.I):
                qs={n['quarter'] for n in values if n['company']==a and n['quarter'].startswith('Q')} & {n['quarter'] for n in values if n['company']==b and n['quarter'].startswith('Q')}
            else:
                mentioned_q=re.findall(r'\b(?:Q[1-4]|H[12])\b',before,re.I)
                after_q=re.findall(r'\b(?:Q[1-4]|H[12])\b',text[ratio.end():],re.I)
                qs={mentioned_q[-1].upper()} if mentioned_q else {after_q[0].upper()} if after_q else {'H2'} if re.search(r'second.half',text,re.I) else set()
            expected=[]
            for q in sorted(qs):
                x=[n for n in values if n['company']==a and n['quarter']==q and n['metric'] in ['revenue','net sales']]
                y=[n for n in values if n['company']==b and n['quarter']==q and n['metric'] in ['revenue','net sales']]
                if len(x)!=1 or len(y)!=1 or x[0].get('display_unit',x[0]['unit'])!=y[0].get('display_unit',y[0]['unit']):continue
                numerator=Decimal(x[0].get('display_value',x[0]['value']));denominator=Decimal(y[0].get('display_value',y[0]['value']))
                if denominator<=0:continue
                actual=numerator/denominator;digits=len(ratio[1].split('.')[1]) if '.' in ratio[1] else 0
                rounded=actual.quantize(Decimal(1).scaleb(-digits),rounding=ROUND_HALF_UP)
                expected.append(dict(period=q,numerator=x[0]['report_label'],denominator=y[0]['report_label'],inputs=[str(numerator),str(denominator)],ratio=str(actual),rounded=str(rounded),citations=list(dict.fromkeys(x[0]['citations']+y[0]['citations']))))
            if expected and any(Decimal(e['rounded'])!=Decimal(ratio[1]) for e in expected):
                issues.append(issue('narrative_ratio',number,text,expected,
                    'Recompute this ratio from the displayed numerator and denominator, and preserve its period. Use the supplied rounded ratios; do not use one quarterly ratio for both quarters when they differ.'))
    # One issue per line/type is sufficient feedback; preserve all supporting rows.
    merged={}
    for item in issues:
        key=(item['code'],item['line'])
        if key in merged:merged[key]['evidence'].extend(e for e in item['evidence'] if e not in merged[key]['evidence'])
        else:merged[key]=item
    return list(merged.values())
