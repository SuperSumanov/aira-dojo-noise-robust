import unittest
from collections import Counter
from unittest.mock import patch
from pathlib import Path
import tempfile
import csv
import fixed_pool_trial as p


class PoolTests(unittest.TestCase):
 def test_complete_fixed_matrix(self):
  rows=p.schedule();self.assertEqual(len(rows),36);self.assertEqual([r['index'] for r in rows],list(range(36)))
  self.assertEqual(Counter((r['program'],r['arm']) for r in rows),Counter({(i,a):3 for i in p.PROGRAMS for a in p.ARMS}))
  self.assertEqual({r['seed'] for r in rows},{130701})
 def test_latin_arms_same_fifo(self):
  for repeat in range(3):
   per=[r for r in p.schedule() if r['repeat']==repeat]
   self.assertEqual([per[i]['arm'] for i in (0,4,8)],list(p.ARMS[repeat:]+p.ARMS[:repeat]))
   self.assertEqual(per[0]['arm'],p.ARMS[repeat])
   self.assertEqual([[r['program'] for r in per if r['arm']==a] for a in p.ARMS],[ [p.PROGRAMS[(i+repeat)%4] for i in range(4)] ]*3)
 def test_capacity(self):
  q=[dict(program=0),dict(program=1),dict(program=4),dict(program=3)]
  self.assertIsNone(p.choose(q,q[:1],'serial',{0,4}))
  self.assertIsNone(p.choose(q,q[:2],'share2',{0,4}))
  self.assertEqual(p.choose(q,q[:1],'share2',{0,4}),q[0])
  self.assertEqual(p.choose(q,q[:1],'one_gpu',{0,4}),q[1])
  self.assertIsNone(p.choose([q[2]],q[:1],'one_gpu',{0,4}))
 def test_every_four_slot_block_is_single_arm(self):
  rows=p.schedule()
  for block in range(9):
   subset=rows[4*block:4*block+4]
   self.assertEqual(len({r['arm'] for r in subset}),1)
   self.assertEqual(len({r['repeat'] for r in subset}),1)
 def test_successful_scheduler_runs_each_slot_once(self):
  rows=p.schedule()[:4]
  for arm in p.ARMS:
   with patch.object(p,'run_one',side_effect=lambda i:dict(index=i,complete=True,returncode=0)):
    outcomes,events=p.execute_block(rows,arm)
   self.assertEqual([r['index'] for r in outcomes],[0,1,2,3])
   self.assertEqual(Counter(r['index'] for r in events),Counter(range(4)))
 def test_failures_not_silently_retried(self):
  rows=p.schedule()[:4];calls=[]
  def run(i):calls.append(i);return dict(index=i,complete=i!=0,returncode=int(i==0))
  with patch.object(p,'run_one',side_effect=run):outcomes,_=p.execute_block(rows,'share2')
  self.assertEqual(Counter(calls),Counter(range(4)))
  self.assertEqual(sum(r['complete'] for r in outcomes),3)
 def test_fixture_preserves_query_source_and_size(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
   root=Path(temp);old=root/'old';old.mkdir()
   source=root/'tabular-playground-series-dec-2021/prepared/public/train.csv';source.parent.mkdir(parents=True)
   source.write_text('Id,x,Cover_Type\n1,0,1\n2,0,1\n3,0,1\n4,0,2\n5,0,2\n10,0,3\n6,0,3\n')
   (old/'train.csv').write_text('Id,x,Cover_Type\n1,0,1\n2,0,1\n3,0,1\n4,0,2\n5,0,2\n')
   (old/'test.csv').write_text('Id,x\n10,0\n')
   (old/'sample_submission.csv').write_text('Id,Cover_Type\n10,0\n')
   pin=p.sha(source);old_pin=p.sha(old/'train.csv')
   plan=dict(programs=[dict(data=str(old))],public_inputs=[dict(path=source.as_posix(),sha256=pin)])
   result=p.covered_fixture(plan,root/'new')
   self.assertEqual(result['training_rows'],5)
   self.assertEqual(result['replacements'],[dict(position=4,public_source_index=6,old_class='2',new_class='3')])
   self.assertEqual(p.sha(source),pin);self.assertEqual(p.sha(old/'train.csv'),old_pin)
   self.assertEqual(p.sha(old/'test.csv'),p.sha(root/'new/test.csv'))
   with (root/'new/train.csv').open(newline='') as f:ids={r['Id'] for r in csv.DictReader(f)}
   self.assertNotIn('10',ids);self.assertIn('6',ids)
 def test_missing_class_only_in_query_is_not_used(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
   root=Path(temp);old=root/'old';old.mkdir()
   source=root/'tabular-playground-series-dec-2021/prepared/public/train.csv';source.parent.mkdir(parents=True)
   source.write_text('Id,x,Cover_Type\n1,0,1\n2,0,1\n10,0,3\n')
   (old/'train.csv').write_text('Id,x,Cover_Type\n1,0,1\n2,0,1\n')
   (old/'test.csv').write_text('Id,x\n10,0\n')
   plan=dict(programs=[dict(data=str(old))],public_inputs=[dict(path=source.as_posix(),sha256=p.sha(source))])
   with self.assertRaisesRegex(ValueError,'excluded query'):p.covered_fixture(plan,root/'new')


if __name__=='__main__':unittest.main()
