"""Deterministic checks for explicit source-period rules and labelled results.

This checks supported presentation structures, not unrestricted prose entailment.
Source publication dates and mentions of comparative periods are not source periods.
"""
from decimal import Decimal
import re

def citation_id(value):
    if not isinstance(value,str):return value
    match=re.fullmatch(r'(?:\[S[1-9]\d*\]|S[1-9]\d*)',value.strip(),re.I)
    return '['+match[0].strip('[]').upper()+']' if match else value

def fiscal_period(text):
    if not isinstance(text,str):return None
    text=text.replace('–','-')
    patterns=[r'\bQ([1-4])\s*(?:[- ]*FY\s*)?(20\d{2}|\d{2})\b',
              r'\bFY\s*(20\d{2}|\d{2})\s*Q([1-4])\b']
    for index,pattern in enumerate(patterns):
        match=re.search(pattern,text,re.I)
        if match:
            q,year=(match[1],match[2]) if index==0 else (match[2],match[1])
            return (int('20'+year if len(year)==2 else year),int(q))
    match=re.search(r'\b(first|second|third|fourth)[ -]quarter(?:\s+and\s+(?:full\s+year|fiscal))?\s+(?:fiscal\s+)?(20\d{2})\b',text,re.I)
    if match:return (int(match[2]),['first','second','third','fourth'].index(match[1].lower())+1)
    return None

def source_period(source):
    year,q=source.get('fiscal_year'),source.get('fiscal_quarter')
    if type(year)is int and type(q)is int and 2000<=year<=2099 and 1<=q<=4:return year,q
    # Titles and issuer URL paths may identify the release. Body text contains
    # prior-year and prior-quarter comparatives, so it is deliberately excluded.
    period=fiscal_period(source.get('title',''))
    if period:return period
    url=source.get('source_url') or ''
    match=re.search(r'fy[-_/](20\d{2})[-_/]q([1-4])\b',url,re.I)
    if match:return int(match[1]),int(match[2])
    return None

def source_policy(task):
    patterns=[r"quarter(?:'|’)?s\s+own\s+(?:contemporaneous\s+)?(?:quarter\s+)?release",
              r'each\s+quarter[^.]{0,60}\bown\s+(?:contemporaneous\s+)?release',
              r"compan(?:y|ies)(?:'|’)?s?\s+own\s+release\s+for\s+(?:that|the|each)\s+quarter",
              r'(?:本|每个|各个)季度[^。]{0,20}(?:原始|对应|当季)(?:[^。]{0,12})(?:发布稿|财报|报告)']
    for pattern in patterns:
        match=re.search(pattern,task,re.I)
        if match:return {'own_quarter_release':True,'origin':'explicit_user_request','matched_text':match[0]}
    return {'own_quarter_release':False,'origin':'not_requested'}

def requests_calculation(task):
    text=re.sub(r'\b(?:do not|don\x27t|never)\s+(?:calculate|compute)[^.]*','',task,flags=re.I)
    text=re.sub(r'(?:不要|无需|不需要)计算[^。]*','',text)
    return bool(re.search(r'\b(?:calculate|compute)\b|\bsum of (?:the )?displayed\b|\bas the sum of\b|计算|汇总|增长率',text,re.I))

def source_eligibility(period,citations,sources,policy):
    if not policy.get('own_quarter_release'):return None
    expected=fiscal_period(period)
    if expected is None:return {'status':'unverified_source_period','reason':'Use an explicit fiscal quarter and year for this own-release requirement.'}
    by_id={s['citation']:s for s in sources};observed=[]
    for cite in citations:
        source=by_id.get(citation_id(cite))
        if source:
            found=source_period(source);observed.append({'citation':source['citation'],'period':list(found) if found else None})
    if any(o['period']==list(expected) for o in observed):return None
    return {'status':'ineligible_source_period','reason':'The requested quarter requires its own release; a later release comparative column is not eligible.',
            'expected_period':list(expected),'observed_sources':observed}

def normal_label(text):
    return re.sub(r'\s+',' ',re.sub(r'[*_`]', '',text)).strip().casefold()

def report_rows(content):
    rows=[];header=''
    body=re.split(r'^#{1,2}[ \t]+Sources[ \t]*$',content,maxsplit=1,flags=re.M)[0]
    for number,line in enumerate(body.splitlines(),1):
        if line.strip().startswith('|'):
            cells=[s.strip() for s in line.strip().strip('|').split('|')]
            if len(cells)>=2 and not re.search(r'\d',cells[1]) and re.search(r'\b(?:USD|EUR|GBP|million|billion|percent)\b',cells[1],re.I):header=cells[1]
            if len(cells)>=2 and not all(re.fullmatch(r'[:\- ]*',s) for s in cells):
                rows.append({'line':number,'label':normal_label(cells[0]),'value':cells[1],'text':line,'header_unit':header,'format':'table'})
        else:
            if not line.strip():header=''
            match=re.match(r'^\s*(?:[-*]\s+)?(?:\*\*)?([^:：\n]{1,120}?)(?:\*\*)?[:：]\s*(.+)$',line)
            if match:rows.append({'line':number,'label':normal_label(match[1]),'value':match[2],'text':line,'format':'labelled_line'})
    return rows

def unavailable(value):
    return bool(re.search(r'\b(unavailable|undefined|not available|not provided|not disclosed|not calculable|cannot|n/?a)\b|\bno (?:own )?(?:contemporaneous )?(?:quarter )?release\b|\b(?:release|source|evidence) (?:is )?(?:absent|missing)\b|无法确定|无法计算|不可用',value,re.I))

def result_matches(value,node,header_unit=''):
    if 'display_value' in node:
        node={**node,'value':node['display_value'],'unit':node['display_unit']}
    value=re.sub(r'\[S\d+\]','',value).replace('−','-')
    if node['status'] in {'unavailable','undefined_zero_baseline'}:return unavailable(value)
    if node['status']!='available':return False
    if unavailable(value):return False
    # Match the leading displayed quantity; a parenthetical original figure may
    # legitimately use a different scale. Header units remain a separate check.
    primary=re.split(r'[(（;]|,(?!\d)',value,maxsplit=1)[0]
    unit_text=primary+' '+header_unit
    if node.get('unit')=='input_id':
        expected=node['selected_ids']
        labels=node.get('selected_labels',expected)
        candidates=node.get('candidate_labels',dict(zip(expected,labels)))
        observed={id for id,rendered in candidates.items() if any(re.search(r'(?<![\w])'+re.escape(label)+r'(?![\w])',value,re.I) for label in {id,rendered})}
        return observed==set(expected)
    # Preserve the original unit text for currency checks while keeping a sign
    # written before its currency symbol/code, e.g. -$93.6, in numeric parsing.
    numeric_text=re.sub(r'([+-])\s*(?:[$€£¥]|USD|EUR|GBP|JPY|CNY|CAD|AUD)\s*(?=\d)',r'\1',value,flags=re.I)
    nums=re.findall(r'(?<![A-Za-z\d])[+-]?\d[\d,]*(?:\.\d+)?',numeric_text)
    if not nums or Decimal(nums[0].replace(',',''))!=Decimal(node['value']):return False
    if 'display_decimal_places' in node:
        places=len(nums[0].split('.')[1]) if '.' in nums[0] else 0
        if places!=node['display_decimal_places']:return False
    unit=node.get('unit','').lower()
    currencies=re.findall(r'\b(?:USD|EUR|GBP|JPY|CNY|CAD|AUD)\b',unit_text,re.I)
    expected_currency=re.search(r'\b(?:usd|eur|gbp|jpy|cny|cad|aud)\b',unit)
    if expected_currency and any(c.lower()!=expected_currency[0] for c in currencies):return False
    if unit=='percent' and not re.search(r'%|percent|百分',unit_text,re.I):return False
    expected_scale=re.search(r'\b(thousand|million|billion|trillion)s?\b',unit)
    scales=re.findall(r'\b(thousand|million|billion|trillion)s?\b',unit_text,re.I)
    if expected_scale and any(scale.lower()!=expected_scale[1] for scale in scales):return False
    if 'billion' in unit and re.search(r'\d\s*[mMtT]\b',unit_text):return False
    return True

def validate_report(content,sources,calls,policy):
    rows=report_rows(content);issues=[];checks=[];bindings={}
    for call in calls:
        result=call['result']
        if 'error' in result:continue
        for node in result.get('facts',[])+result.get('metrics',[]):
            label=node.get('report_label')
            if label:bindings[normal_label(label)]=node
    for label,node in bindings.items():
        matched=[r for r in rows if r['label']==label]
        # The table is the canonical result when provided. A same-labelled
        # prose line can describe its source, original precision or formula.
        # Prose entailment is outside this check; standalone values remain
        # supported when there is no table for that label.
        tables=[r for r in matched if r['format']=='table']
        if tables:matched=tables
        if not matched:
            issues.append({'code':'missing_calculated_row','label':node['report_label'],'expected':node.get('value'),
                           'required_action':'Include the labelled result in a Markdown table or a standalone Label: value line.'})
        for row in matched:
            passed=result_matches(row['value'],node,row.get('header_unit',''))
            checks.append({'label':node['report_label'],'line':row['line'],'passed':passed})
            if not passed:
                issue={'code':'calculation_result_mismatch','label':node['report_label'],'line':row['line'],
                    'observed':row['value'],'expected_status':node['status'],'expected':node.get('value'),'unit':node.get('unit'),
                    'required_action':'Use the latest tool result. If the inputs were wrong, correct the calculation plan first.'}
                # Diagnose the unit alone only when adding it makes the exact
                # existing validator pass. A wrong number remains a mismatch.
                if node.get('unit')=='percent' and result_matches(row['value']+'%',node,row.get('header_unit','')):
                    issue.update(code='missing_percent_unit',expected_display=node['value']+'%',
                        required_action=f"Replace this row's Result cell with {node['value']}%. A percent sign in the Basis/formula cell or surrounding prose does not supply the Result cell's unit. Keep the numeric magnitude; do not multiply by100 again.")
                elif node.get('normalization'):
                    issue.update(expected_display=str(node.get('value'))+' '+node.get('unit',''),
                        required_action='Use the normalized fact value returned by the tool, not original_value. Keep the original value only as an explicitly labelled source note; use normalized inputs for dependent calculations.')
                if 'display_value' in node:
                    issue.update(expected=node['display_value'],unit=node['display_unit'],
                        expected_display=node['display_value']+' '+node['display_unit'],
                        required_action='Use display_value and display_unit exactly, including the requested decimal places. Keep original_value/value for provenance and the declared calculation basis; do not substitute them for the displayed quantity.')
                issues.append(issue)
    if policy.get('own_quarter_release'):
        for row in rows:
            if fiscal_period(row['label']) is None or unavailable(row['value']):continue
            # Inspect a primary numeric value, not a year buried in an
            # explanatory gap sentence. Free prose entailment is out of scope.
            if not re.match(
                    r'^\s*(?:about\s+|approximately\s+|[~≈]\s*)?(?:(?:USD|EUR|GBP|JPY|CNY|CAD|AUD)|[$€£¥])?\s*[+-]?\d',
                    re.sub(r'[*_`]', '',row['value']),re.I):continue
            if not re.search(r'\d',row['value']):continue
            cites=re.findall(r'\[S\d+\]',row['text'])
            failed=source_eligibility(row['label'],cites,sources,policy)
            if failed:issues.append({'code':'source_period_mismatch','line':row['line'],'label':row['label'],**failed,
                                     'required_action':'Cite this quarter\'s own retrieved release or mark the value unavailable; do not substitute a later release.'})
    return {'passed':not issues,'issues':issues,'labelled_result_checks':checks,'bound_labels':sorted(bindings),
            'source_policy':policy,'scope':'Canonical table results (labelled lines when no table exists) and explicit own-quarter-release rule; not unrestricted prose entailment or input-value truth.'}


def validate_sections(content, required):
    """Reject missing/empty sections and literal drafting placeholders.

    No arbitrary minimum length, or claim of semantic completeness.
    """
    text=re.sub(r'^```[^\n]*\n.*?^```[^\n]*$', '', content, flags=re.M|re.S)
    headings=list(re.finditer(r'^##[ \t]+([^\n]+?)[ \t]*$',text,re.M))
    issues=[]
    for title in required:
        found=[(i,h) for i,h in enumerate(headings) if h[1].strip()==title]
        if not found:
            issues.append(dict(code='missing_section',section=title,required_action='Include this required level-two section with substantive content or an evidence-based explanation of unavailable information.'))
            continue
        for i,h in found:
            body=text[h.end():headings[i+1].start() if i+1<len(headings) else len(text)]
            cleaned=re.sub(r'^#{3,6}[^\n]*','',body,flags=re.M)
            cleaned=re.sub(r'\[S\d+\]|[*_`#|\-\s]','',cleaned)
            if not cleaned or re.fullmatch(r'(?:x+|todo|tbd|placeholder|\.\.\.|待补充|待填写)[.!。]?',cleaned,re.I):
                issues.append(dict(code='empty_or_placeholder_section',section=title,
                    required_action='Replace the empty or placeholder section with supported report content; if evidence is missing, state what cannot be established. Preserve other valid sections.'))
    return issues
