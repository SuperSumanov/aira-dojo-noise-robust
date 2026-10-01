"""Bounded classical TASK-model reference; not a critic or a new agent method.

Fit uses only public training labels. All three prediction files are frozen
before the separate readout may open previously approved D_search labels.
No additional hyperparameter trials after readout; no protected cohorts/test.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import platform
import re
import statistics
import sys
import time
from pathlib import Path

B = Path('/research/d7/spc/yzyang4')
ROOT = B / 'task-span-reference-20261002-v1'
PUBLIC = B / 'tweet-search-only-20260927-a4d1/public'
OLD = B / 'task-feedback-real-20261001-v6'
RULE_ROOT = B / 'task-feedback-public-rule-20261002-v1'
SEEDS = [102401, 102402, 102403]
BIASES = [0.0, -0.5, 0.5, -1.0, 1.0]


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p): return json.loads(p.read_bytes())
def save(p, obj):
    with p.open('x') as f:
        json.dump(obj, f, sort_keys=True, indent=2, allow_nan=False); f.write('\n')
def readcsv(p):
    with p.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
def jac(a, b):
    a, b = set(a.lower().split()), set(b.lower().split())
    return len(a & b) / len(a | b) if a | b else 0.
def tokens(text): return list(re.finditer(r'\S+', text))


def features(row):
    ts = tokens(row['text']); words = [t.group().lower() for t in ts]; s = row['sentiment']
    return [dict(bias=1., sentiment=s, word=w, sentiment_word=s + '|' + w,
                 previous=words[i-1] if i else '<B>', next=words[i+1] if i+1 < len(ts) else '<E>',
                 position=i/max(1, len(ts)-1), length=min(len(w), 30)/30,
                 sentiment_position=s+'|'+str(min(4, i*5//max(1, len(ts))))) for i,w in enumerate(words)]


def target(row):
    needle = row['selected_text'].strip().lower(); text = row['text'].lower()
    # Unicode case conversion can expand characters and invalidate offsets.
    # Exclude such training alignments instead of silently shifting labels.
    if len(text) != len(row['text']): return None
    if not needle: return None
    start = text.find(needle)
    if start < 0: return None
    end = start + len(needle)
    return [int(t.start() < end and t.end() > start) for t in tokens(row['text'])]


def decode(text, margins, bias):
    ts = tokens(text)
    assert len(ts) == len(margins)
    if not ts: return text
    # Maximum nonempty contiguous span. Ties retain earliest-ending span.
    best = running = float(margins[0]) - bias; left = best_left = best_right = 0
    for i in range(1, len(ts)):
        value = float(margins[i]) - bias
        if running < 0: running, left = value, i
        else: running += value
        if running > best: best, best_left, best_right = running, left, i
    return text[ts[best_left].start():ts[best_right].end()]


def split_id(row, seed):
    return int(hashlib.sha256((str(seed)+':'+row['textID']).encode()).hexdigest(), 16) % 5


def smoke():
    import numpy as np
    import sklearn
    from sklearn.feature_extraction import FeatureHasher
    from sklearn.linear_model import SGDClassifier
    row = dict(text='I love this!', selected_text='love this!', sentiment='positive')
    matrix = FeatureHasher(n_features=2**18, alternate_sign=False, dtype=np.float32).transform(features(row))
    model = SGDClassifier(loss='log_loss',max_iter=2,tol=None,random_state=1).fit(matrix,target(row))
    assert len(model.decision_function(matrix))==3
    print(json.dumps(dict(synthetic_smoke='PASS',sklearn=sklearn.__version__,numpy=np.__version__,
                          real_output_root_exists=ROOT.exists(),source_sha256=sha(Path(__file__)))))


def fit():
    os.umask(0o077); started = time.monotonic()
    import numpy as np
    import scipy
    import sklearn
    import joblib
    from sklearn.feature_extraction import FeatureHasher
    from sklearn.linear_model import SGDClassifier
    ROOT.mkdir()
    input_hashes = {n:sha(PUBLIC/n) for n in ('train.csv','test.csv')}
    train, query = readcsv(PUBLIC/'train.csv'), readcsv(PUBLIC/'test.csv')
    assert all(sha(PUBLIC/n)==h for n,h in input_hashes.items())
    ids, qids = [r['textID'] for r in train], [r['textID'] for r in query]
    assert len(ids) == len(set(ids)) and len(qids) == len(set(qids)) and not set(ids)&set(qids)
    frozen_rule = load(RULE_ROOT/'rule.json')['chosen']
    assert sha(RULE_ROOT/'rule.json') == '2beaad25ab591c957f1183de5b17457ff738b25130d13075df500c36bb4fbfc0'
    assert frozen_rule == dict(column='sentiment', value='neutral', operation='copy_full_text')
    plan = dict(role='CLASSICAL_TASK_REFERENCE_NOT_CRITIC_OR_AGENT_METHOD', seeds=SEEDS, script_sha256=sha(Path(__file__)),
                source_commit='ba99b5f4999d4a15149e1fcecbfc0e4d2557435a', train_sha256=sha(PUBLIC/'train.csv'), input_sha256=sha(PUBLIC/'test.csv'),
                rule_sha256=sha(RULE_ROOT/'rule.json'), train_rows=len(train), query_rows=len(query), shared_ids=0,
                validation='SHA256(seed:textID) mod5 == 0; public training only',
                features='word, sentiment, sentiment-word, previous/next token, position, length, sentiment-position bin',
                model=dict(loss='log_loss',alpha=1e-5,max_iter=8,tol=None,average=True,hash_features=2**18,alternate_sign=False),
                biases=BIASES, bias_selection='highest public internal mean Jaccard; ties first configured bias',
                output='neutral uses existing frozen full-text rule; other sentiments use one maximum-sum contiguous token span',
                fits_per_seed=2, total_fits=6, hard_wall_seconds=240, cpu_threads=1, new_gpu=0, agent_calls=0,
                comparison='against fixed original+rule and strongest historical F+rule; all seeds retained, no post-readout tuning',
                limitation='exploratory known task/dev set, not matched E2E or new task generalization; public validation not independent of research history',
                versions=dict(python=sys.version.split()[0],numpy=np.__version__,scipy=scipy.__version__,sklearn=sklearn.__version__),
                invocation=sys.argv,platform=platform.platform(),host=platform.node(),
                threads={k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')})
    save(ROOT/'plan.json',plan)
    hasher = FeatureHasher(n_features=2**18, alternate_sign=False, dtype=np.float32)
    # Public-only label alignment. Missing exact target substrings are reported,
    # never fabricated; every query row remains in prediction/score denominators.
    usable, yparts, fparts, token_owner, unmatched = [], [], [], [], 0
    for i, row in enumerate(train):
        y = target(row)
        if y is None or not y: unmatched += 1; continue
        feats = features(row); assert len(y) == len(feats)
        usable.append(i); yparts.extend(y); fparts.extend(feats); token_owner.extend([i]*len(y))
    X = hasher.transform(fparts); del fparts
    y = np.asarray(yparts, dtype=np.int8); owner = np.asarray(token_owner, dtype=np.int32)
    query_features = [features(r) for r in query]
    Xq = hasher.transform(f for fs in query_features for f in fs)
    query_lengths = [len(fs) for fs in query_features]
    receipts = []
    for seed in SEEDS:
        began = time.monotonic(); valid_ids = {i for i,r in enumerate(train) if split_id(r,seed)==0}
        mask = np.asarray([int(i) not in valid_ids for i in owner])
        model = SGDClassifier(loss='log_loss',alpha=1e-5,max_iter=8,tol=None,average=True,random_state=seed,n_jobs=1)
        model.fit(X[mask],y[mask])
        # Include unmatched public-validation rows in metric selection too.
        validation = [train[i] for i in sorted(valid_ids)]
        vf = [features(r) for r in validation]
        vm = model.decision_function(hasher.transform(f for fs in vf for f in fs))
        bias_scores = []
        for bias in BIASES:
            offset = 0; scores = []
            for row, fs in zip(validation,vf):
                margins = vm[offset:offset+len(fs)]; offset += len(fs)
                pred = row['text'] if row['sentiment']=='neutral' else decode(row['text'],margins,bias)
                scores.append(jac(pred,row['selected_text']))
            bias_scores.append(statistics.mean(scores))
        choice = max(range(len(BIASES)),key=lambda i:bias_scores[i]); bias = BIASES[choice]
        model = SGDClassifier(loss='log_loss',alpha=1e-5,max_iter=8,tol=None,average=True,random_state=seed,n_jobs=1)
        model.fit(X,y)
        dest = ROOT/f'model-{seed}.private.joblib'; joblib.dump(model,dest)
        margins = model.decision_function(Xq); offset = 0; predictions = []
        for row,length in zip(query,query_lengths):
            scores = margins[offset:offset+length]; offset += length
            pred = row['text'] if row['sentiment']=='neutral' else decode(row['text'],scores,bias)
            predictions.append(dict(textID=row['textID'],selected_text=pred))
        output = ROOT/f'prediction-{seed}.private.csv'
        with output.open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['textID','selected_text']); w.writeheader(); w.writerows(predictions)
        receipt=dict(seed=seed,chosen_bias=bias,public_validation_scores=bias_scores,public_validation_rows=len(validation),
                     mining_token_rows=int(mask.sum()),refit_token_rows=len(y),unmatched_or_empty_training_rows=unmatched,
                     model_sha256=sha(dest),prediction_sha256=sha(output),elapsed_seconds=time.monotonic()-began)
        save(ROOT/f'fit-{seed}.json',receipt); receipts.append(receipt)
    assert all(sha(PUBLIC/n)==h for n,h in input_hashes.items())
    out=dict(status='PREDICTIONS_FROZEN_LABELS_NOT_OPENED',plan_sha256=sha(ROOT/'plan.json'),fits=6,rows=receipts,
             elapsed_seconds=time.monotonic()-started,metric_private_read=False)
    save(ROOT/'fit-complete.json',out); print(json.dumps(out,sort_keys=True))


def score():
    started=time.monotonic(); complete=load(ROOT/'fit-complete.json'); plan=load(ROOT/'plan.json')
    assert complete['status']=='PREDICTIONS_FROZEN_LABELS_NOT_OPENED' and len(complete['rows'])==3
    assert sha(ROOT/'plan.json')==complete['plan_sha256'] and sha(Path(__file__))==plan['script_sha256']
    assert sha(PUBLIC/'train.csv')==plan['train_sha256'] and sha(PUBLIC/'test.csv')==plan['input_sha256']
    sys.path.insert(0,str(OLD)); import task_feedback_real_20261001 as engine; engine.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    task=MLEBenchTask(RunConfig.load_from_json(OLD/'configs/11.json').task)
    spec=task._search_only_module.SPEC['tweet-sentiment-extraction']
    truth={r['textID']:r['selected_text'] for r in readcsv(B/spec.get('source',spec.get('view'))/'private/dsearch.csv')}
    inputs={r['textID']:r for r in readcsv(PUBLIC/'test.csv')}; assert truth.keys()==inputs.keys()
    old=load(RULE_ROOT/'summary.json')
    # Both fixed baselines are identified before any new prediction is scored.
    assert sha(RULE_ROOT/'summary.json')=='7445f0c59ade28985cc039ba78c6e7663d8abf57464b2772405ee596837e46f7'
    refs={'original_plus_rule':old['rows'][3]['rule_score'],'historical_strong_F_plus_rule':old['rows'][8]['rule_score']}
    results=[]
    for r in complete['rows']:
        p=ROOT/f'prediction-{r["seed"]}.private.csv'; assert sha(p)==r['prediction_sha256']
        predrows=readcsv(p); pred={v['textID']:v['selected_text'] for v in predrows}
        assert len(predrows)==len(pred)==len(truth) and pred.keys()==truth.keys()
        metric=task._search_only_score('tweet-sentiment-extraction',p)
        value=statistics.mean(jac(pred[k],truth[k]) for k in truth)
        assert metric['split']=='D_search_development_only' and math.isclose(value,metric['mean_word_jaccard'],abs_tol=1e-12)
        z=dict(seed=r['seed'],chosen_bias=r['chosen_bias'],score=value,prediction_sha256=r['prediction_sha256'],
               difference_original=value-refs['original_plus_rule'],difference_strong=value-refs['historical_strong_F_plus_rule'],
               fit_elapsed_seconds=r['elapsed_seconds'],plan_sha256=complete['plan_sha256'])
        for s in ('neutral','positive','negative'):
            keys=[k for k in truth if inputs[k]['sentiment']==s]
            z[s+'_rows']=len(keys);z[s+'_score']=statistics.mean(jac(pred[k],truth[k]) for k in keys)
        results.append(z)
    out=dict(status='COMPLETE_DEVELOPMENT_REFERENCE',rows=results,baselines=refs,seed_score_median=statistics.median(r['score'] for r in results),
             seed_score_sample_variance=statistics.variance(r['score'] for r in results),
             seeds_above_strong=sum(r['difference_strong']>0 for r in results),full_denominator=3,
             fit_complete_sha256=sha(ROOT/'fit-complete.json'),readout_elapsed_seconds=time.monotonic()-started,
             scope='single previously observed task/dev set; standalone classical task model with existing neutral rule; not a new agent method or matched same-budget contrast')
    save(ROOT/'summary.json',out)
    with (ROOT/'rows.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
    print(json.dumps(out,sort_keys=True))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['smoke','fit','score']);args=p.parse_args()
    dict(smoke=smoke,fit=fit,score=score)[args.mode]()
