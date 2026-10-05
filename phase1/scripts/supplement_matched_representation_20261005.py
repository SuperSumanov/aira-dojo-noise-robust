"""Posthoc diagnostic, not a new gate: grid robustness and conditional uncertainty.

No new fit, predictor selection, protected cohort, or model updates. Both split
seeds use the SAME bootstrap indices; they are not independent test datasets.
"""
import csv,json,statistics
from collections import Counter
from pathlib import Path
import numpy as np
from scipy.stats import rankdata
from matched_representation_20261005 import R,B,TASKS,read,write,sha,load,check

def auc(y,p):
    n=int(y.sum());m=len(y)-n
    if not n or not m:return None
    return float((rankdata(p)[y==1].sum()-n*(n+1)/2)/(n*m))

def main():
    check();out=R/'readout-v1';s=read(out/'summary.json');assert s['complete']==8
    with (out/'runs.csv').open(newline='') as f:rows=list(csv.DictReader(f))
    grids=read(out/'inner-grid.json');grid_diagnostics=[]
    for task in TASKS:
        for seed in sorted({r['seed'] for r in rows}):
            pair={r['arm']:r for r in rows if r['task']==task and r['seed']==seed}
            a=grids[pair['word']['index']];b=grids[pair['word_char']['index']]
            diffs=[y['inner_oriented_score']-x['inner_oriented_score'] for x,y in zip(a['rows'],b['rows'])]
            assert all(x['params']==y['params'] for x,y in zip(a['rows'],b['rows']))
            k=a['selected']['grid_index']
            grid_diagnostics.append(dict(task=task,seed=int(seed),configurations=28,
                matched_hyperparameter_inner_wins=sum(d>0 for d in diffs),median_matched_inner_difference=statistics.median(diffs),
                inner_gain_at_word_selected_parameters=diffs[k],word_selected_C_boundary=a['selected']['params']['C'] in (.1,100.),
                union_selected_C_boundary=b['selected']['params']['C'] in (.1,100.),
                converged_grid_fits_word=sum(r['converged'] for r in a['rows']),converged_grid_fits_union=sum(r['converged'] for r in b['rows'])))
    boot=[];rng=np.random.default_rng(115090)
    for task in TASKS:
        relevant=[r for r in rows if r['task']==task];cfg=read(R/'configs'/f"{relevant[0]['index']}.json")
        scorer=Path(cfg['task']['search_only_dev_scorer_path']);assert sha(scorer)==cfg['task']['search_only_dev_scorer_sha256']
        spec=load('supplement_scorer',scorer).SPEC[task];manifest_path=B/spec['view']/'manifest.json'
        assert sha(manifest_path)==spec['view_sha'];manifest=read(manifest_path)
        # All candidate-visible public bytes are still the bound immutable view.
        for n,h in manifest['public_sha256'].items():assert sha(B/spec['view']/'public'/n)==h
        label_path=B/spec['source']/'private/dsearch.csv';assert sha(label_path)==manifest['source_dsearch_sha256']
        with label_path.open(newline='',encoding='utf-8-sig') as f:labels=list(csv.DictReader(f))
        preds={}
        for r in relevant:
            pred=R/f"episode-{r['index']}"/'action-0/submission.csv';assert sha(pred)==r['prediction_sha256']
            with pred.open(newline='',encoding='utf-8-sig') as f:rr=list(csv.DictReader(f))
            keyed={x[spec['id']]:x for x in rr};assert len(keyed)==len(labels)
            if task==TASKS[0]:arr=np.array([float(keyed[x[spec['id']]][spec['label']]) for x in labels])
            else:arr=np.array([float(keyed[x['id']][x['author']]) for x in labels])
            preds[(r['seed'],r['arm'])]=arr
        seeds=sorted({r['seed'] for r in relevant});n=len(labels)
        if task==TASKS[0]:
            y=np.array([int(x[spec['label']]) for x in labels]);clusters={}
            for i,x in enumerate(labels):
                k=x['requester_username'];assert k and k not in ('None','nan')
                clusters.setdefault(k,[]).append(i)
            groups=[np.array(v) for v in clusters.values()]
            def effect(ix):
                vals=[]
                for seed in seeds:
                    a=auc(y[ix],preds[(seed,'word')][ix]);b=auc(y[ix],preds[(seed,'word_char')][ix])
                    if a is None:return None
                    vals.append(b-a)
                return float(np.mean(vals))
            grouping='requester_username clusters'
        else:
            gains=np.mean([np.log(np.maximum(preds[(seed,'word_char')],1e-15))-np.log(np.maximum(preds[(seed,'word')],1e-15)) for seed in seeds],axis=0)
            groups=[np.array([i]) for i in range(n)]
            def effect(ix):return float(gains[ix].mean())
            grouping='rows (within-task conditional interval; no source-document cluster available)'
        estimate=effect(np.arange(n));samples=[]
        for _ in range(2000):
            ix=np.concatenate([groups[j] for j in rng.integers(0,len(groups),len(groups))]);v=effect(ix)
            if v is not None:samples.append(v)
        ci=np.quantile(samples,[.025,.975]).tolist()
        boot.append(dict(task=task,observed_seed_mean_difference=estimate,conditional_percentile_95=ci,
            requested_replicates=2000,valid_replicates=len(samples),rows=n,clusters=len(groups),grouping=grouping,
            paired_across_arms_and_seeds=True,seed=115090,
            warning='Posthoc descriptive interval conditional on these trained models and reused dev task. Does not correct repeated development-set use or quantify across-task/split-training uncertainty.'))
    report=dict(status='POSTHOC_DIAGNOSTIC_ONLY',summary_sha256=sha(out/'summary.json'),script_sha256=sha(__file__),
        grid_diagnostics=grid_diagnostics,conditional_intervals=boot,
        independent_prediction_hashes={t:len({r['prediction_sha256'] for r in rows if r['task']==t}) for t in TASKS},
        original_gate_unchanged=True,new_fits=0,protected_opened=False)
    write(out/'supplement-v1.json',report);print(json.dumps(report))
if __name__=='__main__':main()
