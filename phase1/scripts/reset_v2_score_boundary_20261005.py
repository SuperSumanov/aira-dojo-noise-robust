"""Read-only sensitivity for score-before-cleanup, without changing primary eligibility."""
import csv
import json
from pathlib import Path
from implementation_reset_v2_20261005 import R, check, read, sha, write
from reset_v2_closure_audit_20261005 import delta


def main():
    check()
    out=R/'readout-v1'
    primary=read(out/'summary.json');audit=read(out/'closure-pairwise-supplement.json')
    frozen=read(out/'export-receipt.json')
    assert all(sha(out/n)==h for n,h in frozen.items())
    assert audit['primary_summary_sha256']==sha(out/'summary.json')
    assert sha(R/'source/src/dojo/tasks/mlebench/task.py')=='39e60193d40947e6b638e126ac5feb85e25e326dc8b0079746fa7e8cc72e553d'
    with (out/'runs.csv').open(newline='') as f:rows={int(r['index']):r for r in csv.DictReader(f)}
    findings=[]
    for item in audit['score_without_result']:
        idx=item['index'];row=rows[idx]
        score=read(R/f'episode-{idx}'/item['action']/'score.private.json')
        metric=score['receipt']['log_loss' if row['task']=='spooky-author-identification' else 'auc']
        diff=delta(metric,row['final_dev_metric'],row['task'])
        findings.append(dict(**item,task=row['task'],arm=row['arm'],saved_action_best=float(row['final_dev_metric']),
            score_only_metric=metric,oriented_difference_to_saved_best=diff,
            could_improve_saved_best=item['timely'] and diff>0,
            primary_eligibility_unchanged=True))
    contradictions=[]
    for p in primary['contrasts']:
        if not p['complete']:continue
        for control in ('continue','new_idea','random_hpo'):
            d=p['reimplement_minus_'+control]
            if d<=0:contradictions.append(dict(task=p['task'],seed=p['seed'],control=control,difference=d))
    result=dict(scope='POST_HOC_DEADLINE_SENSITIVITY_NOT_A_NEW_ENDPOINT',
        primary_summary_sha256=sha(out/'summary.json'),closure_audit_sha256=sha(out/'closure-pairwise-supplement.json'),
        findings=findings,complete_block_contradictions_to_all_wins=contradictions,
        all_wins_criterion_already_contradicted=bool(contradictions),
        primary_gate_unchanged=primary['numerical_screen'],automatic_expansion=False,
        interpretation='The trusted task calls scoring only after successful, non-timeout execution. A score receipt can precede cleanup/final result persistence. It is not retroactively made primary-eligible. Other missing worker endpoints remain unknown.',
        diagnostic_source_sha256=sha(__file__))
    p=out/'score-boundary-supplement.json';assert not p.exists()
    write(p,result)
    assert all(sha(out/n)==h for n,h in frozen.items())
    print(json.dumps(dict(result=result,sha256=sha(p))))


if __name__=='__main__':main()
