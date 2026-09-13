"""Synthetic isolation/target/feature tests, not evidence of research efficacy."""
import unittest
import validity_cpu_transfer_20260914 as v

class Validity(unittest.TestCase):
    def fixture(self):
        rows=[]
        for i in range(4):
            for j in range(6):
                code=f"x={i*10+j}\nprint('{'safe' if j%2 else 'broken'} computation')"
                rows.append(dict(root=f'r{i}',run=f'r{i}/run',task=v.TASKS[i%2],code=code,
                    label=j%2,ast_key=v.ast_key(code),code_sha256=v.sha(code.encode())))
        return rows

    def test_label_only_uses_observed_execution_and_format(self):
        node=dict(step=1,exec_time=1,exit_code=0,metric_info={'valid_submission':True},metric=-999999,is_buggy=True)
        self.assertEqual(v.validity(node),1)
        node['metric']=float('nan');node['term_out']='arbitrary failure text';self.assertEqual(v.validity(node),1)
        node['exit_code']=1;self.assertEqual(v.validity(node),0)
        node['exit_code']=None;self.assertIsNone(v.validity(node))
        node['exit_code']=0;node['metric_info']={};self.assertIsNone(v.validity(node))
        node['metric_info']={'valid_submission':False};self.assertEqual(v.validity(node),0)
        node['step']=0;self.assertIsNone(v.validity(node))

    def test_conflicting_flat_nested_rejected(self):
        with self.assertRaises(ValueError):v.validity(dict(step=1,exec_time=1,exit_code=0,metric_info={'valid_submission':1},**{'metric_info/valid_submission':0}))

    def test_protocol_and_ast_purge(self):
        rows=self.fixture();rows[6]['code']=rows[0]['code'];rows[6]['ast_key']=rows[0]['ast_key']
        collected=[]
        for fold,train,test,purged in v.folds(rows,'protocol'):
            self.assertEqual({r['root'] for r in test},{f'r{fold}'})
            self.assertFalse({r['run'] for r in train}&{r['run'] for r in test})
            self.assertFalse({r['ast_key'] for r in train}&{r['ast_key'] for r in test})
            if fold in (0,1):self.assertEqual(purged,1)
            collected.extend(test)
        self.assertEqual(len(collected),len(rows))

    def test_no_test_vocabulary_or_outcome_features(self):
        rows=self.fixture();train=rows[:18];test=[dict(rows[-1],code="print('zzuniquetestonlyzz')",term_out='label hints')]
        predictions,prior,report,(tf,lr)=v.fit_predict(train,test)
        self.assertNotIn('zzuni',tf.vocabulary_)
        self.assertTrue(report['fitted']);self.assertTrue(report['converged'])
        self.assertGreaterEqual(predictions[0],0);self.assertLessEqual(predictions[0],1)
        altered=[dict(test[0],label=1-test[0]['label'],term_out='opposite',metric=99,exec_time=99)]
        other,_,_,_=v.fit_predict(train,altered)
        self.assertEqual(predictions[0],other[0])

    def test_auc_orientation_and_task_macro(self):
        rows=[dict(task=t,run=str(i),label=i%2,predicted_validity=i%2) for t in v.TASKS for i in range(4)]
        metrics,macro=v.task_metrics(rows)
        self.assertEqual(macro,1.);self.assertTrue(all(r['brier']==0 for r in metrics))

    def test_ast_removes_only_nonsemantic_format(self):
        self.assertEqual(v.ast_key('x=1 # note'),v.ast_key('x = 1'))
        self.assertNotEqual(v.ast_key('x=1'),v.ast_key('x=2'))

if __name__=='__main__':unittest.main()
