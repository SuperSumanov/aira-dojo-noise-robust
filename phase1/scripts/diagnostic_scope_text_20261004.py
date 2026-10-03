"""Spooky countercase: full-public vs fold-train vocabulary in an actual check.

Six classical executions only, no agent continuation or hidden scoring. Reuses
the already tested native worker; all sources/configs are frozen before launch.
Two split seeds are NOT independent tasks or a new learning-seed experiment.
"""
import argparse
import ast
import copy
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import re
import shutil
import statistics
import subprocess
import sys

B = Path('/research/d7/spc/yzyang4')
R = B/'diagnostic-text-scope-20261004-v1'
D = B/'executable-evidence-20261004-v1'
PIZZA = B/'diagnostic-scope-20261004-v1'
PUBLIC = B/'search-only-dev-spooky-20260927-v1/public'
PY = B/'venvs/aira/bin/python'
BASE = 'a3de6a56ef0a3e03221cfa2278fcbf2770062fe6'
CORE_SHA = '5f1441fcf268f776b446deb6cbb36d0668efad10298780959f79174d396f7220'
NODE_SHA = {'diagnostic':'b49c8d5f2f6103f2af152bddfa86698b8c3e22b11b30810e3df8cfd26add1d51',
            'reference':'f0ac74804c4e2a163376afd715ec9f2b0e420275bc0b56c8ee715dd001b1eb1b'}
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{10,}|hf_[a-z0-9]{15,}|gh[pousr]_[a-z0-9]{15,}|Bearer\s+\S{12,})')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    raw = path.read_bytes()
    assert not SECRET.search(raw), 'credential shape: content withheld'
    return json.loads(raw)


def encode(obj):
    raw = (json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    assert not SECRET.search(raw)
    return raw


def write(path,obj):
    with path.open('xb') as f:
        f.write(encode(obj))


def roster():
    rng = random.Random(106601)
    seeds = [42,173]
    rng.shuffle(seeds)
    rows = []
    for seed in seeds:
        arms = ['all_public','fold_train']
        rng.shuffle(arms)
        for arm in arms:
            rows.append(dict(index=len(rows),case='diagnostic',seed=seed,arm=arm))
    for seed in (42,173):
        rows.append(dict(index=len(rows),case='reference',seed=seed,arm='fold_train'))
    return rows


def target(n):
    return n.targets[0].id if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) else None


def original(case):
    path = D/f'episode-15/action-{1 if case=="diagnostic" else 0}/node.private.json'
    assert sha(path) == NODE_SHA[case]
    return read(path)


class SplitSeed(ast.NodeTransformer):
    def __init__(self,seed): self.seed=seed
    def visit_Call(self,n):
        if ast.unparse(n.func)=='StratifiedKFold':
            matches=[k for k in n.keywords if k.arg=='random_state']
            assert len(matches)==1 and ast.literal_eval(matches[0].value)==42
            matches[0].value=ast.Constant(self.seed)
        return self.generic_visit(n)


def vector_configs(code):
    return [{k.arg:ast.literal_eval(k.value) for k in n.keywords}
            for n in ast.walk(ast.parse(code)) if isinstance(n,ast.Call) and ast.unparse(n.func)=='TfidfVectorizer']


def program(row):
    case,seed,arm=row['case'],row['seed'],row['arm']
    code=original(case)['code']
    tree=ast.parse(code)
    if case=='reference':
        idx=next(i for i,n in enumerate(tree.body) if isinstance(n,ast.For) and 'skf.split' in ast.unparse(n.iter))
        loop=copy.deepcopy(tree.body[idx])
        boundary=next(i for i,n in enumerate(loop.body) if target(n)=='lr_word')
        selected=[n for n in loop.body if target(n) in ('lr_combined','prob_val_combined','score_combined') or
                  (isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and ast.unparse(n.value.func)=='lr_combined.fit')]
        assert len(selected)==4
        loop.body=loop.body[:boundary]+selected+[ast.Break()]
        tree=ast.Module(body=tree.body[:idx]+[loop],type_ignores=[])
    tree=SplitSeed(seed).visit(tree)
    ast.fix_missing_locations(tree)
    code=ast.unparse(tree)
    if case=='diagnostic':
        parsed=ast.parse(code)
        start=next(i for i,n in enumerate(parsed.body) if target(n)=='Xw')
        stop=next(i for i,n in enumerate(parsed.body) if isinstance(n,ast.Assign) and
                  isinstance(n.targets[0],ast.Tuple) and
                  [ast.unparse(x) for x in n.targets[0].elts]==['tr_idx','va_idx'])
        assert stop>start
        replacement=f'''
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state={seed})
tr_idx, va_idx = next(iter(skf.split(X_text, y)))
_scope_fit_full = {arm=='all_public'!r}
_scope_fit_text = X_text if _scope_fit_full else X_text[tr_idx]
tfw.fit(_scope_fit_text)
tfc.fit(_scope_fit_text)
Xw = tfw.transform(X_text)
Xc = tfc.transform(X_text)
X = sparse.hstack([Xw,Xc])
'''
        tree=ast.Module(body=parsed.body[:start]+ast.parse(replacement).body+parsed.body[stop+1:],type_ignores=[])
        code=ast.unparse(tree)
        vecs,xt,xv,yp,pred,tr,va='(tfw,tfc)','Xtr','Xva','yva','pva','tr_idx','va_idx'
    else:
        vecs,xt,xv,yp,pred,tr,va='(tfidf_word,tfidf_char)','X_tr_combined','X_val_combined','y_val','prob_val_combined','train_idx','val_idx'
    footer=f'''
import hashlib as _h, json as _json, sklearn as _sk, platform as _platform
def _matrix_sha(x):
    x=x.tocsr(copy=True); x.sort_indices()
    h=_h.sha256(str(x.shape).encode())
    for a in (x.data,x.indices.astype(np.int64),x.indptr.astype(np.int64)):
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()
_vectors={vecs}
np.savez_compressed('diagnostic_oof.npz', y={yp}, predictions={pred}, train_indices={tr}, val_indices={va})
_meta=dict(case={case!r}, seed={seed}, arm={arm!r}, rows=len({yp}), classes=classes,
    log_loss=float(log_loss({yp},{pred},labels=np.arange(3))),
    features=int({xt}.shape[1]), matrix_train_sha256=_matrix_sha({xt}), matrix_val_sha256=_matrix_sha({xv}),
    vocabulary_sha256=[_h.sha256(_json.dumps(v.vocabulary_,sort_keys=True,default=int).encode()).hexdigest() for v in _vectors],
    idf_sha256=[_h.sha256(v.idf_.tobytes()).hexdigest() for v in _vectors],
    versions=dict(python=_platform.python_version(),numpy=np.__version__,pandas=pd.__version__,sklearn=_sk.__version__),
    rng='Split changes42/173; LR explicit42, LGB original defaults, Python/numpy42. No generation.')
with open('diagnostic_meta.json','x') as _f:
    _json.dump(_meta,_f,sort_keys=True)
print('DIAGNOSTIC_TEXT_SCOPE_DONE')
'''
    answer='import random, numpy as np\nrandom.seed(42)\nnp.random.seed(42)\n'+code+'\n'+footer
    ast.parse(answer)
    assert not SECRET.search(answer.encode()) and 'submission.to_csv' not in answer
    return answer


def core():
    assert sha(R/'replay_core.py')==CORE_SHA
    spec=importlib.util.spec_from_file_location('text_scope_core',R/'replay_core.py')
    m=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=m
    spec.loader.exec_module(m)
    m.ROOT=R; m.PUBLIC=PUBLIC; m.schedule=roster; m.digest=sha
    return m


def prepare():
    assert not R.exists()
    assert read(PIZZA/'readout-v1/summary.json')['complete']==10
    assert sha(PIZZA/'diagnostic_scope_20261004.py')==CORE_SHA
    assert vector_configs(original('diagnostic')['code'])==vector_configs(original('reference')['code'])
    R.mkdir(mode=0o700)
    for rel,expected in read(PIZZA/'plan.json')['files'].items():
        if rel.startswith(('source/','forets_','opencl-vendors/')) or rel=='v6_runtime.py':
            assert sha(PIZZA/rel)==expected
            dest=R/rel; dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(PIZZA/rel,dest)
    shutil.copyfile(PIZZA/'diagnostic_scope_20261004.py',R/'replay_core.py')
    shutil.copyfile(__file__,R/'diagnostic_scope_text_20261004.py')
    (R/'diagnostic_scope_20261004.py').write_text('from diagnostic_scope_text_20261004 import main\nmain()\n')
    for d in ('programs','configs','bin'): (R/d).mkdir()
    (R/'bin/singularity').write_text(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom diagnostic_scope_text_20261004 import core\ncore().runtime().task_runtime()\n')
    os.chmod(R/'bin/singularity',0o700)
    for row in roster():
        i=row['index']; (R/f'episode-{i}').mkdir()
        (R/'programs'/f'{i}.private.py').write_text(program(row))
        cfg=read(D/'configs/15.json')
        cfg['id']=f'diagnostic-text-scope-{i}'
        cfg['logger'].update(output_dir=str(R/f'episode-{i}/native-log'),write_env_vars=False,use_wandb=False,use_console=False,print_config=False)
        cfg['metadata'].update(seed=row['seed'],base_path=str(R/'source'),git_commit_id=BASE,script_id='diagnostic-text-scope-20261004')
        cfg['interpreter'].update(timeout=300,working_dir=str(R/f'episode-{i}/unused-work'))
        cfg['interpreter']['env'].update(PYTHONHASHSEED=str(row['seed']),OMP_NUM_THREADS='6',OPENBLAS_NUM_THREADS='6',MKL_NUM_THREADS='6',NUMEXPR_NUM_THREADS='6')
        cfg['task']['cache_dir']=str(R/'no-official-data')
        assert Path(cfg['task']['data_dir'])==PUBLIC
        write(R/'configs'/f'{i}.json',cfg)
    batch=(PIZZA/'run.sbatch').read_text().replace('diagnostic-scope\n','diagnostic-text-scope\n').replace('01:30:00','00:45:00').replace('5340s','2640s').replace(str(PIZZA),str(R))
    (R/'run.sbatch').write_text(batch)
    prior=original('diagnostic')['terminal']
    original_loss=float(re.search(r'LightGBM single-fold log-loss: ([0-9.]+)',prior).group(1))
    parent=original('reference')['terminal']
    parent_loss=float(re.search(r'Fold 1: word=[0-9.]+, char=[0-9.]+, combined=([0-9.]+)',parent).group(1))
    write(R/'plan.json',dict(protocol='diagnostic-text-scope-v1',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        base_commit=BASE,schedule=roster(),executions=6,gpu_hours_cap=.75,gpus=1,allocation_seconds=2700,
        code_seconds=300,original_sources=NODE_SHA,core_sha256=CORE_SHA,source_sha256=sha(R/'diagnostic_scope_text_20261004.py'),
        original_singlefold_rounded=original_loss,original_reference_rounded=parent_loss,
        public_data={n:sha(PUBLIC/n) for n in ('train.csv','test.csv')},
        files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file()},
        primary='All four diagnostic executions; within split seed all_public minus fold_train logloss. Lower is better. Compare both to actual same-fold combined LR reference. No omission or reseeding.',
        controls='Source scope flag only; same model params/rows/splits/classes/dependencies. Fold-train diagnostic and reference feature-matrix/vocabulary/idf SHA equal. Seed42 matches original rounded outputs within5e-7.',
        interpretation='Post-Pizza selected countercase, not an untouched confirmation. A scope discrepancy need not cause large bias or reverse a choice. Report all signs, including small or absent effects. No agent-continuation or final-quality claims.',
        material_threshold=.01,gate='Descriptive only: both absolute shifts>=.01 or any/both LR ranking reversals. No automatic agent expansion.',
        randomness='split42/173; LR42 and original LGB defaults retained; Python/numpy42; hashseed=split. Not an all-model-RNG sweep.',
        stopping='Single six-execution batch; no rescue, replacement or extra seeds. Missing estimates null. Reuse native completed-slot checkpoints only with exact plan; no resubmission authorized here.',
        costs='Single3090/6CPU/45min hard allocation cap; includes startup,idling,failures. Prior observed check117.6662287649815sec. Each code cap300sec, worker deadline420sec. Overhead or slow slots can leave missing slots at allocation cap; these are not retried or imputed. No generation/API/hidden score.',
        preflight='Source/actual loader, AST single difference, explicit class/seed/fold identities, independent metric readout, all6 denominator, fixed randomized order, pinned image/runtime, exact data hashes, completed-slot checkpoint, cap/returncode and credential gates. Native task image unchanged.',
        model_base_updates=0,paid_api=0,generator_calls=0,dsearch_read=False,protected_opened=False))
    m=core();m.check();m.runtime()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    for row in roster():
        cfg=RunConfig.load_from_json(R/'configs'/f'{row["index"]}.json');cfg.validate()
        t=MLEBenchTask(cfg.task);assert t._search_only_score and not t.private_dir.exists()
    for seed in (42,173):
        left=program(dict(case='diagnostic',seed=seed,arm='all_public')).replace('_scope_fit_full = True','_scope_fit_full = FLAG').replace("arm='all_public'","arm='SCOPE'")
        right=program(dict(case='diagnostic',seed=seed,arm='fold_train')).replace('_scope_fit_full = False','_scope_fit_full = FLAG').replace("arm='fold_train'","arm='SCOPE'")
        assert left==right
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    write(R/'cpu.json',dict(status='PASS',configs=6,source_pairs=2,vector_configs_match=True,plan_sha256=sha(R/'plan.json')))
    # Readout is part of this same immutable script, fixed before submission.
    write(R/'analysis-freeze.json',dict(status='FROZEN_BEFORE_SUBMISSION',plan_sha256=sha(R/'plan.json'),script_sha256=sha(R/'diagnostic_scope_text_20261004.py')))
    print(json.dumps(dict(status='PREPARED',executions=6,plan_sha256=sha(R/'plan.json'),gpu_hours_cap=.75)))


def analyze():
    import numpy as np
    import pandas as pd
    from sklearn.metrics import log_loss
    p=core().check()
    assert (R/'closed.json').exists()
    frozen=read(R/'analysis-freeze.json')
    assert frozen['plan_sha256']==sha(R/'plan.json') and frozen['script_sha256']==sha(Path(__file__))
    labels=pd.read_csv(PUBLIC/'train.csv')['author'].map({'EAP':0,'HPL':1,'MWS':2}).to_numpy()
    rows=[]; metas={}; arrays={}; errors=[]; metric_errors=[]
    for slot in roster():
        i=slot['index'];ep=R/f'episode-{i}/action-0';result=read(ep/'result.json')
        assert all(result[k]==v for k,v in slot.items()) and result['plan_sha256']==sha(R/'plan.json')
        assert result['code_sha256']==sha(R/'programs'/f'{i}.private.py')
        row=dict(**slot,task='spooky-author-identification',base_commit=BASE,plan_sha256=sha(R/'plan.json'),
                 complete=result['complete'],seconds=result['seconds'],exit_code=result['exit_code'],error_type=result['error_type'],timed_out=result['timed_out'],log_loss=None,features=None)
        if result['complete']:
            for n,h in result['artifacts'].items(): assert sha(ep/n)==h
            meta=read(ep/'diagnostic_meta.json')
            assert all(meta[k]==slot[k] for k in ('case','seed','arm'))
            with np.load(ep/'diagnostic_oof.npz',allow_pickle=False) as z: a={k:z[k] for k in z.files}
            assert np.array_equal(labels[a['val_indices']],a['y'])
            assert len(set(a['train_indices']) & set(a['val_indices']))==0
            assert sorted(np.r_[a['train_indices'],a['val_indices']].tolist())==list(range(len(labels)))
            pred=a['predictions'];assert pred.shape==(len(a['y']),3) and np.isfinite(pred).all()
            value=float(log_loss(a['y'],pred,labels=np.arange(3)))
            clipped=np.clip(pred,np.finfo(pred.dtype).eps,1-np.finfo(pred.dtype).eps)
            clipped=clipped/clipped.sum(axis=1,keepdims=True)
            manual=float(-np.log(clipped[np.arange(len(a['y'])),a['y']]).mean())
            assert abs(value-manual)<1e-12 and abs(value-meta['log_loss'])<1e-12
            metric_errors.append(abs(value-manual))
            row.update(log_loss=value,features=meta['features']);metas[i]=meta;arrays[i]=a
        rows.append(row)
    pairs=[]
    for seed in (42,173):
        group=[r for r in rows if r['seed']==seed]
        aa=next(r for r in group if r['arm']=='all_public')
        bb=next(r for r in group if r['case']=='diagnostic' and r['arm']=='fold_train')
        rr=next(r for r in group if r['case']=='reference')
        row=dict(seed=seed,complete=all(x['complete'] for x in group),all_loss=aa['log_loss'],fold_loss=bb['log_loss'],reference_loss=rr['log_loss'],all_minus_fold=None,ranking_reversal=None)
        if row['complete']:
            for field in ('train_indices','val_indices','y'):
                assert np.array_equal(arrays[aa['index']][field],arrays[bb['index']][field]) and np.array_equal(arrays[bb['index']][field],arrays[rr['index']][field])
            for field in ('classes','versions'):
                assert metas[aa['index']][field]==metas[bb['index']][field]==metas[rr['index']][field]
            for field in ('matrix_train_sha256','matrix_val_sha256','vocabulary_sha256','idf_sha256'):
                if metas[bb['index']][field]!=metas[rr['index']][field]: errors.append(dict(seed=seed,field=field))
            row.update(all_minus_fold=aa['log_loss']-bb['log_loss'],all_minus_reference=aa['log_loss']-rr['log_loss'],fold_minus_reference=bb['log_loss']-rr['log_loss'],
                       ranking_reversal=(aa['log_loss']-rr['log_loss'])*(bb['log_loss']-rr['log_loss'])<0)
        pairs.append(row)
    reproduction=[]
    for case,key in [('diagnostic','original_singlefold_rounded'),('reference','original_reference_rounded')]:
        row=next(r for r in rows if r['seed']==42 and r['case']==case and (case=='reference' or r['arm']=='all_public'))
        reproduction.append(dict(case=case,original_rounded=p[key],new=row['log_loss'],passed=None if row['log_loss'] is None else abs(row['log_loss']-p[key])<=.0000005))
    deltas=[r['all_minus_fold'] for r in pairs if r['all_minus_fold'] is not None]
    complete=sum(r['complete'] for r in rows)
    status='COMPLETE' if complete==6 and not errors and all(x['passed'] for x in reproduction) else ('INCOMPLETE' if complete<6 else 'CONTROL_FAILURE')
    result=dict(status=status,plan_sha256=sha(R/'plan.json'),script_sha256=sha(Path(__file__)),assigned=6,complete=complete,
        controls=errors,reproduction=reproduction,rows=rows,pairs=pairs,
        median_scope_shift=statistics.median(deltas) if deltas else None,sample_variance=statistics.variance(deltas) if len(deltas)>1 else None,
        metric_checks=len(metric_errors),max_metric_error=max(metric_errors,default=None),
        scope='One previously reused developer task, one post-Pizza selected diagnostic, two split seeds. Public single-fold metrics only; not independent tasks, final quality or a new agent method.')
    out=R/'readout-v1';out.mkdir()
    write(out/'summary.json',result)
    import csv
    with (out/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(result))


def main():
    os.umask(0o077)
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','submit','controller','worker','status','analyze']);p.add_argument('--index',type=int)
    a=p.parse_args()
    if a.mode=='prepare':prepare()
    elif a.mode=='analyze':analyze()
    elif a.mode=='worker':core().worker(a.index)
    else:getattr(core(),a.mode)()


if __name__=='__main__':main()
