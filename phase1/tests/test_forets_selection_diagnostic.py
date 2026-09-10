"""Artificial ledgers only; no task, model, network or protected data."""
import copy
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import forets_selection_diagnostic as diagnostic
from forets_selection_20260908 import choose_slots
from forets_pilot_plan import run_order


def snapshot(scores=(.9, .8, .2, .1), *, step=0, policy='critic_topk_random', seed=6):
    n = 4-step
    values = list(scores[:n]) if policy == 'critic_topk_random' else [None]*n
    selected = choose_slots(n, 2, 1, policy, seed, 'leaf-classification', step,
                            values if policy == 'critic_topk_random' else None)
    ready = 'scored' if policy == 'critic_topk_random' else 'generated'
    return dict(schema=4, binding=dict(schema=4, task='leaf-classification', step=step,
                selection_policy=policy), phase='complete', pool_sha256='1'*64,
                selected=selected, candidates=[dict(node=dict(id=f'artificial-{i}',code='DO_NOT_EXPORT'),
                    score=values[i], state='completed' if i in selected else ready) for i in range(n)])


def diagnose(value, *, step=0, policy='critic_topk_random', seed=6):
    return diagnostic.diagnose_snapshot(value, task='leaf-classification', seed=seed, policy=policy, step=step)


def save_snapshot(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, sort_keys=True)
    with closing(sqlite3.connect(path)) as db:
        with db:
            db.execute('CREATE TABLE snapshot (id INTEGER PRIMARY KEY,payload TEXT,sha256 TEXT)')
            db.execute('INSERT INTO snapshot VALUES (1,?,?)', (raw,hashlib.sha256(raw.encode()).hexdigest()))


class DiagnosticTests(unittest.TestCase):
    def test_distinct_cutoff_is_not_a_quality_claim(self):
        row = diagnose(snapshot())
        self.assertTrue(row['strictly_separated_cutoff'])
        self.assertFalse(row['cutoff_tie'])
        self.assertTrue(row['replay_matches'])
        for forbidden in ('accuracy','utility','score','code','selected_node_id'):
            self.assertNotIn(forbidden, row)

    def test_all_ties_may_change_slot_but_are_not_discrimination(self):
        changed = []
        for seed in range(20):
            row = diagnose(snapshot(scores=(.5,)*4,seed=seed),seed=seed)
            self.assertTrue(row['all_scores_equal'])
            self.assertTrue(row['cutoff_tie'])
            self.assertFalse(row['strictly_separated_cutoff'])
            changed.append(row['coupled_random_slot_differs'])
        self.assertIn(True,changed)

    def test_ties_only_inside_topk_are_not_cutoff_ties(self):
        row = diagnose(snapshot(scores=(.9,.9,.2,.1)))
        self.assertFalse(row['cutoff_tie'])
        self.assertFalse(row['all_scores_equal'])

    def test_boundary_tie_is_not_all_equal(self):
        row = diagnose(snapshot(scores=(.9,.4,.4,.1)))
        self.assertTrue(row['cutoff_tie'])
        self.assertFalse(row['all_scores_equal'])

    def test_full_pool_is_exactly_same_slot(self):
        for step in (2,3):
            row = diagnose(snapshot(step=step),step=step)
            self.assertTrue(row['full_pool_no_pruning'])
            self.assertFalse(row['coupled_random_slot_differs'])
            self.assertFalse(row['coupled_random_excluded'])
            self.assertIsNone(row['cutoff_tie'])

    def test_random_arm_remains_unscored(self):
        row = diagnose(snapshot(policy='uniform_random'),policy='uniform_random')
        self.assertEqual(row['known_score_count'],0)
        self.assertIsNone(row['all_scores_equal'])
        self.assertIsNone(row['cutoff_tie'])
        self.assertFalse(row['coupled_random_slot_differs'])

    def test_partial_generation_is_not_zero_intervention(self):
        data = snapshot()
        data.update(phase='collecting', selected=None, pool_sha256=None)
        for c in data['candidates']: c.update(state='pending',node=None,score=None)
        row = diagnose(data)
        self.assertFalse(row['selection_recorded'])
        self.assertIsNone(row['coupled_random_slot_differs'])

    def test_selected_not_executed_is_not_completed(self):
        data = snapshot(); data['phase']='selected'
        data['candidates'][data['selected'][0]]['state']='scored'
        self.assertFalse(diagnose(data)['selected_execution_completed'])

    def test_mismatch_nonfinite_missing_scores_and_binding_rejected(self):
        original=snapshot()
        changes=[lambda d:d['selected'].__setitem__(0,3),
                 lambda d:d['candidates'][0].update(score=float('nan')),
                 lambda d:d['candidates'][0].update(score=None),
                 lambda d:d['binding'].update(task='wrong'),
                 lambda d:d['binding'].update(step=True),
                 lambda d:d['binding'].update(score_bypass='full_pool_no_pruning'),
                 lambda d:d.update(phase='collecting'),
                 lambda d:d['candidates'][3].update(state='executing')]
        for change in changes:
            data=copy.deepcopy(original);change(data)
            with self.assertRaises(ValueError): diagnose(data)

    def test_readonly_hash_and_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'batch.sqlite';save_snapshot(path,snapshot())
            before=path.read_bytes()
            self.assertEqual(diagnostic.read_snapshot(path)['schema'],4)
            self.assertEqual(before,path.read_bytes())
            lock=path.with_suffix('.sqlite.lock');lock.touch()
            with self.assertRaises(ValueError): diagnostic.read_snapshot(path)
            lock.unlink()
            with closing(sqlite3.connect(path)) as db:
                with db: db.execute("UPDATE snapshot SET sha256='bad'")
            with self.assertRaises(ValueError): diagnostic.read_snapshot(path)

    def test_selector_matches_real_production_hash(self):
        file=Path(diagnostic.__file__).with_name('forets_selection_20260908.py')
        self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),diagnostic.SELECTOR_SHA)

    def test_whole_package_preserves_missing_runs_and_serialization_distinction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            prepared=dict(schema=1,role='forets_e2e_development',source_tree=diagnostic.SOURCE_TREE,runs=[])
            (root/'configs').mkdir()
            for i,(task,seed,policy) in enumerate(run_order()):
                run_id=f'artificial-{i}';directory=f'runs/{run_id}'
                cfg=dict(solver=dict(selection_policy=policy,selector_seed=seed,num_children=4,
                    critic_top_k=2,num_children_to_choose=1,skip_redundant_critic=False,step_limit=4,
                    checkpoint_path=str(root/directory/'checkpoint')))
                raw=json.dumps(cfg,indent=2).encode()
                (root/'configs'/f'{run_id}.json').write_bytes(raw)
                prepared['runs'].append(dict(task=task,seed=seed,policy=policy,run_id=run_id,
                    run_dir=directory,process_summary=directory+'/summary.json',
                    config_sha256=hashlib.sha256(raw).hexdigest()))
            runtime=copy.deepcopy(prepared)
            # Runtime source may use different whitespace while preserving the config.
            for r in runtime['runs']: r['config_sha256']='2'*64
            for name,value in [('submission',dict(job_id='12933')),('campaign.started',dict(allocation_id='12933')),
                               ('campaign.finished',dict(status='incomplete')),('manifest',prepared),('runtime-manifest',runtime)]:
                (root/f'{name}.json').write_text(json.dumps(value),encoding='utf-8')
            entry=runtime['runs'][1]
            path=root/entry['run_dir']/'checkpoint/forets-candidates-private/batch-0.sqlite'
            save_snapshot(path,snapshot())
            with patch.object(diagnostic,'PACKAGE',root):
                result=diagnostic.analyze_package(root)
                self.assertEqual(len(result['runs']),8)
                self.assertEqual(sum(r['observed_ledgers'] for r in result['runs']),1)
                self.assertEqual(result['runs'][1]['recorded_selections'],1)
                self.assertEqual(result['runs'][0]['missing_step_files'],[0,1,2,3])
                self.assertNotIn('DO_NOT_EXPORT',json.dumps(result))
                (root/'campaign.finished.json').unlink()
                with self.assertRaises(ValueError):diagnostic.analyze_package(root)

    def test_current_deployment_rejects_unfinished_before_ledger_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'campaign.started.json').write_text(json.dumps(dict(allocation_id='13004')))
            with patch.object(diagnostic,'RESILIENCE_PACKAGE',root):
                with self.assertRaisesRegex(ValueError,'not ready'):
                    diagnostic.analyze_package(root,deployment='13004')

    def test_unknown_deployment_rejected_before_path_resolution(self):
        with self.assertRaisesRegex(ValueError,'unknown reviewed'):
            diagnostic.analyze_package('not-a-real-path',deployment='arbitrary-corpus')


if __name__=='__main__':
    unittest.main()
