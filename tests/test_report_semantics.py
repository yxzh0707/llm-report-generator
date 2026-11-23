import json
import unittest
from report_semantics import validate_narrative


def fixture():
    sources=[];facts=[]
    for i,(company,q,value,body) in enumerate([
        ('Alpha',3,'100','Third Quarter\n2025 2024 Change\nSensors 108 100 +8%\n12 weeks ended March 30, 2025.'),
        ('Alpha',4,'200','Fourth Quarter\n2025 2024 Change\nSensors 126 100 +26%\nThree Months Ended June 30, 2025. Gross Profit Margin: GAAP: 61.0 percent, up 20 basis points; Operating (Non-GAAP): 63.4 percent, up 30 basis points.'),
        ('Beta',3,'80','Third Quarter\n2025 2024 Change\nSensors 100 100 +0%\nThree Months Ended November 30, 2025.'),
        ('Beta',4,'80','Fourth Quarter\n2025 2024 Change\nSensors 120 100 +20%\nThree Months Ended February 28, 2026.'),
    ],1):
        cite=f'[S{i}]';sources.append(dict(citation=cite,title=f'{company} Q{q} FY2025',text=body))
        facts.append(dict(id=str(i),report_label=f'{company} Q{q} revenue',status='available',value=value,unit='USD millions',citations=[cite]))
    return [dict(result=dict(facts=facts,metrics=[]))],sources


def check(text):
    calls,sources=fixture();return validate_narrative(text,calls,sources)


class NarrativeChecks(unittest.TestCase):
    def test_calculation_success_does_not_consume_subsequent_repair_attempts(self):
        import tempfile
        from pathlib import Path
        from runtime_adapter import assemble
        from phase1_request_policy import ReportRequest
        from run_report import DEFAULT_BUDGET
        from test_runtime_integration import ToolFake
        with tempfile.TemporaryDirectory() as td:
            runtime,evidence=assemble(Path(td),ReportRequest(task='Summarize'),None,[],[],None,
                DEFAULT_BUDGET,model=ToolFake(responses=[]))
            evidence.calculation_calls=[{'result':{'metrics':[]}}]*4
            self.assertEqual(evidence.calculation_failures(),0)
            # An independent malformed plan is attempted even after four
            # successes; three consecutive failures still stop repair.
            for n in range(1,4):
                self.assertIn('error',evidence.calculate({}))
                self.assertEqual(evidence.calculation_failures(),n)
            count=len(evidence.calculation_calls)
            self.assertIn('Three consecutive',evidence.calculate({})['error'])
            self.assertEqual(len(evidence.calculation_calls),count)

    def test_uploaded_source_without_url_or_fiscal_period(self):
        calls,sources=fixture()
        sources[0].update(title='Uploaded financial notes',source_url=None)
        self.assertEqual(validate_narrative('Alpha Q3 Sensors grew sequentially by 8%.',calls,sources),[])
        self.assertEqual(validate_narrative('Ordinary summary.',[],sources),[])

    def test_metric_identity_uses_source_hierarchy_not_number_list(self):
        x=check('Alpha reports operating (non-GAAP) margin of 63.4% [S2].')
        self.assertEqual(x[0]['code'],'narrative_metric_label');json.dumps(x)
        self.assertIn('Gross Profit Margin',x[0]['evidence'][0]['source_quote'])
        self.assertEqual(check('Alpha reports operating (non-GAAP) gross margin of 63.4% [S2].'),[])
        self.assertEqual(check('Alpha reports operating margin of 20.0% [S2].'),[])
        self.assertEqual(check('Beta reports operating (non-GAAP) margin of 63.4% [S4].'),[])
        self.assertEqual(check('Alpha reports not operating margin of 63.4% [S2].'),[])

    def test_growth_checks_actual_quarter_inputs(self):
        x=check('Alpha Q4 has quarter-over-quarter momentum (Sensors +26%).')
        self.assertEqual(x[0]['code'],'narrative_growth_basis')
        self.assertEqual(len(x[0]['evidence']),2);json.dumps(x)
        self.assertEqual(check('Alpha Q4 Sensors grew 26% year-over-year.'),[])
        self.assertEqual(check('Alpha Q4 has quarter-over-quarter momentum (Sensors +17%).'),[])
        self.assertEqual(check('Beta Q4 has quarter-over-quarter momentum (Sensors +20%).'),[])

    def test_growth_does_not_guess_when_prior_quarter_absent(self):
        calls,sources=fixture();sources=[s for s in sources if s['citation']!='[S1]']
        self.assertEqual(validate_narrative('Alpha Q4 has quarter-over-quarter momentum (Sensors +26%).',calls,sources),[])

    def test_overlap_proves_disjoint_bounds(self):
        x=check('Alpha and Beta have overlapping Q3 periods; Q4 materials are also available.')
        self.assertEqual(x[0]['code'],'narrative_period_overlap');json.dumps(x)
        self.assertEqual(check('Alpha and Beta Q3 periods do not overlap.'),[])
        self.assertEqual(check('Alpha and Beta have non-overlapping Q3 periods.'),[])
        self.assertEqual(check('Alpha and Beta Q3 periods are not aligned.'),[])
        calls,sources=fixture();sources[2]['text']='Three Months Ended March 30, 2025.'
        self.assertEqual(validate_narrative('Alpha and Beta have overlapping Q3 periods.',calls,sources),[])

    def test_overlap_needs_both_source_periods(self):
        calls,sources=fixture();sources[2]['text']='Released November 30, 2025. No period duration supplied.'
        self.assertEqual(validate_narrative('Alpha and Beta have overlapping Q3 periods.',calls,sources),[])

    def test_ratios_bind_period_orientation_and_display_precision(self):
        self.assertEqual(check("Alpha Q3 revenue was about 1.3x Beta's."),[])
        self.assertEqual(check("Alpha Q4 revenue was about 2.5x Beta's."),[])
        self.assertEqual(check("Beta Q4 revenue was about 0.4x Alpha's."),[])
        x=check("Alpha revenue is roughly 1.3x Beta's in each quarter.")
        self.assertEqual(x[0]['code'],'narrative_ratio')
        self.assertEqual([e['rounded'] for e in x[0]['evidence']],['1.3','2.5'])
        self.assertEqual(check("In both quarters: Alpha's Q3 revenue was 1.3x Beta's, and its Q4 revenue was 2.5x Beta's."),[])
        self.assertEqual(check("Alpha revenue exceeded Beta revenue. The product speed was 3.0x higher."),[])

    def test_ratio_missing_or_zero_denominator_is_not_guessed(self):
        calls,sources=fixture();calls[0]['result']['facts'][3]['value']='0'
        self.assertEqual(validate_narrative("Alpha Q4 revenue was 2.5x Beta's.",calls,sources),[])

    def test_sources_section_is_not_reported_as_a_claim(self):
        self.assertEqual(check('## Sources\nAlpha reports operating (non-GAAP) margin of 63.4% [S2].'),[])


if __name__=='__main__':unittest.main()
