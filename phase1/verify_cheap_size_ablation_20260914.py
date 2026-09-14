"""No refit: independently reconstruct size input, weights and model delivery."""
import os
for n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='1'
from contextlib import closing
from collections import Counter,defaultdict
import importlib.util,json,sqlite3
from pathlib import Path
import numpy as np,joblib
from analyze_cheap_recent_transfer_20260914 import read,checked,sha,BASE
from cheap_rule_baselines_20260914 import interval,distribution
ROOT=BASE/'forets-size-only-ablation-20260914-o8h3m5qv'
SHA='67fdb9c4b3468fffb3f96e57e7374ee99c30b054e8758b4ba6b8364a7681f240'
def main():
    s=read(ROOT/'summary.json',SHA);live=BASE/'forets-wallclock-20260912-km65uuej'
    source=live/'source/src/dojo/solvers/fore_ts/cheap_ranker.py';inv=read(live/'source-files.json')
    if sha(source.read_bytes())!=inv['src/dojo/solvers/fore_ts/cheap_ranker.py']:raise ValueError('feature source')
    spec=importlib.util.spec_from_file_location('features',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    train=[]
    for item in s['training_sources']:
        p=Path(item['inventory_path']);v=read(p,item['sha256'])
        train.extend(json.loads(raw) for raw in checked(p.parent/'nodes.private.jsonl',v['private_nodes_sha256']).splitlines())
    counts=Counter(r['run'] for r in train);weights=[1/counts[r['run']] for r in train];factor=len(train)/sum(weights);weights=np.array([v*factor for v in weights])
    x=np.array([module.features(r['code'])[:2] for r in train]);y=np.array([r['label'] for r in train])
    if (len(train),len(counts))!=(2482,138):raise ValueError('training denominator')
    if any(sha(v.tobytes())!=s[k] for v,k in ((x,'training_matrix_sha256'),(y,'training_labels_sha256'),(weights,'training_weights_sha256'))):raise ValueError('training representation')
    perrun=defaultdict(float)
    for r,w in zip(train,weights):perrun[r['run']]+=w
    if max(abs(v-len(train)/len(counts)) for v in perrun.values())>1e-9:raise ValueError('run-equal weights')
    path=ROOT/'size_only.private.joblib'
    if sha(path.read_bytes())!=s['model_sha256']:raise ValueError('ablation model')
    model=joblib.load(path)['model']
    if model.n_features_in_!=2 or model.get_params()!=s['parameters']:raise ValueError('model shape/parameters')
    sources={v['cohort']:v for v in s['source_proofs']};maximum=0.;critical=[]
    for r in s['rows']:
        src=Path(sources[r['cohort']]['root']);p=src/'runs'/r['run']/'checkpoint/forets-candidates-private'/r['pool']
        if sha(p.read_bytes())!=r['pool_sha256']:raise ValueError('pool')
        with closing(sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)) as db:raw,h=db.execute('select payload,sha256 from snapshot where id=1').fetchone()
        if sha(raw.encode())!=h:raise ValueError('pool payload')
        v=json.loads(raw);codes=[c['node']['code'] for c in v['candidates']]
        predicted=model.predict_proba(np.array([module.features(c)[:2] for c in codes]))[:,1].tolist()
        maximum=max(maximum,max(abs(a-b) for a,b in zip(predicted,r['size_scores'])))
        if predicted!=r['size_scores'] or interval(r['full_scores'],predicted,r['labels'])!=(r['gain_lower'],r['gain_upper']):raise ValueError('model delivery/paired bounds')
        if r['technical_eligible'] and not r['duplicate_within_run'] and r['fully_known'] and r['labels'][0]!=r['labels'][1]:critical.append(r)
    for g in s['groups']:
        rr=[r for r in s['rows'] if (r['cohort'],r['task'])==(g['cohort'],g['task']) and r['technical_eligible'] and not r['duplicate_within_run']];byrun=defaultdict(list)
        for r in rr:byrun[r['run']].append(r)
        if (len(byrun),len(rr))!=(g['runs'],g['all_applicable_pairs']):raise ValueError('group count')
        for endpoint in ('lower','upper'):
            value=float(np.mean([sum(r['gain_'+endpoint] for r in v)/len(v) for v in byrun.values()])) if byrun else None
            target=g['run_equal_'+endpoint]
            if (value is None)!=(target is None) or (value is not None and abs(value-target)>1e-12):raise ValueError('run-equal statistics')
    result=dict(status='verified_source_features_run_weights_saved_model_predictions_and_paired_bounds',summary_sha256=SHA,
        training_nodes=len(train),training_runs=len(counts),prediction_pools=len(s['rows']),prediction_max_abs_difference=maximum,
        known_discordant=len(critical),full_valid_choices=sum(r['full_validity'] for r in critical),size_only_valid_choices=sum(r['size_validity'] for r in critical),
        full_better_pairs=sum(r['full_validity']>r['size_validity'] for r in critical),full_worse_pairs=sum(r['full_validity']<r['size_validity'] for r in critical),
        original_full_model_unchanged=sha(Path(module.MODEL_PATH).read_bytes())==s['full_model_sha256'],models_refit=0,script_sha256=sha(Path(__file__).read_bytes()),
        limitations='Independent inputs/model delivery/arithmetic; no independent training repeat, no current E2E endpoint use.')
    if not result['original_full_model_unchanged']:raise ValueError('original model drift')
    raw=(json.dumps(result,sort_keys=True)+'\n').encode()
    with (ROOT/'independent.json').open('xb') as f:f.write(raw)
    print(json.dumps(dict(sha256=sha(raw),**result)))
if __name__=='__main__':main()
