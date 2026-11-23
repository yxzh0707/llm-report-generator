import unittest
from dataclasses import asdict
from experiments.closure_study import (audit, expand_incomplete_list, sources_for,
    read, FREEZE, ROOT, ReportRequest, load_documents)
from experiments.closure_evaluation import validate, calibration


class ClosureTests(unittest.TestCase):
    def test_preserve_original_and_actual_offsets(self):
        original = read(FREEZE / 'T4_uploaded_only_evidence.json')
        old_end = original['uploaded'][4]['char_end']
        docs = {d.document_id:d for d in load_documents(ROOT / 'data/corpus/processed')}
        expanded, changes = expand_incomplete_list(original, docs)
        self.assertEqual(original['uploaded'][4]['char_end'], old_end)
        self.assertEqual(len(changes), 1)
        self.assertLessEqual(changes[0]['added_chars'], 1400)
        s = expanded['uploaded'][4]
        self.assertEqual(s['text'], docs[s['document_id']].text[s['char_start']:s['char_end']])
        for word in ('Client segment', 'Gaming segment', 'Embedded segment'):
            self.assertIn(word, s['text'])

    def test_source_and_selected_document_gates(self):
        request = asdict(ReportRequest(task='x', source_mode='hybrid'))
        s = [{'citation':'[S1]','document_id':'a','source_kind':'uploaded'},
             {'citation':'[S2]','document_id':'b','source_kind':'web'}]
        result = audit('Content [S1]\n## Sources\n[S2]', request, s, ['a'])
        gates = {x['id']:x['passed'] for x in result['items']}
        self.assertFalse(gates['source_mode'])
        self.assertTrue(gates['selected_documents'])
        self.assertFalse(result['automatic_passed'])

    def test_itemwise_refs_missing_duplicate_and_unknown(self):
        import json
        p = calibration()[0]['packet']
        q = p['questions'][0]['id']
        good = {'id':q,'label':'YES','report_refs':['R0001'],'source_refs':['S1L0001'],'reason':'ok'}
        self.assertEqual(validate(json.dumps({'items':[good]}),p)[0]['label'],'YES')
        for item in [dict(good,report_refs=['R9999']),dict(good,source_refs=[]),dict(good,reason='')]:
            self.assertEqual(validate(json.dumps({'items':[item]}),p)[0]['label'],'INVALID')
        self.assertEqual(validate(json.dumps({'items':[good,good]}),p)[0]['label'],'INVALID')
        self.assertEqual(validate('{oops',p)[0]['label'],'INVALID')
        unknown = dict(good,label='UNKNOWN',report_refs=[],source_refs=[])
        self.assertEqual(validate(json.dumps({'items':[unknown]}),p)[0]['label'],'UNKNOWN')

    def test_calibration_balanced_distinct(self):
        cc = calibration()
        self.assertEqual(len(cc),12)
        self.assertEqual(sum(c['expected']=='YES' for c in cc),6)
        self.assertEqual(len({str(c['packet']) for c in cc}),12)


if __name__ == '__main__': unittest.main()
