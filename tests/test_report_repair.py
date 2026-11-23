import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from calculation_precision import presentation_policy,input_precision_policy
from report_calculations import calculate_metrics
from report_validation import validate_report,validate_sections

TASK='Use reported revenue, in USD billions to two decimal places. Report H2 as the sum of the displayed Q3 and Q4 values in USD billions to two decimal places.'

class ReportRepairTests(unittest.TestCase):
    def calculate(self,task):
        facts=[dict(id='a',value='63209',unit='USD millions',period='Q3 FY2025',citations=['[S1]'],report_label='A Q3'),
               dict(id='b',value='86161',unit='USD millions',period='Q4 FY2025',citations=['[S2]'],report_label='A Q4')]
        metrics=[dict(id='h',operation='sum',inputs=['a','b'],decimal_places=3,report_label='A H2')]
        return calculate_metrics(facts,metrics,[{'citation':'[S1]'},{'citation':'[S2]'}],
            input_policy=input_precision_policy(task),display_policy=presentation_policy(task))

    def test_displayed_sum_and_originals_preserved(self):
        r=self.calculate(TASK)
        self.assertEqual([f['value'] for f in r['facts']],['63209','86161'])
        self.assertEqual([f['display_value'] for f in r['facts']],['63.21','86.16'])
        self.assertEqual(r['metrics'][0]['operand_normalization'][0]['original_value'],'63209')
        self.assertEqual(r['metrics'][0]['display_value'],'149.37')

    def test_displayed_sum_does_not_round_independent_growth_inputs(self):
        facts=[dict(id='q3',value='963',unit='USD millions',period='Q3 FY2025',citations=['[S1]']),
               dict(id='q4',value='1029',unit='USD millions',period='Q4 FY2025',citations=['[S2]'])]
        metrics=[dict(id='sum',operation='sum',inputs=['q3','q4'],decimal_places=2),
                 dict(id='growth',operation='percent_change',inputs=['q3','q4'],decimal_places=1)]
        sources=[{'citation':'[S1]'},{'citation':'[S2]'}]
        r=calculate_metrics(facts,metrics,sources,input_policy=input_precision_policy(TASK),display_policy=presentation_policy(TASK))
        self.assertEqual(r['metrics'][0]['value'],'1.99')
        self.assertEqual(r['metrics'][1]['value'],'6.9')  # raw; rounded 0.96/1.03 would yield 7.3
        self.assertEqual(r['facts'][0]['value'],'963')
        only_growth=calculate_metrics(facts,metrics[1:],sources,input_policy=input_precision_policy(TASK))
        self.assertEqual(only_growth['metrics'][0]['value'],'6.9')

    def test_displayed_sum_scope_preserves_other_quarters_and_missing_dependencies(self):
        sources=[{'citation':'[S1]'},{'citation':'[S2]'}]
        facts=[dict(id='a',value='963',unit='USD millions',period='Q1 FY2025',citations=['[S1]']),
               dict(id='b',value='1029',unit='USD millions',period='Q2 FY2025',citations=['[S2]'])]
        metrics=[dict(id='sum',operation='sum',inputs=['a','b'],decimal_places=2)]
        r=calculate_metrics(facts,metrics,sources,input_policy=input_precision_policy(TASK))
        self.assertEqual(r['metrics'][0]['value'],'1992.00')
        facts[0]['period']='Q3 FY2025';facts[1].update(period='Q4 FY2025',value=None,citations=[])
        r=calculate_metrics(facts,metrics,sources,input_policy=input_precision_policy(TASK))
        self.assertEqual(r['metrics'][0]['status'],'unavailable')

    def test_display_only_does_not_change_calculation_inputs(self):
        r=self.calculate('Present revenue in USD billions to two decimal places.')
        self.assertEqual(r['facts'][0]['value'],'63209')
        self.assertEqual(r['metrics'][0]['value'],'149370.000')
        self.assertEqual(r['metrics'][0]['display_value'],'149.37')

    def test_precision_is_checked_not_just_numeric_equality(self):
        r=self.calculate(TASK)
        text='| Item | Revenue (USD billions) |\n| A Q3 | 63.21 |\n| A Q4 | 86.16 |\n| A H2 | 149.37 |'
        check=lambda s:validate_report(s,[],[{'result':r}],{})
        self.assertTrue(check(text)['passed'])
        for bad in [text.replace('63.21','63.210'),text.replace('USD billions','USD millions'),text.replace('149.37','149.36')]:
            self.assertFalse(check(bad)['passed'])
            self.assertIn('display_value',check(bad)['issues'][0]['required_action'])

    def test_conflicts_negations_and_unrequested_precision(self):
        for text in ['', 'Write a detailed report.', 'Do not use USD billions to two decimal places.',
                     'Use USD billions to two decimal places. Use USD millions to one decimal place.']:
            self.assertEqual(presentation_policy(text),{})
        self.assertFalse(input_precision_policy('Use USD billions to two decimal places. Do not take the sum of the displayed Q3 and Q4 values.'))

    def test_placeholders_rejected_without_a_word_floor(self):
        for body in ['','x','TODO','### Details\n...']:
            self.assertTrue(validate_sections('## Findings\n'+body,['Findings']))
        self.assertFalse(validate_sections('## Findings\nUnavailable: the Q4 release was not supplied.',['Findings']))
        self.assertFalse(validate_sections('## Findings\nRevenue grew 8% [S1].',['Findings']))

if __name__=='__main__':unittest.main()
