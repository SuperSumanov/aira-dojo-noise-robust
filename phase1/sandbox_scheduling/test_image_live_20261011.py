import csv,json,tempfile,unittest,zipfile
from pathlib import Path
import image_dev_data_20261011 as d
import image_live_2plus4_20261011 as t

class ProtocolTests(unittest.TestCase):
    def test_matrix(self):
        rows=t.schedule();self.assertEqual(len(rows),32)
        self.assertEqual([rows[i*8]['arm'] for i in range(4)],['fifo1','share2','share2','fifo1'])
        for i,j in [(i,i+8) for i in range(8)]+[(i,i+8) for i in range(16,24)]:
            self.assertEqual((rows[i]['task'],rows[i]['seed'],rows[i]['lane']),(rows[j]['task'],rows[j]['seed'],rows[j]['lane']))
        self.assertEqual(t.CAP*6/3600,17)
        self.assertGreaterEqual(t.CAP,4*t.SLOT_SECONDS)
    def test_split(self):
        parts=d.split([f'{i}.png' for i in range(100)])
        self.assertEqual(list(map(len,parts)),[80,10,10]);self.assertEqual(len(set(sum(parts,[]))),100)
        self.assertEqual(parts,d.split([f'{i}.png' for i in reversed(range(100))]))
        with self.assertRaises(ValueError):d.split(['x']*100)
        with self.assertRaises(ValueError):d.split(['../x']+[f'{i}.png' for i in range(99)])
    def test_exact_transform(self):
        self.assertEqual(t.change('aa b cc',' b ',' x '),'aa x cc')
        with self.assertRaises(ValueError):t.change('b b','b','a')

class ScorerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PIL import Image
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name);source=cls.root/'source'
        cactus=source/d.TASKS[0]/'prepared/public';cactus.mkdir(parents=True)
        names=[f'{i}.jpg' for i in range(100)];train,query,res=d.split(names)
        labels={n:i%2 for i,n in enumerate(train+query+res)}
        d.write_csv(cactus/'train.csv',['id','has_cactus'],[(n,labels[n]) for n in names])
        import io
        with zipfile.ZipFile(cactus/'train.zip','w') as z:
            for n in names:
                buf=io.BytesIO();Image.new('RGB',(32,32),color=(labels[n]*255,50,75)).save(buf,format='JPEG');z.writestr('train/'+n,buf.getvalue())
        den=source/d.TASKS[1]/'prepared/public';(den/'train').mkdir(parents=True);(den/'train_cleaned').mkdir()
        for i in range(40):
            Image.new('L',(3,2),color=100+i).save(den/'train'/f'{i}.png')
            Image.new('L',(3,2),color=120+i).save(den/'train_cleaned'/f'{i}.png')
        cls.spec=d.prepare(source,cls.root/'views')
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_no_reference_visible(self):
        for task,spec in self.spec.items():
            root=Path(spec['view']);m=json.loads((root/'manifest.json').read_text());public=root/'public'
            files={p.name for p in public.rglob('*') if p.is_file()}
            self.assertFalse(set(m['reserved_ids'])&files)
            self.assertFalse((root/'private-unavailable').exists())
            if task==d.TASKS[1]:self.assertFalse(set(m['query_ids'])&{p.name for p in (public/'train_cleaned').iterdir()})
    def test_auc_reference_and_shuffled(self):
        import pandas as pd
        root=Path(self.spec[d.TASKS[0]]['view']);ref=pd.read_csv(root/'search-reference/labels.csv')
        p=self.root/'auc.csv';ref.iloc[::-1].to_csv(p,index=False)
        self.assertEqual(d.score_at(self.root,self.spec,d.TASKS[0],p)['auc'],1.)
        ref['has_cactus']=.5;ref.to_csv(p,index=False)
        self.assertEqual(d.score_at(self.root,self.spec,d.TASKS[0],p)['auc'],.5)
    def test_rmse(self):
        import pandas as pd,numpy as np
        from PIL import Image
        task=d.TASKS[1];root=Path(self.spec[task]['view']);m=json.loads((root/'manifest.json').read_text())
        df=pd.read_csv(root/'public/sample_submission.csv');df['value']=np.concatenate([np.asarray(Image.open(root/'search-reference'/n),dtype=float).ravel()/255 for n in m['query_ids']])
        p=self.root/'rmse.csv';df.iloc[::-1].to_csv(p,index=False)
        self.assertLess(d.score_at(self.root,self.spec,task,p)['rmse'],1e-12)
    def test_bad_predictions(self):
        import pandas as pd
        task=d.TASKS[0];df=pd.read_csv(Path(self.spec[task]['view'])/'public/sample_submission.csv');p=self.root/'bad.csv'
        df.iloc[:-1].to_csv(p,index=False)
        with self.assertRaises(d.InvalidSubmissionError):d.score_at(self.root,self.spec,task,p)
        df['has_cactus']=float('nan');df.to_csv(p,index=False)
        with self.assertRaises(d.InvalidSubmissionError):d.score_at(self.root,self.spec,task,p)
        df['has_cactus']=2.;df.to_csv(p,index=False)
        with self.assertRaises(d.InvalidSubmissionError):d.score_at(self.root,self.spec,task,p)

class ReadoutTests(unittest.TestCase):
    def rows(self):
        return [dict(row,started=True,complete=True,valid=True,score=(.8 if row['task']==d.TASKS[0] else .2),
                     valid_returns=2,cuda_valid_returns=2) for row in t.schedule()]
    def test_no_false_positive_from_equal(self):
        from image_live_readout_20261011 import summarize
        s=summarize(self.rows());self.assertFalse(s['quality_gate_before_structure'])
        self.assertEqual(s['per_task_medians'],{task:0 for task in d.TASKS})
    def test_orientation_and_failure_denominator(self):
        from image_live_readout_20261011 import summarize
        rows=self.rows()
        for row in rows:
            if row['arm']=='share2':
                row['score']+=(.02 if row['task']==d.TASKS[0] else -.02);row['valid_returns']=3;row['cuda_valid_returns']=3
        self.assertTrue(summarize(rows)['quality_gate_before_structure'])
        rows[0].update(started=False,complete=False,valid=False,score=None,cuda_valid_returns=0,valid_returns=0)
        s=summarize(rows);self.assertFalse(s['quality_gate_before_structure']);self.assertEqual(s['assigned'],32)
        self.assertIsNone(s['paired_pool_valid_return_differences'][0]);self.assertEqual(s['validity_rank'][d.TASKS[0]]['unobserved'],1)

if __name__=='__main__':unittest.main()
