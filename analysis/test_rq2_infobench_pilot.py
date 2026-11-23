import json
import unittest

from analysis.rq2_infobench_pilot import validate_answer, empty_body, questions
from analysis.rq2_infobench_itemwise import extract


class PilotContracts(unittest.TestCase):
    def setUp(self):
        self.packet = {'report':'Revenue increased.', 'sources':[{'citation':'[S1]','text':'Revenue increased.'}],
                       'questions':[{'id':'annual'}]}
        self.answer = {'items':[{'id':'annual','label':'YES','report_quote':'Revenue increased.',
                                'source_id':'[S1]','source_quote':'Revenue increased.','reason':'Evidence agrees.'}]}

    def test_unverifiable_quote_rejected(self):
        validate_answer(json.dumps(self.answer), self.packet)
        self.answer['items'][0]['source_quote'] = 'Revenue doubled.'
        with self.assertRaises(ValueError):
            validate_answer(json.dumps(self.answer), self.packet)

    def test_duplicate_and_missing_ids_rejected(self):
        self.answer['items'] *= 2
        with self.assertRaises(ValueError):
            validate_answer(json.dumps(self.answer), self.packet)

    def test_unknown_retained_and_empty_yes_rejected(self):
        item=self.answer['items'][0]
        item.update(label='UNKNOWN', report_quote='', source_quote='', source_id='')
        self.assertEqual(validate_answer(json.dumps(self.answer),self.packet)['items'][0]['label'],'UNKNOWN')
        item['label']='YES'
        with self.assertRaises(ValueError):
            validate_answer(json.dumps(self.answer), self.packet)

    def test_control_keeps_headings_but_removes_claim(self):
        control=empty_body('## Key Findings\nRevenue doubled.\n## Sources\n[S1] annual report\n')
        self.assertNotIn('Revenue doubled',control)
        self.assertIn('## Key Findings',control)
        self.assertIn('[S1] annual report',control)

    def test_added_depth_definition_not_explicit_following_score(self):
        qs=questions('T3',{'style':'formal_analytical','depth':'detailed'})
        depth=next(q for q in qs if q['id']=='depth_diagnostic')
        self.assertTrue(depth['diagnostic'])

    def test_itemwise_isolates_failure_without_changing_neighbor(self):
        self.packet['questions'].append({'id':'other'})
        bad={**self.answer['items'][0], 'id':'other', 'report_quote':'Invented text'}
        self.answer['items'].append(bad)
        raw={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(self.answer)}}]}
        rows=extract(self.packet,raw)
        self.assertEqual([r['label'] for r in rows],['YES','INVALID'])
        self.assertEqual(rows[1]['raw_label'],'YES')

    def test_missing_response_retains_planned_denominator(self):
        rows=extract(self.packet,{})
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['label'],'INVALID')


if __name__=='__main__': unittest.main()
