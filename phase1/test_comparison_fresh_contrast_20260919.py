import copy,unittest
from test_comparison_reuse_verifier_20260919 import fixture
from merge_comparison_reuse_20260919 import combine
from analyze_comparison_fresh_debug_20260919 import analyze


def sources():
    full=fixture(None,[.1,.2,.3,None])
    for row in full['rows']:
        row.update(run=f'prefix-{row["seed"]}',slot=row['index']%6,raw_code_sha256='a'*64,code_sha256='b'*64,status='returned')
    first=copy.deepcopy(full);second=copy.deepcopy(full)
    for s,unknown,job in [(first,2,'14115'),(second,1,'14128')]:
        s.update(job=job,allocation_state='COMPLETED',prepared_sha256='x')
        for r in s['rows']:
            if r['seed']==unknown:r.update(valid=None,score=None,independent_score=None,wall_seconds=None,status='not_started')
        s['groups']=[g if g['seed']!=unknown else dict(seed=unknown,prefix_matches=False,status='UNKNOWN_NO_EFFECT_CLAIM') for g in s['groups']]
        s.update(valid=sum(r['valid'] is True for r in s['rows']),no_valid_output=sum(r['valid'] is False for r in s['rows']),unknown=6)
    return first,second


def new_answers(banks,value):
    rows=[]
    for old in banks['rows']:
        if old['role']!='debug':continue
        rows.append(dict(old,node='fresh-'+str(old['seed']),request_seed=500+old['seed'],score=value,independent_score=value,
                         valid=value is not None,generation_status='code_ready',generation_seconds=600))
    return dict(role='fresh_native_debug_draws_not_live_e2e',rows=rows,generation_job='newgen',job='newexec')


class ContrastTests(unittest.TestCase):
    def test_disjoint_completion_costs_kept(self):
        result=combine(*sources());self.assertEqual(result['gpu_hours'],2);self.assertEqual(result['unknown'],0)
        self.assertEqual([a['job'] for a in result['allocations']],['14115','14128'])
    def test_reject_repeat_of_first_seed(self):
        a,b=sources();b['rows'][0]['status']='returned'
        with self.assertRaises(ValueError):combine(a,b)
    def test_reject_candidate_substitution(self):
        a,b=sources();b['rows'][6]['code_sha256']='c'*64
        with self.assertRaises(ValueError):combine(a,b)
    def test_fresh_success_can_reverse_old_positive(self):
        banks=combine(*sources());result=analyze(banks,new_answers(banks,.05))
        for group in result['groups']:
            self.assertEqual(group['one_action_cache_vs_debug']['losses'],4)
            self.assertEqual(group['symbolic_cache_first_then_debug']['terminal_quality_vs_debug'],dict(wins=0,ties=1,losses=3))
    def test_fresh_failure_retained_without_best_answer_selection(self):
        banks=combine(*sources());result=analyze(banks,new_answers(banks,None))
        self.assertEqual(result['groups'][0]['one_action_cache_vs_debug'],dict(wins=3,ties=1,losses=0,alternatives=4))
    def test_generation_failure_remains_unknown(self):
        banks=combine(*sources());fresh=new_answers(banks,None);fresh['rows'][0].update(valid=None,wall_seconds=None,generation_status='generation_failed')
        group=analyze(banks,fresh)['groups'][0]
        self.assertEqual(group['status'],'UNKNOWN_NO_EFFECT_CLAIM');self.assertNotIn('plug_in_latency_not_live_policy',group)
    def test_wrong_prefix_rejected(self):
        banks=combine(*sources());fresh=new_answers(banks,None);fresh['rows'][0]['run']='different'
        with self.assertRaises(ValueError):analyze(banks,fresh)

if __name__=='__main__':unittest.main()
