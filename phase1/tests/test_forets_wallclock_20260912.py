import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import forets_wallclock_20260912 as target
import forets_wallclock_patch_20260912 as hooks
import build_forets_wallclock_20260912 as builder

TREE = '900fa3bdf6971381c37a9792723dba42c63e5ac6'


class WallclockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, dict(FORETS_SEARCH_START_NS='1000000000',
            FORETS_SEARCH_SECONDS='600', FORETS_INCUMBENT_DIR=str(self.root/'incumbents')))
        self.env.start(); target._nodes.clear()
        self.addCleanup(self.temp.cleanup); self.addCleanup(self.env.stop)

    def solver(self, step=1, code='print(1)'):
        node = SimpleNamespace(id='node-'+str(step), code=code)
        solver = SimpleNamespace(state=SimpleNamespace(current_step=step),
                                 journal=SimpleNamespace(get_best_node=lambda: node))
        archive = self.root/('archive-'+str(step)); archive.mkdir()
        submission = b'id,value\n1,2\n'; report = b'{"score": 0.5}\n'
        target.write_private(archive/'submission.csv', submission)
        target.write_private(archive/'report.json', report)
        receipt = dict(submission_sha256=target.sha(submission), report_sha256=target.sha(report))
        with target.submission_context(code, code+'\n') as binding:
            target.capture_submission(archive, receipt)
        target.remember_submission(node, {'_forets_submission_archive': binding['receipt']})
        return solver

    def read(self):
        return target.read_incumbent(self.root/'incumbents', expected_start_ns=10**9, expected_seconds=600)

    def test_cutoff_checks_after_fsync(self):
        solver = self.solver()
        receipt = target.checkpoint_incumbent(solver, clock_ns=iter([600*10**9, 601*10**9]).__next__)
        self.assertFalse(receipt['eligible']); self.assertIsNone(self.read())

    def test_no_work_after_deadline(self):
        self.assertIsNone(target.checkpoint_incumbent(self.solver(), clock_ns=lambda: 601*10**9))
        self.assertFalse((self.root/'incumbents').exists())

    def test_only_latest_eligible_not_best_external_score(self):
        a = self.solver(1); b = self.solver(2)
        target.checkpoint_incumbent(a, clock_ns=lambda: 2*10**9)
        target.checkpoint_incumbent(b, clock_ns=lambda: 3*10**9)
        self.assertEqual(self.read()['node_id'], 'node-2')

    def test_partial_commit_ignored_without_repair(self):
        solver = self.solver(); target.checkpoint_incumbent(solver, clock_ns=lambda: 2*10**9)
        target.write_private(self.root/'incumbents/step-000002.commit.json', b'{')
        self.assertEqual(self.read()['current_step'], 1)

    def test_same_code_different_execution_not_collapsed(self):
        a = self.solver(1); b = self.solver(2)
        target.checkpoint_incumbent(a, clock_ns=lambda: 2*10**9)
        target.checkpoint_incumbent(b, clock_ns=lambda: 3*10**9)
        self.assertEqual(Path(self.read()['submission']['archive_dir']).name, 'archive-2')

    def test_code_and_formatted_execution_recorded_separately(self):
        solver = self.solver(); target.checkpoint_incumbent(solver, clock_ns=lambda: 2*10**9)
        receipt = self.read()['submission']
        self.assertNotEqual(receipt['code_sha256'], receipt['executed_code_sha256'])

    def test_mutated_incumbent_and_unknown_archive_rejected(self):
        solver = self.solver(); solver.journal.get_best_node().code = 'changed'
        with self.assertRaises(ValueError): target.checkpoint_incumbent(solver, clock_ns=lambda: 2*10**9)
        target._nodes.clear()
        with self.assertRaises(ValueError): target.checkpoint_incumbent(solver, clock_ns=lambda: 2*10**9)

    def test_no_incumbent_is_missing_not_zero(self):
        solver = SimpleNamespace(state=SimpleNamespace(current_step=1), journal=SimpleNamespace(get_best_node=lambda: None))
        target.checkpoint_incumbent(solver, clock_ns=lambda: 2*10**9)
        self.assertIsNone(self.read()['submission']); self.assertIsNone(self.read()['code'])

    def test_duplicate_step_no_overwrite(self):
        solver = self.solver(); target.checkpoint_incumbent(solver, clock_ns=lambda: 2*10**9)
        with self.assertRaises(FileExistsError): target.checkpoint_incumbent(solver, clock_ns=lambda: 3*10**9)

    def test_hash_and_cutoff_binding_checked(self):
        solver = self.solver(); target.checkpoint_incumbent(solver, clock_ns=lambda: 2*10**9)
        with self.assertRaises(ValueError):
            target.read_incumbent(self.root/'incumbents', expected_start_ns=2*10**9, expected_seconds=600)
        path = self.root/'incumbents/step-000001.json'
        with path.open('ab') as stream: stream.write(b' ')
        with self.assertRaises(ValueError): self.read()

    def test_partial_config_rejected(self):
        with self.assertRaises(ValueError): target.budget({target.FIELDS[0]: '1'})
        self.assertIsNone(target.budget({}))

    def test_request_guard_is_not_swallowed_as_candidate_error(self):
        target.admit_request(clock_ns=lambda: 465*10**9)
        with self.assertRaises(target.SearchBudgetExpired): target.admit_request(clock_ns=lambda: 466*10**9)
        self.assertFalse(issubclass(target.SearchBudgetExpired, Exception))

    def test_exact_production_hooks_compile_and_preserve_feedback(self):
        files = {'src/dojo/solvers/mcts/mcts.py': hooks.patch_mcts,
                 'src/dojo/tasks/mlebench/task.py': hooks.patch_task,
                 'src/dojo/tasks/mlebench/submission_archive.py': hooks.patch_archive,
                 'src/dojo/core/solvers/llm_helpers/backends/paid_budget.py': hooks.patch_budget,
                 'src/dojo/core/runners/slurm/bounded_process.py': hooks.patch_supervisor}
        for name, fn in files.items():
            source = subprocess.check_output(['git', 'show', TREE+':'+name]).decode()
            changed = fn(source); ast.parse(changed)
            with self.assertRaises(ValueError): fn(changed)
            if name.endswith('mcts.py'):
                self.assertIn('state = self.step(task, state)\n            from '+hooks.MODULE, changed)
            if name.endswith('task.py'):
                self.assertIn('with submission_context(action, solution) as binding:', changed)
                self.assertIn('eval_result[AUX_EVAL_INFO] = parse_report(report)', changed)
                self.assertNotIn('report["_forets', changed)

    def test_eight_run_complete_counterbalanced_matrix(self):
        rows=builder.order()
        self.assertEqual(len(rows),8)
        self.assertEqual({(t,s,a) for _,t,s,a in rows},
            {(t,s,a) for t in ('leaf-classification','spaceship-titanic') for s in (22,23)
             for a in ('uniform_random','critic_topk_random')})
        self.assertEqual(rows[0][3],rows[6][3]);self.assertNotEqual(rows[0][3],rows[4][3])


if __name__ == '__main__': unittest.main()
