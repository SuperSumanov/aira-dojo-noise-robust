import copy,unittest
from readout_comparison_cache_acceptance_20260919 import join_rows

def fixture():
    cases=[];responses=[];banks={1:dict(rows=[]),2:dict(rows=[])}
    for i in range(8):
        seed=i//4+1
        case=dict(index=i,seed=seed,request_seed=801+i,run=str(seed),node=str(i),code_sha256='a'*64,
                  log_sha256='b'*64,exit_code=0 if i<3 else 1,timed_out=False)
        cases.append(case)
        responses.append(dict(case,status='analysis_returned',analysis_seconds=2,native_metric=.4 if i<3 else None,
            native_is_bug=i>=3,would_accept_without_grader_guard=i<3))
        banks[seed]['rows'].append(dict(case,role='cache',valid=i<3))
    return cases,responses,banks

class AcceptanceTests(unittest.TestCase):
    def test_complete_join_without_oracle_replacement(self):
        rows=join_rows(*fixture());self.assertEqual(sum(r['native_acceptance'] for r in rows),3)
    def test_analyzer_can_reject_a_valid_program(self):
        cases,rows,banks=fixture();rows[0].update(native_is_bug=True,would_accept_without_grader_guard=False)
        out=join_rows(cases,rows,banks)[0]
        self.assertTrue(out['official_valid']);self.assertFalse(out['native_acceptance'])
    def test_missing_response_is_unknown_not_rejected(self):
        cases,rows,banks=fixture();out=join_rows(cases,rows[1:],banks)[0]
        self.assertIsNone(out['native_acceptance']);self.assertTrue(out['official_valid'])
    def test_wrong_code_is_rejected(self):
        cases,rows,banks=fixture();rows[0]['code_sha256']='c'*64
        with self.assertRaises(ValueError):join_rows(cases,rows,banks)
    def test_metric_without_success_cannot_accept(self):
        cases,rows,banks=fixture();rows[4].update(native_is_bug=False,native_metric=.1,would_accept_without_grader_guard=True)
        with self.assertRaisesRegex(ValueError,'equation'):join_rows(cases,rows,banks)
    def test_duplicate_response_rejected(self):
        cases,rows,banks=fixture();rows.append(copy.deepcopy(rows[0]))
        with self.assertRaisesRegex(ValueError,'duplicate'):join_rows(cases,rows,banks)

if __name__=='__main__':unittest.main()
