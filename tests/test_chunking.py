import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from phase1_document_retrieval import Document
from document_chunking import build_index, expand_parents


def doc(text):
    return Document('d', 'D', 'd.txt', None, text, '')


class ChunkingTests(unittest.TestCase):
    def test_abbreviations_decimals_and_wrapped_sentence(self):
        text = 'Dr. Smith reported U.S. revenue of $3.14 million. Revenue grew\nby 12.5% this year. Next sentence.'
        children, parents = build_index(doc(text), child_target=40, child_max=100)
        self.assertTrue(any('Dr. Smith reported U.S. revenue of $3.14 million.' in c.text for c in children))
        self.assertTrue(any('Revenue grew\nby 12.5% this year.' in c.text for c in children))
        self.assertEqual(''.join(c.text for c in children), text)

    def test_long_sentence_can_be_recovered_from_parent(self):
        text = 'The company ' + 'may incur costs ' * 100 + 'without returns.'
        children, parents = build_index(doc(text))
        self.assertTrue(any(c.forced_split for c in children))
        expanded = expand_parents([(1, c) for c in children], parents)
        self.assertEqual(len(expanded), 1)
        self.assertEqual(expanded[0][1].text, text)

    def test_no_punctuation_bounds_and_lossless_offsets(self):
        text = 'Revenue\n2025\n130497\n' * 500
        children, parents = build_index(doc(text))
        self.assertEqual(''.join(p.text for p in parents.values()), text)
        self.assertEqual(''.join(c.text for c in children), text)
        self.assertTrue(all(len(p.text)<=4000 for p in parents.values()))
        self.assertTrue(all(len(c.text)<=1500 for c in children))
        for c in children:
            self.assertEqual(c.text, text[c.char_start:c.char_end])
            p=parents[c.parent_id]
            self.assertLessEqual(p.char_start,c.char_start)
            self.assertLessEqual(c.char_end,p.char_end)
        expanded=expand_parents([(1,c) for c in children],parents,max_chars=4500)
        self.assertLessEqual(sum(len(p.text) for _,p in expanded),4500)


if __name__ == '__main__':
    unittest.main()
