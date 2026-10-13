import unittest
from weight_effort_runtime_prompts_20261014 import ORDER, verify


class PromptChecks(unittest.TestCase):
    def rows(self):
        return [dict(index=i, arm=ORDER[i//8], seed=214401+i%8,
                     first_call_success=True, first_call_role='improve', prompt_role='improve',
                     prompt_sha256=f'{i%8:064x}') for i in range(32)]

    def test_equal(self):
        self.assertTrue(verify(self.rows())['first_runtime_prompt_identity_verified'])

    def test_mismatch(self):
        rows=self.rows(); rows[8]['prompt_sha256']='f'*64
        out=verify(rows)
        self.assertFalse(out['first_runtime_prompt_identity_verified'])
        self.assertTrue(out['pairs'][0]['complete_first_call_evidence'])

    def test_failure_not_rescued_by_later_return(self):
        rows=self.rows(); rows[8]['first_call_success']=False
        self.assertFalse(verify(rows)['pairs'][0]['complete_first_call_evidence'])

    def test_missing(self):
        rows=self.rows()
        for k in ('first_call_role', 'first_call_success', 'prompt_role', 'prompt_sha256'):
            rows[8][k]=None
        self.assertFalse(verify(rows)['first_runtime_prompt_identity_verified'])

    def test_seed_mismatch(self):
        rows=self.rows(); rows[8]['seed']+=1
        with self.assertRaises(AssertionError): verify(rows)


if __name__ == '__main__': unittest.main()
