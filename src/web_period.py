"""Conservative opened-release period classification; never infer FY from publication date."""
import re
from urllib.parse import urlparse,unquote
ORDINALS={'first':1,'second':2,'third':3,'fourth':4}

def period_in_label(text):
    text=re.sub(r'\s+',' ',text.replace('-',' '))
    patterns=[(r'\bFY\s*(20\d{2}|\d{2})\s*Q([1-4])\b',False),
              (r'\b(20\d{2})\s*Q([1-4])\b',False),
              (r'\bQ([1-4])\s*(?:(?:FY|Fiscal(?: Year)?)\s*)?(20\d{2}|\d{2})\b',True)]
    for pattern,reverse in patterns:
        m=re.search(pattern,text,re.I)
        if m:
            year,q=(m[2],m[1]) if reverse else (m[1],m[2])
            return (int('20'+year if len(year)==2 else year),int(q))
    m=re.search(r'\b(first|second|third|fourth) quarter(?: and (?:full year|fiscal(?: year)?))? (?:fiscal(?: year)? )?(20\d{2})\b',text,re.I)
    if m:return int(m[2]),ORDINALS[m[1].lower()]
    m=re.search(r'\bfiscal(?: year)? (20\d{2}) (first|second|third|fourth) quarter\b',text,re.I)
    if m:return int(m[1]),ORDINALS[m[2].lower()]
    return None

def classify_release(url,text,*,calendar_fiscal_year=False):
    """Classify the page's own reporting period from its heading/primary lead.

    calendar_fiscal_year is a declared issuer-calendar property, not derived
    from a search query. A directory or earnings-call page is not a release.
    """
    if not isinstance(text,str) or not text.strip():return {'status':'unverified','reason':'empty_text'}
    lines=[s.strip() for s in text.splitlines() if s.strip() and not s.strip().startswith('--- Page')]
    title=lines[0][:300] if lines else ''
    head=re.sub(r'\s+',' ',text[:1800])
    if re.search(r'/(?:metrics|balance-sheets|income-statements|cash-flows)/?$',urlparse(url).path,re.I):
        return {'status':'not_release','reason':'supporting_statement_not_release','title':title}
    if re.search(r'\b(?:to report|will report|earnings call)\b',title,re.I):
        return {'status':'not_release','reason':'announcement_or_event_page','title':title}
    release=bool(re.search(r'\b(?:reports|announces)\b.{0,130}\b(?:quarter|results)\b',title,re.I)
                 or re.search(r'\breleases\s+Q[1-4]\s+FY\s*\d{2,4}\s+earnings\b',title,re.I)
                 or re.search(r'\bFY\s*\d{2,4}\s*Q[1-4]\b',title,re.I)
                 or (text.lstrip().startswith('--- Page') and re.search(r'\b(?:reports|announces|earnings release)\b',head,re.I)))
    sec_exhibit=(urlparse(url).hostname in {'sec.gov','www.sec.gov'} and '/Archives/edgar/data/' in urlparse(url).path)
    if sec_exhibit and re.search(r'\b(?:reports|announces)\b.{0,170}\b(?:quarter|results)\b',head,re.I):release=True
    if not release:return {'status':'not_release','reason':'no_release_heading','title':title}
    candidates=[]
    def add(period,method,quote):
        if period:candidates.append({'period':list(period),'method':method,'quote':quote[:400]})
    add(period_in_label(title),'opened_heading',title)
    # An explicit Results subheading belongs to the current announcement;
    # guidance, comparative table columns and publication dates do not.
    for m in re.finditer(r'^\s*(Q[1-4]\s+FY\s*(?:20\d{2}|\d{2}))\s+Results\s*:',text[:1800],re.I|re.M):
        add(period_in_label(m[1]),'primary_results_subheading',m[0])
    # Fiscal paths/explicit quarter-year filenames are valid, unlike /2025/01 publication paths.
    path=unquote(urlparse(url).path)
    m=re.search(r'\bfy[-_/](20\d{2})[-_/]q([1-4])\b|/(20\d{2})/q([1-4])/|/(20\d{2})q([1-4])',path,re.I)
    if m:
        vals=[v for v in m.groups() if v];add((int(vals[0]),int(vals[1])),'fiscal_url_path',m[0])
    # Original release attachments can encode fiscal periods without a year
    # in the visible heading, e.g. q3-fy25-earnings-release.pdf.
    filename=path.rsplit('/',1)[-1].replace('+',' ').replace('_',' ')
    filename=re.sub(r'(release)(?=fy\d)',r'\1 ',filename,flags=re.I)
    if re.search(r'\.(?:pdf|html?)$',filename,re.I) and re.search(r'\bfy\s*\d',filename.replace('-',' '),re.I):
        add(period_in_label(filename),'fiscal_release_filename',filename)
    # Only the issuer's opening announcement, before comparative narrative/table data.
    lead=re.sub(r'\s+',' ',text[:5000])
    m=re.search(r'(?:announced|announces|reported|reports)\s+(?:the following\s+)?financial results for (?:its |the )?fiscal(?: year)? (20\d{2}) (first|second|third|fourth) quarter',lead,re.I)
    if m:add((int(m[1]),ORDINALS[m[2].lower()]),'explicit_fiscal_lead',m[0])
    if calendar_fiscal_year:
        m=re.search(r'(?:announced|announces|reported|reports) financial results for (?:its |the )?(first|second|third|fourth) quarter ended [A-Za-z]+ \d{1,2},? (20\d{2})',lead,re.I)
        if m:add((int(m[2]),ORDINALS[m[1].lower()]),'primary_period_end_declared_calendar_issuer',m[0])
    if text.lstrip().startswith('--- Page') or sec_exhibit:
        # PDF headings may wrap; do not examine later financial comparison rows.
        m=re.search(r'\b(?:reports|announces)\b.{0,170}\b(?:quarter).{0,60}?\b20\d{2}\b',head,re.I)
        if m:add(period_in_label(m[0]),'pdf_release_heading',m[0])
    unique={tuple(x['period']) for x in candidates}
    # A filename or subheading must not contradict the visible release quarter.
    heading_quarter=re.search(r'\b(?:reports|announces)\b.{0,60}?\b(first|second|third|fourth)[ -]quarter\b',head,re.I)
    if heading_quarter and any(q!=ORDINALS[heading_quarter[1].lower()] for _,q in unique):
        return {'status':'unverified','reason':'conflicting_periods','title':title,'matches':candidates}
    if len(unique)!=1:return {'status':'unverified','reason':'conflicting_periods' if unique else 'period_not_explicit','title':title,'matches':candidates}
    year,q=next(iter(unique))
    return {'status':'classified','fiscal_year':year,'fiscal_quarter':q,'title':title,'matches':candidates}

def inspect_web_source(source,text,scope):
    result=classify_release(source.get('source_url',''),text,calendar_fiscal_year=scope.get('calendar_fiscal_year',False))
    if result['status']!='classified':return {'decision':'quarantine','reason':result['reason'],'classification':result}
    if result['fiscal_year']!=scope['fiscal_year']:
        return {'decision':'exclude','reason':'wrong_fiscal_year','classification':result}
    if result['fiscal_quarter'] not in scope.get('quarters',[1,2,3,4]):
        return {'decision':'exclude','reason':'wrong_fiscal_quarter','classification':result}
    return {'decision':'keep','reason':'target_period_release','classification':result}

def validate_scope(scope):
    if scope is None:return
    if not isinstance(scope,dict) or set(scope)-{'fiscal_year','quarters','calendar_fiscal_year'}:raise ValueError('Invalid web period scope')
    if type(scope.get('fiscal_year'))is not int or not 2000<=scope['fiscal_year']<=2099:raise ValueError('Explicit fiscal year required')
    qs=scope.get('quarters',[1,2,3,4])
    if not isinstance(qs,list) or not qs or any(type(q)is not int or q not in {1,2,3,4} for q in qs):raise ValueError('Invalid fiscal quarters')
    if type(scope.get('calendar_fiscal_year',False))is not bool:raise ValueError('Invalid issuer calendar flag')
