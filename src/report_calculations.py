"""Bounded Decimal calculations and per-metric evidence dependencies.

The caller selects facts, units and dependency membership. This module validates
source identities and arithmetic, not the semantic truth of extracted facts.
No expressions, code execution, network access or implicit missing-to-zero cast.
"""
from decimal import Decimal, ROUND_HALF_UP, localcontext
import re
from report_validation import citation_id, source_eligibility, fiscal_period
from calculation_precision import normalize, unit_scale

CALCULATION_TOOL = 'calculate_report_metrics'
CALCULATION_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['facts', 'metrics'],
    'properties': {
        'facts': {'type': 'array', 'minItems': 1, 'maxItems': 64, 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['id', 'value', 'unit', 'period', 'citations'],
            'properties': {
                'id': {'type': 'string', 'description': 'Unique ID, e.g. Q1.'},
                'value': {'type': ['string','null'], 'description': 'Exact decimal input in the stated unit. If unavailable, null; never zero. Use displayed rounded values when the user requests calculations from displayed values.'},
                'unit': {'type': 'string', 'description': 'Consistent unit across an operation, e.g. USD billions.'},
                'period': {'type': 'string', 'description': 'Fiscal period of this fact, e.g. Q1 FY2024.'},
                'report_label': {'type': 'string','description':'Exact table row or Label: value label for this fact in the final report. Omit only for undisplayed intermediate inputs.'},
                'source_quote': {'type':'string','description':'Verbatim contiguous passage from a cited source containing the ORIGINAL numeric token. Copy the original amount into value, removing commas only; never pre-round or rescale it.'},
                'unit_quote': {'type':'string','description':'Verbatim scale/header from the same cited source when source_quote lacks the unit, e.g. (In millions).'},
                'normalization': {'type':'object','additionalProperties':False,'required':['unit','decimal_places'],
                    'description':'Only when the user requires calculations from rounded/displayed inputs: supply the ORIGINAL value and unit above; the tool converts its scale and rounds deterministically. Omit to preserve input precision.',
                    'properties':{'unit':{'type':'string'},'decimal_places':{'type':'integer','minimum':0,'maximum':8}}},
                'citations': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Existing [S#] evidence IDs supporting the value. Empty for unavailable facts.'}}}},
        'metrics': {'type': 'array', 'minItems': 1, 'maxItems': 64, 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['id', 'operation', 'inputs', 'decimal_places'],
            'properties': {
                'id': {'type': 'string', 'description': 'Unique metric ID, e.g. H1.'},
                'report_label': {'type': 'string','description':'Exact row label to use in the report, e.g. H1 revenue. Provide for every requested result.'},
                'operation': {'type': 'string', 'enum': ['sum','difference','percent_change','argmax','argmin']},
                'inputs': {'type': 'array','minItems': 1,'maxItems': 64,'items': {'type': 'string'},
                    'description': 'Fact or metric IDs actually needed for THIS metric. difference=[left,right]; percent_change=[base,current]. Include all required candidates for argmax/argmin, including missing ones.'},
                'decimal_places': {'type': 'integer','minimum': 0,'maximum': 8}}}}
    }
}

def calculate_metrics(facts, metrics, sources, *, policy=None, input_policy=None, display_policy=None):
    if not isinstance(facts,list) or not isinstance(metrics,list) or not (1<=len(facts)<=64 and 1<=len(metrics)<=64):
        raise ValueError('Use 1–64 facts and 1–64 metrics')
    ids=set();nodes={};results={};known={s['citation'] for s in sources}
    for node in facts+metrics:
        id=node.get('id') if isinstance(node,dict) else None
        if not isinstance(id,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,47}',id) or id in ids:
            raise ValueError('Node IDs must be unique simple identifiers')
        ids.add(id);nodes[id]=node
    labels=[n.get('report_label') for n in facts+metrics if n.get('report_label')]
    if any(not isinstance(label,str) for label in labels) or len(set(s.casefold().strip() for s in labels))!=len(labels):
        raise ValueError('Report labels must be distinct strings within a calculation plan')
    for f in facts:
        if set(f)-{'report_label','normalization','source_quote','unit_quote'}!={'id','value','unit','period','citations'}:
            raise ValueError('Fact requires id, value, unit, period and citations only')
        if any(not isinstance(f[k],str) or not (1<=len(f[k])<=120) for k in ('unit','period')):
            raise ValueError('Fact unit and period must be nonempty bounded text')
        cites=f['citations']
        if not isinstance(cites,list) or len(cites)>64 or any(not isinstance(c,str) for c in cites):
            raise ValueError('Invalid citation list')
        cites=[citation_id(c) for c in cites]
        label=f.get('report_label')
        if label is not None and (not isinstance(label,str) or not 1<=len(label)<=120):raise ValueError('report_label must be bounded nonempty text')
        base=dict(id=f['id'],unit=f['unit'],period=f['period'],citations=sorted(set(cites)),leaf_inputs=[f['id']])
        if label:base['report_label']=label
        normalization=f.get('normalization')
        if input_policy and input_policy.get('scope')!='displayed_quarter_sum' and fiscal_period(f['period']) is not None:
            required={k:input_policy[k] for k in ('unit','decimal_places')}
            if normalization is not None and normalization!=required:
                raise ValueError('Fact normalization conflicts with the explicit user input-precision contract')
            normalization=required
        value=f['value']
        if value is not None and (not isinstance(value,str) or not re.fullmatch(r'[+-]?\d{1,24}(?:\.\d{1,12})?',value)):
            raise ValueError('Values must be bounded plain decimal strings, without commas or exponent notation')
        if normalization is not None:
            value=normalize(value,f['unit'],normalization)
            base.update(unit=normalization['unit'],original_value=f['value'],original_unit=f['unit'],
                        normalization={**normalization,'rounding':'ROUND_HALF_UP'})
        if f['value'] is None:
            results[f['id']]=dict(base,status='unavailable',value=None,missing_inputs=[f['id']])
        else:
            if not cites or not set(cites)<=known:
                results[f['id']]=dict(base,status='invalid_source',value=None,invalid_inputs=[f['id']])
            elif (failure:=source_eligibility(f['period'],cites,sources,policy or {})):
                results[f['id']]=dict(base,status=failure['status'],value=None,invalid_inputs=[f['id']],source_check=failure)
            else:
                results[f['id']]=dict(base,status='available',value=value,_number=Decimal(value))
    metric_ids={m['id'] for m in metrics}
    for m in metrics:
        if set(m)-{'report_label'}!={'id','operation','inputs','decimal_places'}:
            raise ValueError('Metric requires id, operation, inputs and decimal_places only')
        if m['operation'] not in {'sum','difference','percent_change','argmax','argmin'}:
            raise ValueError('Unknown operation')
        inputs=m['inputs'];places=m['decimal_places']
        if not isinstance(inputs,list) or not 1<=len(inputs)<=64 or any(not isinstance(i,str) or i not in ids for i in inputs):
            raise ValueError('Declare each dependency as a fact or metric, including unavailable facts')
        if len(set(inputs))!=len(inputs):
            raise ValueError('Duplicate operands are not allowed; avoid double-counting evidence')
        if m['operation'] in {'difference','percent_change'} and len(inputs)!=2:
            raise ValueError('Difference and percent_change require exactly two ordered operands')
        if type(places) is not int or not 0<=places<=8:
            raise ValueError('decimal_places must be 0–8')
        if 'report_label' in m and (not isinstance(m['report_label'],str) or not 1<=len(m['report_label'])<=120):raise ValueError('report_label must be bounded nonempty text')
    visiting=set()
    def resolve(id):
        if id in results:return results[id]
        if id in visiting:raise ValueError('Cyclic calculation dependency')
        visiting.add(id);m=nodes[id];children=[resolve(i) for i in m['inputs']];visiting.remove(id)
        # A request to sum displayed quarters applies to this operation only.
        # Keep the original facts for independent ratios/growth calculations,
        # including when both operations share the very same fact IDs.
        operand_normalization=[]
        if input_policy and input_policy.get('scope')=='displayed_quarter_sum' and m['operation']=='sum':
            periods=[fiscal_period(c.get('period','')) for c in children]
            wanted={q.upper() for q in input_policy['quarters']}
            if all(p is not None for p in periods) and {'Q'+str(p[1]) for p in periods}==wanted:
                spec={k:input_policy[k] for k in ('unit','decimal_places')};adjusted=[]
                for c in children:
                    if c['status']=='available':
                        value=normalize(c['value'],c['unit'],spec)
                        operand_normalization.append(dict(id=c['id'],original_value=c['value'],original_unit=c['unit'],value=value,**spec))
                        c={**c,'value':value,'unit':spec['unit'],'_number':Decimal(value)}
                    adjusted.append(c)
                children=adjusted
        base=dict(id=id,operation=m['operation'],inputs=m['inputs'],decimal_places=m['decimal_places'],
            leaf_inputs=sorted({leaf for c in children for leaf in c['leaf_inputs']}),
            citations=sorted({cite for c in children for cite in c['citations']}))
        if m.get('report_label'):base['report_label']=m['report_label']
        if operand_normalization:base['operand_normalization']=operand_normalization
        missing=sorted({i for c in children for i in c.get('missing_inputs',[])})
        invalid=sorted({i for c in children if c['status'] not in {'available','unavailable'} for i in c.get('invalid_inputs',c['leaf_inputs'])})
        if invalid:
            result=dict(base,status='blocked_invalid_input',value=None,invalid_inputs=invalid,missing_inputs=missing)
        elif missing:
            result=dict(base,status='unavailable',value=None,missing_inputs=missing)
        elif len({c['unit'] for c in children})!=1 or any('_number' not in c for c in children):
            result=dict(base,status='invalid_units_or_operand',value=None,invalid_inputs=base['leaf_inputs'])
        else:
            numbers=[c['_number'] for c in children];op=m['operation'];unit=children[0]['unit']
            if op=='percent_change' and numbers[0]==0:
                result=dict(base,status='undefined_zero_baseline',value=None,invalid_inputs=base['leaf_inputs'])
            elif op in {'argmax','argmin'}:
                target=(max if op=='argmax' else min)(numbers)
                selected=[i for i,n in zip(m['inputs'],numbers) if n==target]
                result=dict(base,status='available',value=selected[0] if len(selected)==1 else selected,
                            unit='input_id',selected_ids=selected,
                            selected_labels=[results[i].get('report_label') or results[i].get('period') or i for i in selected],
                            candidate_labels={i:results[i].get('report_label') or results[i].get('period') or i for i in m['inputs']},tie=len(selected)>1)
            else:
                with localcontext() as ctx:
                    ctx.prec=80
                    n=sum(numbers) if op=='sum' else numbers[0]-numbers[1] if op=='difference' else (numbers[1]-numbers[0])/numbers[0]*100
                    if abs(n)>Decimal('1e40'):
                        result=dict(base,status='result_out_of_range',value=None,invalid_inputs=base['leaf_inputs'])
                    else:
                        n=n.quantize(Decimal(1).scaleb(-m['decimal_places']),rounding=ROUND_HALF_UP)
                        if n==0:n=abs(n)
                        result=dict(base,status='available',value=format(n,'f'),unit='percent' if op=='percent_change' else unit,_number=n)
        results[id]=result;return result
    for id in metric_ids:resolve(id)
    def clean(r):
        node={k:v for k,v in r.items() if not k.startswith('_')}
        if display_policy and r.get('status')=='available' and r.get('unit') not in {'percent','input_id'}:
            try:
                currency,_=unit_scale(r['unit'])
                target_currency,_=unit_scale(display_policy['unit'])
            except ValueError:
                return node
            if currency==target_currency:
                node.update(display_value=normalize(r['value'],r['unit'],display_policy),
                            display_unit=display_policy['unit'],display_decimal_places=display_policy['decimal_places'])
        return node
    return dict(facts=[clean(results[f['id']]) for f in facts],metrics=[clean(results[m['id']]) for m in metrics],
        arithmetic='Decimal; ROUND_HALF_UP; downstream metrics use displayed rounded intermediate results',
        dependency_rule='Only unavailable or invalid transitive inputs block a metric. Unrelated missing facts never block it.',
        limitation='Citation identities checked against retrieved ledger. Caller-selected values, units, periods, source entailment and dependency membership still require verification.')
