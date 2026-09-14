"""One same-data/weights/hyperparameters two-feature baseline; never deploy it."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
from collections import Counter,defaultdict
from contextlib import closing
import json,math,signal,sqlite3,tempfile,time
from pathlib import Path
import numpy as np,joblib,sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from cheap_rule_baselines_20260914 import SOURCES,BASE,read,checked,sha,interval,distribution
MODEL_ROOT=BASE/'forets-task-validity-20260914-n8q3h72y'
FULL_SHA='05379469122879c798f1d2c571eb733956a067dac314050feeb06d3e09c641d1'
def size_features(code):
    code=code[:30000];return [math.log1p(len(code)),math.log1p(code.count('\n')+1)]
def main(commit):
    os.umask(0o077);signal.alarm(240);began=time.perf_counter()
    if sklearn.__version__!='1.6.1' or len(commit)!=40:raise ValueError('fixed runtime/commit')
    fullpath=MODEL_ROOT/'code_only.private.joblib'
    if sha(fullpath.read_bytes())!=FULL_SHA:raise ValueError('original model changed')
    ms=read(MODEL_ROOT/'summary.json','66be27cbde084c433df25e95cd803bc7f42df3c71ad7d72af23528205d928a33')
    training=[]
    for src in ms['sources']:
        p=Path(src['inventory_path']);inv=read(p,src['sha256'])
        training.extend(json.loads(line) for line in checked(p.parent/'nodes.private.jsonl',inv['private_nodes_sha256']).splitlines())
    counts=Counter(r['run'] for r in training)
    if len(training)!=2482 or len(counts)!=138 or len({(r['run'],r['step']) for r in training})!=2482 or ms['purged']!=0:raise ValueError('same source without reselection')
    weights=[1/counts[r['run']] for r in training];factor=len(training)/sum(weights);weights=np.array([w*factor for w in weights])
    x=np.array([size_features(r['code']) for r in training]);y=np.array([r['label'] for r in training])
    if Counter(y)!=Counter({0:1553,1:929}):raise ValueError('labels')
    model=HistGradientBoostingClassifier(max_iter=100,max_leaf_nodes=15,min_samples_leaf=20,l2_regularization=1,random_state=20260914)
    if model.get_params()!=ms['results'][0]['parameters']:raise ValueError('same hyperparameters')
    root=Path(tempfile.mkdtemp(prefix='forets-size-only-ablation-20260914-',dir=BASE))
    start=time.perf_counter();model.fit(x,y,sample_weight=weights);fit_seconds=time.perf_counter()-start
    path=root/'size_only.private.joblib';joblib.dump(dict(model=model,features=['log_chars','log_lines'],condition='size_only_ablation'),path)
    rows=[];groups=[];source_proofs=[]
    for cohort,(suffix,h) in SOURCES.items():
        source_root=BASE/('forets-wallclock-20260912-'+suffix);result=read(source_root/'cheap-transfer-missingness.json',h)
        # This preceding independent check validated raw labels and production-model scores.
        verification=read(source_root/'cheap-rule-baselines.json')
        if verification['source_missingness_sha256']!=h or verification['independently_verified_all_included_model_predictions_labels_and_bounds'] is not True:raise ValueError('independent full-model receipt')
        source_proofs.append(dict(cohort=cohort,root=str(source_root),missingness_sha256=h,verification_sha256=sha((source_root/'cheap-rule-baselines.json').read_bytes())))
        local=[]
        for old in result['rows']:
            p=source_root/'runs'/old['run']/'checkpoint/forets-candidates-private'/old['pool']
            if sha(p.read_bytes())!=old['pool_sha256']:raise ValueError('source pool')
            with closing(sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)) as db:raw,digest=db.execute('select payload,sha256 from snapshot where id=1').fetchone()
            if sha(raw.encode())!=digest:raise ValueError('payload hash')
            v=json.loads(raw);codes=[c['node']['code'] for c in v['candidates']]
            scores=model.predict_proba(np.array([size_features(c) for c in codes]))[:,1].tolist()
            lower,upper=interval(old['hgb_scores'],scores,old['labels'])
            row=dict(cohort=cohort,run=old['run'],task=old['task'],pool=old['pool'],pool_sha256=old['pool_sha256'],
                technical_eligible=old['technical_eligible'],duplicate_within_run=old['duplicate_within_run'],fully_known=old['fully_known'],labels=old['labels'],
                original_complete_case=old['from_original_complete_case'],full_scores=old['hgb_scores'],size_scores=scores,gain_lower=lower,gain_upper=upper,
                full_validity=float(np.dot(distribution(old['hgb_scores']),old['labels'])) if old['fully_known'] else None,
                size_validity=float(np.dot(distribution(scores),old['labels'])) if old['fully_known'] else None)
            rows.append(row);local.append(row)
        for task in ('leaf-classification','spaceship-titanic'):
            rr=[r for r in local if r['task']==task and r['technical_eligible'] and not r['duplicate_within_run']];perrun=defaultdict(list)
            for r in rr:perrun[r['run']].append(r)
            critical=[r for r in rr if r['fully_known'] and r['labels'][0]!=r['labels'][1]]
            groups.append(dict(cohort=cohort,task=task,runs=len(perrun),all_applicable_pairs=len(rr),known_discordant=len(critical),
                full_valid_on_discordant=sum(r['full_validity'] for r in critical),size_valid_on_discordant=sum(r['size_validity'] for r in critical),
                run_equal_lower=float(np.mean([np.mean([r['gain_lower'] for r in v]) for v in perrun.values()])) if perrun else None,
                run_equal_upper=float(np.mean([np.mean([r['gain_upper'] for r in v]) for v in perrun.values()])) if perrun else None))
    if sha(fullpath.read_bytes())!=FULL_SHA:raise ValueError('original model altered')
    out=dict(role='posthoc_single_supervised_size_only_control_not_deployed',root=str(root),worker_commit=commit,script_sha256=sha(Path(__file__).read_bytes()),
        plan_sha256=sha(Path(__file__).with_name('CHEAP_SIZE_ONLY_ABLATION_PLAN_20260914.md').read_bytes()),training_sources=ms['sources'],training_nodes=len(training),training_runs=len(counts),
        training_matrix_sha256=sha(x.tobytes()),training_labels_sha256=sha(y.tobytes()),training_weights_sha256=sha(weights.tobytes()),
        model_sha256=sha(path.read_bytes()),full_model_sha256=FULL_SHA,parameters=model.get_params(),fit_seconds=fit_seconds,total_seconds=time.perf_counter()-began,
        sklearn_version=sklearn.__version__,source_proofs=source_proofs,rows=rows,groups=groups,model_fits=1,api_calls=0,gpu_jobs=0,original_model_unchanged=True,
        limitations='Post-hoc fixed ablation. Initial validity only; missing-label bounds are not confidence intervals. No deployment/reselection, no current E2E endpoint access.')
    raw=(json.dumps(out,sort_keys=True,allow_nan=False)+'\n').encode()
    with (root/'summary.json').open('xb') as f:f.write(raw)
    print(json.dumps(dict(root=str(root),sha256=sha(raw),groups=groups,fit_seconds=fit_seconds,total_seconds=out['total_seconds'])))
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--commit',required=True);main(p.parse_args().commit)
