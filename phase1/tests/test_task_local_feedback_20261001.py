"""Qualification of synthetic facts only; does not run an agent."""
import itertools
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from task_local_feedback_20261001 import packet, render_pair, right_tails, binomial_cdf


class FeedbackFacts(unittest.TestCase):
    def test_exact_tail_against_enumerated_coin_vectors(self):
        for n in range(1, 9):
            outcomes = [sum(x) for x in itertools.product((0, 1), repeat=n)]
            for k in range(n+1):
                self.assertEqual(right_tails(n)[k], sum(x >= k for x in outcomes)/2**n)

    def test_null_family_bound(self):
        for n in (16, 64, 100):
            for m in (1, 5, 20):
                q = sum(math.comb(n,k) for k,p in enumerate(right_tails(n)) if p <= .05/m)/2**n
                self.assertLessEqual(1-(1-q)**m, .05 + 1e-12)

    def test_sampler_moments(self):
        for p in (.45, .5, .55, .7):
            cdf = binomial_cdf(64, p)
            probs = [cdf[0]] + [b-a for a,b in zip(cdf, cdf[1:])]
            self.assertAlmostEqual(sum(i*q for i,q in enumerate(probs)), 64*p, places=10)
            self.assertAlmostEqual(sum((i-64*p)**2*q for i,q in enumerate(probs)), 64*p*(1-p), places=9)

    def test_target_gain_does_not_hide_global_harm(self):
        facts = packet([45]+[28]*19, n=64, target=0)
        self.assertEqual(facts["target_status"], "supported_under_toy_assumptions")
        self.assertEqual(facts["overall_observed_direction"], "worse")
        self.assertEqual(len(facts["groups"]), 20)

    def test_same_facts_and_no_fake_model_evaluation(self):
        facts = packet([45]+[28]*19, n=64, target=0)
        rendered = render_pair(facts)
        self.assertEqual(rendered["B"]["facts"], rendered["C"]["facts"])
        self.assertEqual(json.loads(rendered["B"]["facts"]), facts)
        self.assertNotEqual(rendered["B"]["instruction"], rendered["C"]["instruction"])
        self.assertNotIn("model_response", rendered)

    def test_insufficient_not_failure(self):
        self.assertEqual(packet([32]*20, n=64, target=0)["target_status"], "insufficient_evidence")

    def test_missing_support_rejected(self):
        with self.assertRaises(ValueError): packet([], n=64, target=0)
        with self.assertRaises(ValueError): packet([0], n=0, target=0)

    def test_non_counts_rejected(self):
        for invalid in (True, 1.5, float("nan"), float("inf"), -1, 65):
            with self.assertRaises(ValueError): packet([invalid], n=64, target=0)

    def test_no_actual_metric_or_role_adapter(self):
        for role in ("dsearch", "dval", "test", "first-960", "Target-300", "Target-522"):
            with self.assertRaises(ValueError): packet([32], n=64, target=0, role=role)
        for metric in ("auc", "logloss", "spearman"):
            with self.assertRaises(ValueError): packet([32], n=64, target=0, metric=metric)

    def test_no_posthoc_target_authorization(self):
        with self.assertRaises(ValueError): packet([32], n=64, target=0, predeclared=False)
        with self.assertRaises(ValueError): packet([32], n=64, target=1)
        with self.assertRaises(ValueError): packet([32], n=64, target=True)


if __name__ == "__main__": unittest.main()
