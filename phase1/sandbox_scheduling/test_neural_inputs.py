import unittest
from neural_inputs import cactus_split,numeric_split
from neural_pool_trial import schedule,read_json_line
from collections import Counter

class FixtureTests(unittest.TestCase):
 def test_fixed_neural_matrix(self):
  rows=schedule()
  self.assertEqual([r['index'] for r in rows],list(range(12)))
  self.assertEqual(Counter((r['program'],r['arm']) for r in rows),Counter({(p,a):3 for p in (0,1) for a in ('serial','share2')}))
  for repeat in range(3):
   own=[r for r in rows if r['repeat']==repeat]
   self.assertEqual([r['program'] for r in own if r['arm']=='serial'],[r['program'] for r in own if r['arm']=='share2'])
 def test_dependency_receipt_unambiguous(self):
  self.assertEqual(read_json_line('warning\n{"ok":true}\n'),{'ok':True})
  with self.assertRaises(ValueError):read_json_line('{}\n{}')
 def test_cactus_sorted_disjoint(self):
  rows=[dict(id=f'{i:03}.jpg',has_cactus=str(i%2)) for i in reversed(range(100))]
  train,query=cactus_split(rows)
  self.assertEqual(len(train),36);self.assertEqual(len(query),64)
  self.assertFalse({r['id'] for r in train}&set(query));self.assertEqual(query[0],'000.jpg')
 def test_cactus_duplicate_or_traversal_rejected(self):
  for bad in ('000.jpg','../x.jpg'):
   rows=[dict(id=f'{i:03}.jpg',has_cactus=str(i%2)) for i in range(100)]
   rows[-1]['id']=bad
   with self.assertRaises(ValueError):cactus_split(rows)
 def test_denoising_numeric_and_validation_nonempty(self):
  train,query=numeric_split([f'{i}.png' for i in reversed(range(1,101))])
  self.assertEqual(train,[f'{i}.png' for i in range(1,32)])
  self.assertEqual(query,['32.png','33.png']);self.assertEqual(len(train)-15,16)
 def test_denoising_ambiguous_numeric_or_insufficient_rejected(self):
  for names in ([f'{i}.png' for i in range(32)],[f'{i}.png' for i in range(40)]+['01.png']):
   with self.assertRaises(ValueError):numeric_split(names)

if __name__=='__main__':unittest.main()
