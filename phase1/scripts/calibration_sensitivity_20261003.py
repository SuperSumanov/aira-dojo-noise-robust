"""Post-readout conditional uncertainty; no refit, selection or new data."""
import csv,hashlib,json,math,statistics,sys,time
from pathlib import Path
import numpy as np
R=Path('/research/d7/spc/yzyang4/calibration-opportunity-20261003-v1')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
    with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def main():
    began=time.monotonic();summary=json.loads((R/'readout-v1/summary.json').read_bytes())
    assert summary['distinct_original_predictions']==summary['distinct_calibrated_predictions']==1
    sys.path.insert(0,str(R));from calibration_opportunity_20261003 import runtime
    m=runtime();from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    cfg=RunConfig.load_from_json(R/'configs/0.json');task=MLEBenchTask(cfg.task);spec=task._search_only_module.SPEC[cfg.task.name]
    labels=rows(m.B/spec.get('source',spec.get('view'))/'private/dsearch.csv');truth={x['id']:x['author'] for x in labels}
    a=R/'episode-0/action-0';base=rows(a/'original.csv');cal=rows(a/'calibrated.csv')
    assert [x['id'] for x in base]==[x['id'] for x in cal] and set(truth)=={x['id'] for x in base}
    delta=np.array([math.log(float(q[truth[p['id']]]))-math.log(float(p[truth[p['id']]])) for p,q in zip(base,cal,strict=True)])
    y=np.array([truth[p['id']] for p in base]);assert abs(delta.mean()-summary['median_improvement'])<1e-12
    rng=np.random.default_rng(103899);boot=np.zeros(5000)
    for label in sorted(set(y)):
        v=delta[y==label]
        boot+=v[rng.integers(0,len(v),size=(5000,len(v)))].sum(1)/len(delta)
    out=dict(role='POSTHOC_CONDITIONAL_SENSITIVITY_NOT_CONFIRMATION',summary_sha256=sha(R/'readout-v1/summary.json'),
        source_sha256=sha(Path(__file__)),rows=len(delta),unique_prediction_pairs=1,bootstrap_seed=103899,replicates=5000,
        class_stratified_bootstrap_percentile95=np.quantile(boot,[.025,.975]).tolist(),
        mean_improvement=float(delta.mean()),relative_loss_reduction=float(delta.mean()/summary['rows'][0]['original']),
        improved_rows=int(sum(delta>0)),worsened_rows=int(sum(delta<0)),unchanged_rows=int(sum(delta==0)),
        class_summary={c:dict(n=int(sum(y==c)),mean_improvement=float(delta[y==c].mean())) for c in sorted(set(y))},
        marginal_calibration_seconds_median=statistics.median(r['calibration_seconds'] for r in summary['rows']),
        inclusive_run_seconds_median=statistics.median(r['seconds'] for r in summary['rows']),
        gpu_hours=298*2/3600,elapsed_seconds=time.monotonic()-began,
        limits='Conditional on one fixed model pair and already reused D_search rows. Does not correct adaptive selection, fit uncertainty, task heterogeneity or support three independent replications. No frozen gate changed.')
    with (R/'readout-v1/sensitivity.json').open('x') as f:json.dump(out,f,sort_keys=True,indent=2)
    print(json.dumps(out,sort_keys=True))
if __name__=='__main__':main()
