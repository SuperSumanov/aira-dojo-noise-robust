import copy,unittest
from analyze_comparison_native_selection_20260920 import choices,select,pool,summarize

def rows():
    return [dict(slot=i,node=str(i),reward=float(6-i),native_accepted=True,native_metric=float(i),
        analysis_status='returned',valid=True,score=float(6-i),wall_seconds=10.,analysis_seconds=1.,inference_seconds=1.) for i in range(6)]

class Selection(unittest.TestCase):
    def test_not_external_oracle(self):
        rr=rows();self.assertEqual(select(rr[:2])['slot'],0);self.assertEqual(select(rr[:2])['score'],6.)
    def test_invalid_final_no_fallback(self):
        rr=rows();rr[0]['valid']=False;rr[0]['score']=None
        self.assertFalse(select(rr[:2])['valid']);self.assertEqual(select(rr[:2])['slot'],0)
    def test_late_cannot_select(self):
        rr=rows();rr[1]['native_metric']=-1
        self.assertEqual(select(rr[:2],budget=15)['slot'],0)
    def test_query_and_cold_charged(self):
        rr=rows();self.assertIsNone(select(rr[:2],budget=15,query_seconds=6)['slot'])
        self.assertIsNone(select(rr[:2],budget=15,load_seconds=16)['slot'])
    def test_tie_original_slot(self):
        rr=rows();rr[1]['native_metric']=rr[0]['native_metric'];self.assertEqual(select(rr[1::-1])['slot'],0)
    def test_no_native_acceptance(self):
        rr=rows()
        for r in rr:r['native_accepted']=False;r['native_metric']=None
        out=pool(rr,160.)['scenarios']['two_evaluations']['frozen_top_two']
        self.assertEqual(out['ties'],15);self.assertEqual(out['probability_valid_final'],0.)
    def test_negative_not_hidden(self):
        out=pool(rows(),160.)['scenarios']['two_evaluations']['frozen_top_two']
        self.assertEqual((out['wins'],out['ties'],out['losses']),(0,5,10))
    def test_uniform_self_symmetry(self):
        out=pool(rows(),160.)['scenarios']['two_evaluations']['uniform_two_of_six']
        self.assertEqual(out['net_preference'],0.);self.assertEqual(out['comparisons'],225)
    def test_duplicate_and_unknown_rejected(self):
        rr=rows();rr[1]['node']='0'
        with self.assertRaises(ValueError):pool(rr,1)
        rr=rows();rr[1]['analysis_status']='unknown'
        with self.assertRaises(ValueError):pool(rr,1)
    def test_matrix_and_unknown_retained(self):
        allrows=[]
        for task,seeds in [('leaf-classification',[1,2,3]),('spooky-author-identification',[1,2])]:
            for seed in seeds:
                for r in rows():allrows.append(r|dict(task=task,seed=seed,node=f'{task}-{seed}-{r["slot"]}'))
        self.assertEqual(summarize(allrows,160)['physical_runs'],5)
        allrows[-1]['analysis_status']='unknown'
        self.assertEqual(summarize(allrows,160)['status'],'INCOMPLETE_NO_POINT_EFFECT_CLAIM')
        with self.assertRaises(ValueError):summarize(allrows[:-1],160)

if __name__=='__main__':unittest.main()
