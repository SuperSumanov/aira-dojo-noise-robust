"""Post-result closure/pairwise sensitivity; does NOT replace the frozen readout.

No GPU/model/data-label reads. Remote input restricted to this closed dev batch.
Hard cutoff is diagnosed, never silently promoted to completed or imputed to zero.
"""
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import unittest

OK = {'completed', 'budget_exhausted'}


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def complete(row):
    return (row['closed'] in (True, 'True') and row['attempted'] in (True, 'True')
            and row['worker_status'] in OK and row['final_dev_metric'] not in (None, '')
            and math.isfinite(float(row['final_dev_metric'])))


def delta(a, b, task):
    return float(b)-float(a) if task == 'spooky-author-identification' else float(a)-float(b)


def stats(values):
    return dict(n=len(values), median=statistics.median(values) if values else None,
                sample_variance=statistics.variance(values) if len(values)>1 else None)


def pairwise(rows):
    records=[]
    for task, seed in sorted({(r['task'],r['seed']) for r in rows if r['arm']!='ROOT'}):
        group={r['arm']:r for r in rows if r['task']==task and r['seed']==seed and r['arm']!='ROOT'}
        assert set(group)=={'continue','reimplement','new_idea','random_hpo'}
        for left,right in [('reimplement','continue'),('reimplement','new_idea'),
                           ('reimplement','random_hpo'),('continue','random_hpo')]:
            a,b=group[left],group[right]
            assert a['source_metric']==b['source_metric'] and a['budget_seconds']==b['budget_seconds']
            valid=complete(a) and complete(b)
            records.append(dict(task=task,seed=seed,left=left,right=right,complete=valid,
                oriented_difference=delta(a['final_dev_metric'],b['final_dev_metric'],task) if valid else None))
    return records


def main():
    from implementation_reset_v2_20261005 import R, check, schedule
    check()
    assert read(R/'closed.json')['service_closed']
    out=R/'readout-v1'
    frozen_hashes=read(out/'export-receipt.json')
    assert all(sha(out/name)==h for name,h in frozen_hashes.items())
    primary=read(out/'summary.json')
    assert primary['job']=='16370' and primary['numerical_screen']=='incomplete'
    checked={(x['index'],x['action']):x for x in read(out/'independent-checks.json')}
    with (out/'runs.csv').open(newline='') as f: rows=list(csv.DictReader(f))
    episodes=[];orphans=[]
    for s in schedule():
        ep=R/f"episode-{s['index']}"
        closed=read(ep/'closed.json');deadline=read(ep/'deadline.json');native=read(ep/'native.json')
        assert closed['image_cleanup_certified'] and closed['step_connection_closed']
        assert closed['step']==native['job']+'.'+native['step'] and native['job']=='16370'
        assert deadline['budget_seconds']==600 and closed['worker_clock_seen']
        results=[];scores=[]
        for action in sorted(ep.glob('action-*'),key=lambda p:int(p.name.split('-')[1])):
            rp,sp=action/'result.json',action/'score.private.json'
            if rp.exists():
                result=read(rp);assert 0<=result['elapsed_seconds']<=600
                results.append(result)
                if result['valid']:
                    assert sp.exists() and result['exit_code']==0 and not result['timed_out']
            if sp.exists():
                score=read(sp);scores.append(score)
                assert (s['index'],action.name) in checked
                assert sha(action/'submission.private.csv')==score['receipt']['submission_sha256']
                assert checked[s['index'],action.name]['absolute_error']<=1e-12
                if not rp.exists():
                    orphans.append(dict(index=s['index'],action=action.name,
                                        score_elapsed_seconds=score['elapsed_seconds'],timely=score['elapsed_seconds']<=600))
        finish=read(ep/'finished.json') if (ep/'finished.json').exists() else None
        cutoff=bool(closed['worker_deadline_reached'] and closed['srun_returncode']==137
                    and closed['worker_clock_seen'] and finish is None)
        episodes.append(dict(index=s['index'],arm=s['arm'],task=s['task'],seed=s['seed'],
            worker_finished_present=finish is not None,hard_cutoff_without_finished=cutoff,
            worker_deadline_reached=closed['worker_deadline_reached'],srun_returncode=closed['srun_returncode'],
            supervisor_elapsed_seconds=closed['supervisor_elapsed_seconds'],
            image_cleanup_certified=closed['image_cleanup_certified'],
            valid_results=sum(x['valid'] for x in results),score_receipts=len(scores),
            last_result_elapsed_seconds=max((x['elapsed_seconds'] for x in results),default=None),
            last_score_elapsed_seconds=max((x['elapsed_seconds'] for x in scores),default=None)))
    comparisons=pairwise(rows)
    grouped=[]
    for task in sorted({r['task'] for r in rows}):
        for arm in ('continue','reimplement','new_idea','random_hpo'):
            eligible=[r for r in rows if r['task']==task and r['arm']==arm and complete(r)]
            grouped.append(dict(task=task,arm=arm,assigned=2,complete=len(eligible),
                final_dev_metric=stats([float(r['final_dev_metric']) for r in eligible]),
                oriented_improvement=stats([float(r['improvement']) for r in eligible])))
    paired_stats=[]
    for task,left,right in sorted({(r['task'],r['left'],r['right']) for r in comparisons}):
        vals=[r['oriented_difference'] for r in comparisons if r['task']==task and r['left']==left and r['right']==right and r['complete']]
        paired_stats.append(dict(task=task,left=left,right=right,**stats(vals)))
    report=dict(scope='POST_HOC_COMPLETE_PAIR_SENSITIVITY_NOT_PRIMARY_NOT_CONFIRMATORY',
        primary_summary_sha256=sha(out/'summary.json'),primary_numerical_screen=primary['numerical_screen'],
        missing_finished=sum(not r['worker_finished_present'] for r in episodes),
        hard_cutoff_missing_finished=sum(r['hard_cutoff_without_finished'] for r in episodes),
        score_without_result=orphans,episodes=episodes,pairs=comparisons,per_task_pairs=paired_stats,
        per_task_arm=grouped,automatic_expansion=False,
        caveat='Completed-pair subsets may be selected by failure mechanism. Missing workers keep unknown endpoints. No promotion by closure, no imputation, no primary gate change, no significance claim.',
        task_adapter_sha256=sha(R/'source/src/dojo/tasks/mlebench/task.py'),
        supervisor_sha256=sha(R/'root_trial_step_supervisor_20260927.py'),
        diagnostic_source_sha256=sha(__file__))
    path=out/'closure-pairwise-supplement.json'
    with path.open('x') as f:json.dump(report,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
    assert all(sha(out/name)==h for name,h in frozen_hashes.items())
    print(json.dumps(dict(path=str(path),sha256=sha(path),missing_finished=report['missing_finished'],
        hard_cutoff_missing_finished=report['hard_cutoff_missing_finished'],score_without_result=orphans,
        per_task_pairs=paired_stats,per_task_arm=grouped)))


class Tests(unittest.TestCase):
    def rows(self):
        return [dict(task='spooky-author-identification',seed=1,arm=a,closed=True,attempted=True,
                     worker_status='completed',final_dev_metric=.4+i*.01,source_metric=.6,budget_seconds=600)
                for i,a in enumerate(('continue','reimplement','new_idea','random_hpo'))]

    def test_missing_fourth_does_not_erase_complete_pair(self):
        rows=self.rows();rows[2]['worker_status']='missing_finished'
        pairs=pairwise(rows)
        self.assertTrue(pairs[0]['complete']);self.assertFalse(pairs[1]['complete'])
        self.assertIsNone(pairs[1]['oriented_difference'])
        self.assertAlmostEqual(pairs[0]['oriented_difference'],-.01)

    def test_missing_left_never_imputed(self):
        rows=self.rows();rows[1]['worker_status']='missing_finished'
        self.assertTrue(all(r['oriented_difference'] is None for r in pairwise(rows)[:3]))

    def test_closed_not_completed_and_metric_direction(self):
        row=self.rows()[0];row['worker_status']='failed';self.assertFalse(complete(row))
        self.assertAlmostEqual(delta(.6,.5,'random-acts-of-pizza'),.1)
        self.assertAlmostEqual(delta(.6,.5,'spooky-author-identification'),-.1)
        self.assertIsNone(stats([])['median']);self.assertIsNone(stats([1])['sample_variance'])
        self.assertEqual(stats([1,3]),dict(n=2,median=2,sample_variance=2))


if __name__=='__main__':
    if '--self-test' in sys.argv: unittest.main(argv=[sys.argv[0]],verbosity=2)
    else: main()
