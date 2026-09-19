import json,tempfile,unittest
from pathlib import Path
from readout_comparison_native_batch_order_20260919 import audit,selection_history,completed_request_time
from run_comparison_native_batch_order_20260919 import keep_incumbent
from readout_comparison_online_continuation_20260919 import compare
from verify_comparison_online_results_20260919 import verify
from test_comparison_online_verifier_20260919 import make

def accepted(kind,metric,elapsed,depth=0):
    return dict(kind=kind,depth=depth,native_accepted=True,internal_metric=metric,completed_seconds=elapsed,status='returned',submission_sha256='a'*64,code_sha256='b'*64,exit_code=0,timed_out=False)

class BatchReadout(unittest.TestCase):
    def test_later_worse_external_score_not_used(self):
        rows=[accepted('sibling',.8,50),accepted('repair',.9,200,1)]
        rows[0]['external_score']=1.;rows[1]['external_score']=0.
        self.assertEqual(selection_history(rows),(0,1,[0,1]))
    def test_ties_keep_first_and_worse_keeps_first(self):
        for v in (.8,.7):self.assertEqual(selection_history([accepted('sibling',.8,50),accepted('repair',v,200,1)]),(0,0,[0]))
    def test_no_success_and_late(self):
        self.assertEqual(selection_history([]),(None,None,[]))
        for metric,elapsed in ((float('nan'),100),(.8,2101)):
            with self.assertRaises(ValueError):selection_history([accepted('sibling',metric,elapsed)])
    def test_actual_persistence_and_independent_audit(self):
        with tempfile.TemporaryDirectory() as d:
            ep=Path(d);rows=[accepted('sibling',.8,50),accepted('repair',.9,200,1)];best=None
            for i,a in enumerate(rows):
                best=keep_incumbent(ep,dict(action_index=i,submission_sha256=a['submission_sha256'],accepted_seconds=a['completed_seconds'],code_sha256=a['code_sha256']),a['internal_metric'],best)
            (ep/'first-accepted.json').write_text(json.dumps(dict(action_index=0,accepted_seconds=50)))
            finished=dict(actions=2,native_accepted=True,first_valid_seconds=50,status='batch_complete',completed_stages=['sibling','repair'],elapsed_seconds=210)
            out=audit(ep,rows,{'cache':True},finished)
            self.assertEqual(out['incumbent_updates'],2);self.assertEqual(out['first_native_accept_seconds'],50)
            bad=json.loads((ep/'incumbent-decision-0.json').read_text());(ep/'incumbent.json').write_text(json.dumps(bad))
            with self.assertRaises(ValueError):audit(ep,rows,{'cache':True},finished)
    def test_wrong_order_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):audit(Path(d),[dict(kind='sibling',depth=0)],{'cache':False},None)
    def test_first_and_best_times_differ(self):
        data=make();data.update(role='conditioned_native_batch_order_not_full_e2e',latency_field='first_native_accept_seconds',metric_delta_field='auc_delta_cache_minus_baseline')
        for r in data['rows']:r.update(first_native_accept_seconds=None)
        for i,first,best,score in ((0,50,1000,.7),(1,100,200,.8)):
            data['rows'][i].update(valid_accepted_submission=True,first_native_accept_seconds=first,accepted_seconds=best,score=score,independent_score=score,selection_audit='PASS_INTERNAL_METRIC_FINAL_INCUMBENT')
        data['comparison']=compare(data['rows'],'auc_delta_cache_minus_baseline','first_native_accept_seconds')
        self.assertEqual(data['comparison']['groups'][0]['first_accept_seconds_delta'],-50)
        self.assertEqual(verify(data)['valid_accepted'],2)
    def test_completed_request_time_never_imputes_missing_calls(self):
        records=[('generation',{'info':{'usage':{'latency':40.}}}),('analysis',{'info':{'usage':{'latency':5.}}})]
        out=completed_request_time(records)
        self.assertEqual(out['observed_model_request_seconds'],45.)
        self.assertTrue(out['request_time_is_lower_bound']);self.assertTrue(out['unrecorded_time_not_assigned_to_model'])
        self.assertEqual(completed_request_time([])['observed_model_request_seconds'],0.)
    def test_unknown_or_nonfinite_request_time_is_not_zero(self):
        for value in (None,float('nan'),float('inf'),-1,True):
            with self.assertRaises(ValueError):completed_request_time([('analysis',{'info':{'usage':{'latency':value}}})])

if __name__=='__main__':unittest.main()
