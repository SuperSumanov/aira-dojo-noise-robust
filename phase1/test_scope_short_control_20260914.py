import copy
import unittest
import analyze_scope_short_control_20260914 as a

class Pool(unittest.TestCase):
    def fixture(self):
        codes=['x=1','x=1\nprint(x)'];nodes={};candidates=[];calls=[]
        for slot,code in enumerate(codes):
            name=f'n{slot}';node=dict(id=name,code=code,exit_code=slot,metric_info={'valid_submission':slot==0})
            nodes[name]=node;candidates.append(dict(node=dict(id=name,code=code,operators_metrics=[])))
            calls.append(dict(slot=slot,state='returned',intent={'role':'candidate','code_sha256':a.sha(code.encode())},execution_metadata={'exit_code_reported':slot}))
        return dict(candidates=candidates,selected=[0,1],phase='complete',task_calls=calls),nodes

    def test_exact_choice_ties_and_orientation(self):
        self.assertEqual(a.choice([4,9],[1,0])['gain'],.5)
        self.assertEqual(a.choice([4,9],[0,1])['gain'],-.5)
        self.assertEqual(a.choice([4,4],[1,0])['gain'],0)
        self.assertEqual(a.choice([4,9],[1,1])['gain'],0)

    def test_original_not_repaired_label(self):
        pool,nodes=self.fixture();pool['task_calls'].append(dict(slot=1,state='returned',intent={'role':'debug'},execution_metadata={'exit_code_reported':0}))
        nodes['debug-child']=dict(id='debug-child',code='repaired',exit_code=0,metric_info={'valid_submission':True})
        value,reason=a.evaluate_pool(pool,nodes)
        self.assertEqual(reason,'eligible');self.assertEqual(value['labels'],[1,0]);self.assertEqual(value['gain'],.5)

    def test_unknown_and_incomplete_not_imputed(self):
        pool,nodes=self.fixture();pool['task_calls'][1]['state']='raised'
        value,reason=a.evaluate_pool(pool,nodes);self.assertIsNone(value);self.assertEqual(reason,'initial_call_unknown')
        pool,nodes=self.fixture();pool['phase']='executing'
        self.assertEqual(a.evaluate_pool(pool,nodes),(None,'incomplete_pool'))

    def test_code_or_exit_drift_fails(self):
        pool,nodes=self.fixture();nodes['n0']['code']='other'
        with self.assertRaises(ValueError):a.evaluate_pool(pool,nodes)
        pool,nodes=self.fixture();nodes['n0']['exit_code']=1
        with self.assertRaises(ValueError):a.evaluate_pool(pool,nodes)

    def test_module_rejection_is_retained(self):
        pool,nodes=self.fixture();nodes['n0']['exit_code']=1;pool['task_calls'][0]['execution_metadata']['exit_code_reported']=1
        nodes['n1']['exit_code']=0;nodes['n1']['metric_info']['valid_submission']=True;pool['task_calls'][1]['execution_metadata']['exit_code_reported']=0
        pool['candidates'][0]['node']['operators_metrics']=[{'edit_scope':{'interface_accepted':False}}]
        value,reason=a.evaluate_pool(pool,nodes)
        self.assertEqual(reason,'eligible');self.assertEqual(value['interface_rejected'],[True,False]);self.assertEqual(value['gain'],-.5)

if __name__=='__main__':unittest.main()
