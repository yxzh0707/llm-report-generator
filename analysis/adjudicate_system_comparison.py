"""Separate source-supported disclosed precision from exact reference matching.

The frozen parser outputs remain unchanged. Every non-reference value is checked
against an explicit disclosed alternative, symmetrically for both arms.
"""
import json,re,sys
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'analysis')]
from experiments.system_comparison import P,OLD,read,save,sha,now,norm,ARMS
from evaluate_system_comparison import clean,RUBRIC

def source_alternatives():
    rules=[]
    for g in read(OLD/'source_gold.json'):
        value=Decimal(g['reported_value'])/(1 if g['reported_unit']=='USD billions' else 1000)
        full=(OLD/'corpus'/(g['id']+'.md')).read_text()
        assert norm(g['proof']) in norm(full),g['id']
        rules.append(dict(source_id=g['id'],value=str(value),proof=g['proof'],basis=g['reported_unit'],reason='Original disclosed amount converted to USD billions without rounding; assess requested display precision separately.'))
    for id,value,quote in [
        ('salesforce_q4','10.00','Fourth quarter revenue of $10.0 billion'),
        ('ibm_q3','16.30','Revenue of $16.3 billion'),
        ('ibm_q4','19.70','Revenue of $19.7 billion')]:
        assert quote in norm((OLD/'corpus'/(id+'.md')).read_text())
        rules.append(dict(source_id=id,value=value,proof=quote,basis='USD billions',reason='Same-quarter release explicitly discloses this rounded headline amount. User task did not require the most precise financial-statement figure.'))
    save(P/'value_adjudication_rules.json',{'recorded_utc':now(),'reason':'Frozen exact-reference matching conflates supported alternative precision with incorrect facts. Preserve original matches and separately audit source support and requested display precision, for both arms.','rules':rules})
    return rules

def adjudicate():
    rules=source_alternatives();rs=read(P/'rule_results.json');out=[];changes=[]
    for r in rs:
        folder=P/'runs'/r['run_id'];ledger={s['citation']:s for s in read(folder/'evidence_ledger.json')} if(folder/'evidence_ledger.json').exists() else {}
        facts=[]
        for f in r['facts']:
            x={**f,'reference_match':f['passed'],'display_precision_passed':True,'source_supported':f['passed']}
            if f['value'] is not None and f.get('observed'):
                v=re.sub(r'\[S\d+\]','',f['observed']);nums=re.findall(r'(?<![A-Za-z\d])[+-]?\d[\d,]*(?:\.\d+)?',v)
                x['display_precision_passed']=bool(nums and re.fullmatch(r'[+-]?\d[\d,]*\.\d{2}',nums[0]))
                if nums:
                    n=Decimal(nums[0].replace(',',''));match=next((a for a in rules if a['source_id']==f['source_id'] and Decimal(a['value'])==n),None)
                    citations=f.get('citations',[])
                    grounded=bool(citations) and all(c in ledger and ledger[c]['document_id']==f['source_id'] for c in citations)
                    units_ok=not re.search(r'\b(?:million|trillion|thousand)s?\b|\d\s*[mMtT]\b',v)
                    if not x['source_supported'] and match and grounded and units_ok:
                        x.update(source_supported=True,adjudication=match)
                        changes.append({'run_id':r['run_id'],'item':f['id'],'reference':f['value'],'observed':f['observed'],'source_rule':match,'display_precision_passed':x['display_precision_passed']})
            elif f['value'] is not None:x['display_precision_passed']=False
            facts.append(x)
        derived=[]
        for f in r['derived']:
            company=f['label'].split(' H2')[0].lower();deps=[x for x in facts if x['id'].startswith(company+'_')]
            x={**f,'reference_match':f['passed'],'supported_calculation':f['passed']}
            if f['status']=='conflicting_rows':
                # Compare results, not explanatory suffixes. Equations use the last RHS.
                parsed=[]
                for hit in f['hits']:
                    v=re.sub(r'\[S\d+\]','',hit['value'])
                    if re.search(r'\b(unavailable|not available|not provided|n/?a|cannot calculate)\b',v,re.I):parsed.append('Unavailable');continue
                    rhs=v.rsplit('=',1)[-1] if '=' in v else v
                    m=re.search(r'(?<![A-Za-z\d])[+-]?\d[\d,]*(?:\.\d+)?',rhs)
                    parsed.append(Decimal(m[0].replace(',','')) if m else None)
                if parsed and None not in parsed and len(set(parsed))==1:
                    x.update(observed=str(parsed[0]),extraction_audit='Repeated result identical after separating equations and annotations',status='equivalent_repeated_rows')
                    if f['value'] is None:x['supported_calculation']=parsed[0]=='Unavailable' and all(d['source_supported'] for d in deps)
            if f['value'] is not None and x.get('observed') and all(d['source_supported'] for d in deps):
                def number(s):
                    z=re.sub(r'\[S\d+\]','',s);m=re.search(r'(?<![A-Za-z\d])[+-]?\d[\d,]*(?:\.\d+)?',z)
                    return Decimal(m[0].replace(',','')) if m else None
                ns=[number(d['observed']) for d in deps];observed=number(x['observed'])
                expected=sum(ns).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
                x.update(supported_calculation=observed==expected,display_based_expected=str(expected))
            derived.append(x)
        out.append({**r,'facts':facts,'derived':derived,'source_numeric_complete':r['delivered'] and all(x['source_supported'] for x in facts),
                    'precision_complete':r['delivered'] and all(x['display_precision_passed'] for x in facts)})
    save(P/'adjudicated_rule_results.json',out);save(P/'numeric_adjudications.json',{'utc':now(),'changes':changes,'reports_audited':len(out),
        'scope':'All available runs and both arms; source support distinguished from exact-reference and display compliance. No generator changes or regeneration.'})
    print(json.dumps({'reports':len(out),'supported_alternative_values':len(changes)}))

def finalize():
    rs=read(P/'adjudicated_rule_results.json');js={r['run_id']:r for r in read(P/'judge_results.json')}
    edits=read(P/'semantic_adjudications.json') if(P/'semantic_adjudications.json').exists() else []
    em={(x['run_id'],x['criterion']):x for x in edits};final=[];unresolved=[]
    for r in rs:
        j=js.get(r['run_id'],{});scores={};flagged={x['criterion'] for x in j.get('quote_flags',[])}
        for key in RUBRIC:
            row=next((x for x in j.get('results',[]) if x['id']==key),None);override=em.get((r['run_id'],key))
            if override:scores[key]=override['passed']
            elif row and key not in flagged:scores[key]=row['passed']
            else:unresolved.append({'run_id':r['run_id'],'criterion':key})
        final.append({**r,'semantic':scores,
            'business_complete':r['delivered'] and scores.get('business_A',False) and scores.get('business_B',False),
            'combined_completion':r['source_numeric_complete'] and r['format_passed'] and r['precision_complete'] and scores.get('business_A',False) and scores.get('business_B',False)})
    groups={}
    for arm in ARMS:
        a=[r for r in final if r['arm']==arm];fs=[f for r in a for f in r['facts']];g={
            'reports':len(a),'delivered':sum(r['delivered'] for r in a),'source_numeric_complete':sum(r['source_numeric_complete'] for r in a),
            'quarter_facts_supported':sum(f['source_supported'] for f in fs if f['value'] is not None),'quarter_facts_available':sum(f['value'] is not None for f in fs),
            'missing_correct':sum(f['source_supported'] for f in fs if f['value'] is None),'missing_items':sum(f['value'] is None for f in fs),
            'business_topics_passed':sum(r['semantic'].get(k,False) and r['delivered'] for r in a for k in ['business_A','business_B']),'business_topics':len(a)*2,
            'structure_passed':sum(r['structure_passed'] and r['delivered'] for r in a),'format_passed':sum(r['format_passed'] for r in a),
            'precision_complete':sum(r['precision_complete'] for r in a),'combined_completion':sum(r['combined_completion'] for r in a),
            'word_limit_passed':sum(x['passed'] and r['delivered'] for r in a for x in r['customization']['items'] if x['id']=='depth_words'),
            'word_limit_tasks':sum(x['id']=='depth_words' for r in a for x in r['customization']['items']),
            'derived_correct':sum(x['supported_calculation'] for r in a for x in r['derived']),'derived_items':len(a)*2,
            'tokens':sum((r['usage'] or {}).get('total_tokens') or 0 for r in a),'usage_missing':[r['run_id'] for r in a if (r['usage'] or {}).get('total_tokens') is None],
            'mean_seconds':round(sum(r['elapsed_seconds'] for r in a)/len(a),2),'mean_calls':round(sum(r['model_calls'] for r in a)/len(a),2),
            'semantic':{k:sum(r['semantic'].get(k,False) and r['delivered'] for r in a) for k in RUBRIC},
            'profiles':{p:{'reports':len(b:=[r for r in a if r['profile']==p]),'delivered':sum(r['delivered'] for r in b),'content_complete':sum(r['source_numeric_complete'] and r['business_complete'] for r in b),'format_passed':sum(r['format_passed'] for r in b),'combined_completion':sum(r['combined_completion'] for r in b)} for p in ('brief','standard','detailed','missing')}}
        groups[arm]=g
    save(P/'final_results.json',final);save(P/'final_summary.json',{'updated_utc':now(),'completed_runs':len(rs),'unresolved':len(unresolved),'unresolved_items':unresolved,'groups':groups})
    print(json.dumps({'runs':len(rs),'unresolved':len(unresolved),'groups':groups},ensure_ascii=False))

if __name__=='__main__':
    {'rules':adjudicate,'final':finalize}[sys.argv[1]]()
