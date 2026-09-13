import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import forets_action_delivery_20260913 as action
import forets_wallclock_20260912 as wall
from read_forets_action_delivery_20260913 import read_latest,replay


class ActionTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)
        self.env=patch.dict(os.environ,dict(FORETS_SEARCH_START_NS=str(10**9),FORETS_SEARCH_SECONDS='600',
            FORETS_INCUMBENT_DIR=str(self.root/'incumbents')))
        self.env.start();self.addCleanup(self.env.stop);wall._nodes.clear()

    def solver(self):
        root=NS(id='root',step=0,code='',parents=[],exec_time=0)
        n=NS(id='one',step=1,code='print(1)',parents=[root],exec_time=1.2,exit_code=0,
            is_buggy=False,metric=NS(value=.4,maximize=False,info={'hidden_score':'DO_NOT_COPY'}))
        wall._nodes[id(n)]=(n,dict(code_sha256=wall.sha(n.code.encode()),archive_dir='/outside/task/archive',
            submission_sha256='a'*64,report_sha256='b'*64))
        return NS(cfg=NS(action_delivery_protocol=action.PROTOCOL,use_test_score=False),
            state=NS(current_step=1),journal=NS(nodes=[root,n],get_best_node=lambda:n))

    def data(self,n=1):
        return json.loads((self.root/f'incumbents/action-incumbents/action-{n:06d}.json').read_bytes())

    def test_default_disabled_no_inspection_or_files(self):
        self.assertIsNone(action.record_action(NS(cfg=NS()),None))
        self.assertFalse((self.root/'incumbents').exists())

    def test_root_initialization_skipped(self):
        s=self.solver();s.journal.nodes=s.journal.nodes[:1]
        self.assertIsNone(action.record_action(s,wall,clock_ns=lambda:2*10**9))
        self.assertFalse((self.root/'incumbents').exists())

    def test_parsed_action_separate_from_primary_iteration(self):
        s=self.solver();c=action.record_action(s,wall,clock_ns=lambda:2*10**9)
        self.assertTrue(c['eligible']);self.assertEqual(self.data()['node_id'],'one')
        self.assertEqual(len(list((self.root/'incumbents').glob('step-*'))),0)
        self.assertNotIn('DO_NOT_COPY',json.dumps(self.data()))
        self.assertNotIn('info',self.data()['observed_nodes'][0])

    def test_failed_candidate_records_existing_incumbent_without_reselect(self):
        s=self.solver();n=NS(id='two',step=2,code='raise RuntimeError()',parents=[],exec_time=2,exit_code=1,
            is_buggy=True,metric=NS(value=None,maximize=False))
        s.journal.nodes.append(n);s.state.current_step=2
        action.record_action(s,wall,clock_ns=lambda:2*10**9)
        self.assertEqual(self.data(2)['node_id'],'one')
        self.assertTrue(self.data(2)['observed_nodes'][-1]['is_buggy'])

    def test_no_incumbent_is_missing_not_zero(self):
        s=self.solver();s.journal.nodes[1].is_buggy=True;s.journal.get_best_node=lambda:None
        action.record_action(s,wall,clock_ns=lambda:2*10**9)
        self.assertIsNone(self.data()['submission']);self.assertIsNone(self.data()['node_id'])

    def test_analysis_unfinished_rejected(self):
        s=self.solver();s.journal.nodes[1].is_buggy=None
        with self.assertRaises(ValueError):action.record_action(s,wall,clock_ns=lambda:2*10**9)
        self.assertFalse((self.root/'incumbents').exists())

    def test_post_deadline_no_write(self):
        self.assertIsNone(action.record_action(self.solver(),wall,clock_ns=lambda:601*10**9))
        self.assertFalse((self.root/'incumbents').exists())

    def test_crosses_deadline_while_persisting_is_ineligible(self):
        c=action.record_action(self.solver(),wall,clock_ns=iter([600*10**9,601*10**9]).__next__)
        self.assertFalse(c['eligible'])

    def test_changed_code_and_missing_execution_association(self):
        s=self.solver();s.journal.nodes[1].code+='\n'
        with self.assertRaises(ValueError):action.record_action(s,wall,clock_ns=lambda:2*10**9)
        wall._nodes.clear()
        with self.assertRaises(ValueError):action.record_action(s,wall,clock_ns=lambda:2*10**9)

    def test_duplicate_write_not_overwritten(self):
        s=self.solver();action.record_action(s,wall,clock_ns=lambda:2*10**9)
        with self.assertRaises(FileExistsError):action.record_action(s,wall,clock_ns=lambda:3*10**9)

    def test_actual_source_patch_compiles_and_parent_log_stays_first(self):
        tree='f1cdee3a9e553e8efeedaa1a66a2c6bd778f9798'
        paths=('src/dojo/config_dataclasses/solver/fore_ts.py','src/dojo/solvers/fore_ts/fore_ts.py')
        raw=[subprocess.check_output(['git','show',tree+':'+p]).decode() for p in paths]
        changed=action.patch_sources(*raw)
        for p,s in zip(paths,changed):compile(s,p,'exec')
        body=changed[1].split('    def log_journal(self):')[1].split('    def load_checkpoint(self):')[0]
        self.assertLess(body.index('super().log_journal()'),body.index('record_action(self, wallclock)'))
        with self.assertRaises(ValueError):action.patch_sources(*changed)

    def test_independent_reader_uses_latest_not_best_hidden_score(self):
        s=self.solver();action.record_action(s,wall,clock_ns=lambda:2*10**9)
        old=s.journal.nodes[-1]
        n=NS(**{**vars(old),'id':'two','step':2,'code':'print(2)','metric':NS(value=.3,maximize=False)})
        wall._nodes[id(n)]=(n,{**wall._nodes[id(old)][1],'code_sha256':wall.sha(n.code.encode())})
        s.journal.nodes.append(n);s.journal.get_best_node=lambda:n;s.state.current_step=2
        action.record_action(s,wall,clock_ns=lambda:3*10**9)
        d=read_latest(self.root/'incumbents',start_ns=10**9,seconds=600)
        self.assertEqual(d['node_id'],'two')

    def test_independent_reader_rejects_wrong_online_selection(self):
        s=self.solver();old=s.journal.nodes[-1]
        n=NS(**{**vars(old),'id':'two','step':2,'code':'print(2)','metric':NS(value=.3,maximize=False)})
        s.journal.nodes.append(n);s.state.current_step=2
        action.record_action(s,wall,clock_ns=lambda:2*10**9)  # Deliberately wrong mocked best.
        with self.assertRaises(ValueError):read_latest(self.root/'incumbents',start_ns=10**9,seconds=600)

    def test_reader_ignores_partial_commit_and_cutoff_crossing(self):
        s=self.solver();action.record_action(s,wall,clock_ns=iter([600*10**9,601*10**9]).__next__)
        self.assertIsNone(read_latest(self.root/'incumbents',start_ns=10**9,seconds=600))
        wall.write_private(self.root/'incumbents/action-incumbents/action-000002.commit.json',b'{')
        self.assertIsNone(read_latest(self.root/'incumbents',start_ns=10**9,seconds=600))

    def test_replay_missing_metrics_ties_and_direction(self):
        rows=[dict(node_id='a',is_buggy=False,search_value=None,maximize=False),
              dict(node_id='b',is_buggy=False,search_value=.4,maximize=False),
              dict(node_id='c',is_buggy=False,search_value=.4,maximize=False)]
        self.assertEqual(replay(rows)['node_id'],'b')
        rows[0]['search_value']=.5
        self.assertEqual(replay(rows)['node_id'],'b')
        for r in rows:r['maximize']=True
        self.assertEqual(replay(rows)['node_id'],'a')


if __name__=='__main__':unittest.main()
