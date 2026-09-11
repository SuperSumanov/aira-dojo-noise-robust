from pathlib import Path
import tarfile
import unittest
from verify_forets_review_selection_20260912 import replay


class ReplayTests(unittest.TestCase):
    def test_full_and_budget_shrunk_pools_match_frozen_selector(self):
        archive=Path(__file__).parent/'releases/forets-review-20260912/release-code-capsule.tar.gz'
        with tarfile.open(archive) as tar:
            source=tar.extractfile('source/src/dojo/solvers/fore_ts/selection.py').read()
        ns={};exec(compile(source,'<frozen pure selector>','exec'),ns)
        for count in (1,2,3,4):
            for coupling in ('independent_subset_v2','common_priority_v1'):
                for policy in ('uniform_random','critic_topk_random'):
                    for seed in (0,11,12):
                        scores=[0.25,-0.5,0.25,2.0][:count] if policy=='critic_topk_random' else None
                        with self.subTest(count=count,coupling=coupling,policy=policy,seed=seed):
                            self.assertEqual(replay(count,scores,policy,coupling,seed,'artificial',6-count),
                                ns['choose_slots'](count,2,1,policy,seed,'artificial',6-count,scores,coupling=coupling))

    def test_incomplete_or_nonfinite_scores_are_not_ranked(self):
        for scores in ([],[float('nan')],[True]):
            with self.assertRaises(ValueError):replay(1,scores,'critic_topk_random','independent_subset_v2',11,'artificial',5)


if __name__=='__main__':unittest.main()
