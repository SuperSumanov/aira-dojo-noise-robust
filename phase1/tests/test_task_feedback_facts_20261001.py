import importlib.util,json,math,tempfile,unittest
from pathlib import Path
P=Path(__file__).parents[1]/'scripts/task_feedback_facts_20261001.py'
s=importlib.util.spec_from_file_location('facts',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class FactsTest(unittest.TestCase):
    def test_same_state_information(self):
        b,bf=m.feedback('B',{'valid':True,'metric':.2},{'overall':.2,'slices':[]},'goal')
        c,cf=m.feedback('C',{'valid':True,'metric':.2},{'overall':.2,'slices':[]},'goal')
        self.assertEqual(bf,cf);self.assertNotEqual(b,c)
        _,af=m.feedback('A',{'valid':True,'metric':.2},{'overall':.2},'goal')
        self.assertNotIn('aggregate_diagnostics',json.loads(af))
    def test_auc(self):
        self.assertEqual(m.auc([0,1],[.2,.8]),1)
        self.assertEqual(m.auc([0,1],[.8,.2]),0)
        self.assertEqual(m.auc([0,1],[.2,.2]),.5)
        self.assertIsNone(m.auc([1,1],[.2,.8]))
    def test_comparison_uses_actual_parent_not_last_sibling(self):
        parent={'overall':.5,'slices':[{'metric':.4}]}
        current={'overall':.6,'slices':[{'metric':.3}]}
        result=m.compare_to_parent(current,parent,'a'*64)
        self.assertAlmostEqual(result['parent_overall_delta'],.1)
        self.assertAlmostEqual(result['slices'][0]['parent_delta'],-.1)
        self.assertEqual(result['parent_code_sha256'],'a'*64)
        self.assertIsNone(m.compare_to_parent(current,None,None)['parent_overall_delta'])
        self.assertNotIn('parent_delta',current['slices'][0])
    def test_metrics(self):
        self.assertAlmostEqual(m.aggregate(m.TASKS[0],[{'author':'EAP'}],[{'EAP':.8}]),-math.log(.8))
        self.assertAlmostEqual(m.aggregate(m.TASKS[2],[{'selected_text':'a b'}],[{'selected_text':'b c'}]),1/3)
    def test_groups_use_train_only(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'train.csv').write_text('id,text,author\na,a b,EAP\nb,a b c,EAP\nc,a b c d,HPL\nd,a b c d e,MWS\n')
            (p/'test.csv').write_text('id,text\nx,a\ny,a b c d e f\n')
            cuts,bins=m.groups(m.TASKS[0],p)
            self.assertEqual(cuts,[3,4]);self.assertEqual(bins,{'x':0,'y':2})
    def test_role_rejection_before_read(self):
        with self.assertRaises(ValueError):m.diagnostics(m.TASKS[0],Path('/absent'),Path('/absent'),Path('/absent'),{'split':'D_val'})
    def test_full_aggregate_binding(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'train.csv').write_text('id,text,author\na,a,EAP\nb,a b,HPL\nc,a b c,MWS\n')
            (p/'test.csv').write_text('id,text\nx,a\ny,a b\nz,a b c\n')
            (p/'truth.csv').write_text('id,author\nx,EAP\ny,HPL\nz,MWS\n')
            (p/'pred.csv').write_text('id,EAP,HPL,MWS\nz,.1,.1,.8\ny,.1,.8,.1\nx,.8,.1,.1\n')
            r={'split':'D_search_development_only','log_loss':-math.log(.8)}
            f=m.diagnostics(m.TASKS[0],p,p/'truth.csv',p/'pred.csv',r)
            self.assertEqual(sum(x['n'] for x in f['slices']),3)
            self.assertAlmostEqual(f['overall'],r['log_loss'])
            r['log_loss']=.9
            with self.assertRaises(ValueError):m.diagnostics(m.TASKS[0],p,p/'truth.csv',p/'pred.csv',r)
if __name__=='__main__':unittest.main()
