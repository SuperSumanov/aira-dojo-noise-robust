"""Artificial result files ONLY. No model, task, API or protected data."""
import copy
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from forets_e2e_readout import ROLE, run_order, summarize


class ReadoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='forets-artificial-readout-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = dict(schema=1, role=ROLE, source_tree='0'*40, runs=[])
        for i, (task, seed, policy) in enumerate(run_order()):
            relative = f'run-{i}'
            self.manifest['runs'].append(dict(run_id=f'artificial-{i}', run_dir=relative,
                config_sha256=f'{i:064x}',
                process_summary=f'{relative}/process/summary.json', task=task, seed=seed, policy=policy))
            (self.root / relative / 'json').mkdir(parents=True)
            (self.root / relative / 'process').mkdir()
            score = (.4 if policy == 'uniform_random' else .2) if task == 'leaf-classification' else (.6 if policy == 'uniform_random' else .7)
            self.event(i, score)
            self.process(i)

    def event_path(self, i):
        return self.root / self.manifest['runs'][i]['run_dir'] / 'json/eval.jsonl'

    def event(self, i, score, selected='artificial-selected'):
        self.event_path(i).write_text(json.dumps(dict(timestamp='synthetic', step=None,
            data=dict(score=score, selected_node_id=selected)))+'\n', encoding='utf-8')

    def process(self, i, status='completed', code=0):
        path = self.root / self.manifest['runs'][i]['process_summary']
        path.write_text(json.dumps(dict(started=True,status=status,returncode=code,elapsed_seconds=10.)), encoding='utf-8')

    def result(self):
        return summarize(self.manifest, self.root)

    def test_direction_and_no_mixed_metric_average(self):
        result = self.result()
        self.assertEqual((result['planned_runs'],result['planned_pairs'],result['comparable_pairs']), (8,4,4))
        self.assertAlmostEqual(result['tasks'][0]['median_improvement'], .2)
        self.assertAlmostEqual(result['tasks'][1]['median_improvement'], .1)
        self.assertEqual(result['tasks'][0]['sample_stdev_improvement'], 0.)
        self.assertNotIn('mean_improvement', result)

    def test_zero_is_real_and_last_report_ignored(self):
        self.event(0, 0.)
        (self.root/'run-0/grading_report.json').write_text('THIS MUST NOT BE PARSED', encoding='utf-8')
        row = self.result()['runs'][0]
        self.assertTrue(row['comparable_final'])
        self.assertEqual(row['comparable_score'], 0.)

    def test_missing_run_retains_denominator_and_unknown_cost(self):
        self.event_path(0).unlink()
        (self.root/self.manifest['runs'][0]['process_summary']).unlink()
        result = self.result()
        self.assertEqual((len(result['runs']),len(result['pairs']),result['comparable_pairs']), (8,4,3))
        self.assertIsNone(result['runs'][0]['comparable_score'])
        self.assertEqual(result['tasks'][0]['by_policy']['uniform_random']['unknown_process_seconds_runs'], 1)

    def test_failed_process_does_not_erase_observed_final_or_enter_pair(self):
        for status, code in [('timed_out',-15),('failed',1),('completed_with_leftovers',0),('completed',1)]:
            with self.subTest(status=status):
                self.process(0,status,code)
                result = self.result()
                self.assertEqual(result['runs'][0]['final_score_observed'],.4)
                self.assertIsNone(result['runs'][0]['comparable_score'])
                self.assertEqual(result['comparable_pairs'],3)

    def test_ambiguous_events_are_not_last_or_best_selected(self):
        text = self.event_path(0).read_text(encoding='utf-8')
        self.event_path(0).write_text(text+text, encoding='utf-8')
        row = self.result()['runs'][0]
        self.assertEqual(row['final_event_issue'],'ambiguous_final_event_count')
        self.assertFalse(row['comparable_final'])

    def test_invalid_scores_and_identity(self):
        for value in [True, float('nan'),float('inf'),-.1,'0.3',None]:
            with self.subTest(value=repr(value)):
                self.event(0,value)
                self.assertFalse(self.result()['runs'][0]['comparable_final'])
        self.event(0,.2,selected='')
        self.assertFalse(self.result()['runs'][0]['comparable_final'])
        self.event(4,1.1)
        self.assertFalse(self.result()['runs'][4]['comparable_final'])

    def test_empty_truncated_and_duplicate_key_json(self):
        for text in ['', '{', '{"data":{"score":0.1,"score":0.2,"selected_node_id":"artificial"}}']:
            with self.subTest(text=text):
                self.event_path(0).write_text(text,encoding='utf-8')
                self.assertFalse(self.result()['runs'][0]['comparable_final'])

    def test_manifest_cannot_drop_or_duplicate_planned_runs(self):
        for change in ('drop','duplicate','same_dir','same_process','wrong_role'):
            with self.subTest(change=change):
                other=copy.deepcopy(self.manifest)
                if change=='drop': other['runs'].pop()
                elif change=='duplicate': other['runs'][1]=copy.deepcopy(other['runs'][0])
                elif change=='same_dir': other['runs'][1]['run_dir']=other['runs'][0]['run_dir']
                elif change=='same_process': other['runs'][1]['process_summary']=other['runs'][0]['process_summary']
                else: other['role']='protected_cohort'
                with self.assertRaises(ValueError): summarize(other,self.root)

    def test_no_relative_or_absolute_escape(self):
        for path in ('../outside.json','/outside.json','C:/outside.json','run-0/../../outside.json'):
            with self.subTest(path=path):
                other=copy.deepcopy(self.manifest)
                other['runs'][0]['process_summary']=path
                with self.assertRaises(ValueError): summarize(other,self.root)

    def test_cli_keeps_null_score_empty_and_refuses_report_overwrite(self):
        self.event_path(0).unlink()
        manifest_path=self.root/'artificial-manifest.json'
        manifest_path.write_text(json.dumps(self.manifest),encoding='utf-8')
        output=self.root/'readout'
        argv=[sys.executable,'-B',str(Path(__file__).resolve().parents[1]/'forets_e2e_readout.py'),
              '--development-root',str(self.root),'--manifest',str(manifest_path),'--output-dir',str(output)]
        first=subprocess.run(argv,capture_output=True,text=True,timeout=15)
        self.assertEqual(first.returncode,0,first.stderr)
        with (output/'runs.csv').open(newline='',encoding='utf-8') as file:
            rows=list(csv.DictReader(file))
        self.assertEqual(len(rows),8)
        self.assertEqual(rows[0]['comparable_score'],'')
        saved=(output/'summary.json').read_bytes()
        second=subprocess.run(argv,capture_output=True,text=True,timeout=15)
        self.assertNotEqual(second.returncode,0)
        self.assertEqual((output/'summary.json').read_bytes(),saved)


if __name__ == '__main__':
    unittest.main(verbosity=2)
