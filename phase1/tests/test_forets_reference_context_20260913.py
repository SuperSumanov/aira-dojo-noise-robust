from pathlib import Path
import json
import subprocess
import sys
from types import SimpleNamespace as NS
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from forets_reference_context_20260913 import reference_context, patch_sources


class PoisonMetric:
    value = .3
    maximize = False
    @property
    def info(self): raise AssertionError('hidden grading metadata accessed')


def node(step, **changes):
    values = dict(code=f'print({step})', step=step, exec_time=5., exit_code=0,
                  is_buggy=False, metric=PoisonMetric())
    values.update(changes)
    return NS(**values)


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.nodes = [node(i) for i in range(4)]
        self.s = NS(cfg=NS(use_test_score=False), state=NS(current_step=4),
            journal=NS(nodes=self.nodes, get_best_node=lambda:self.nodes[0]))
    def context(self, parent=None):
        return reference_context(self.s, parent or self.nodes[1],
            budget_spec=(10,1000,None),clock_ns=lambda:100)
    def test_exact_fixed_roles_and_no_hidden_fields(self):
        c=self.context();self.assertEqual(len(c['references']),4)
        self.assertEqual([r['step'] for r in c['references']],[1,0,2,3])
        self.assertFalse(c['unexecuted_candidate_feedback'])
        self.assertNotIn('info', json.dumps(c))
    def test_no_repeated_reference(self):
        self.assertEqual(len(self.context(self.nodes[0])['references']),3)
    def test_artificial_root_with_empty_execution_is_not_history(self):
        root=node(0,code='',parents=[],exec_time=0.,is_buggy=True)
        baseline=node(1)
        self.s.journal.nodes=[root,baseline]
        self.s.journal.get_best_node=lambda:baseline
        self.s.state.current_step=2
        rows=self.context(baseline)['references']
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['roles'],['parent','incumbent','recent'])
    def test_reject_test_metric_mode(self):
        for value in (True,None,0):
            self.s.cfg.use_test_score=value
            with self.assertRaises(ValueError):self.context()
    def test_reject_unexecuted_or_future_reference(self):
        self.nodes[0].step=4
        with self.assertRaises(ValueError):self.context()
        self.nodes[0].step=0;self.nodes[0].exec_time=None
        with self.assertRaises(ValueError):self.context()
    def test_reject_foreign_parent(self):
        with self.assertRaises(ValueError):self.context(node(1))
    def test_missing_and_nonfinite_metrics(self):
        self.nodes[0].metric=NS(value=None,maximize=None)
        self.assertIsNone(self.context()['references'][1]['search_validation'])
        self.nodes[0].metric.value=float('nan')
        with self.assertRaises(ValueError):self.context()
    def test_actual_pinned_sources_patch_and_compile(self):
        root=Path(__file__).resolve().parents[2];tree='35321718fef54f1907b469ab44334a30fe66b6cd'
        texts=[subprocess.check_output(['git','show',tree+':src/dojo/solvers/fore_ts/'+name],cwd=root).decode()
               for name in ('batch_runtime.py','contextual_rank.py')]
        changed=patch_sources(*texts)
        for text in changed:compile(text,'production','exec')
        self.assertIn('reference_context=references',changed[0])
        self.assertIn('await paid_budget.reserve_async',changed[1])
        self.assertIn("context['executed_reference_context']=reference_context",changed[1])
        with self.assertRaises(ValueError):patch_sources(*changed)


if __name__=='__main__':unittest.main()
