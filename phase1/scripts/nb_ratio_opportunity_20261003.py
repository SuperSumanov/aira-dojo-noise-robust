"""Known NB-ratio logistic reference, not NB-SVM replication or agent method.

Reuse the frozen calibration runner for isolation, not its scientific protocol.
Only public fold labels fit NB ratios, logistic heads and a scalar blend weight.
The three seeds alter fold membership and thus the query fold ensemble.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import calibration_opportunity_20261003 as runner

B=Path('/research/d7/spc/yzyang4')
ROOT=B/'nb-ratio-opportunity-20261003-v1'
PREV=B/'calibration-opportunity-20261003-v1'
SEEDS=(103901,103902,103903)
SOURCE='nb_ratio_opportunity_20261003.py'
read=runner.read;write=runner.write;sha=runner.sha;PY=runner.PY

def tail():
    return '''
import json as _j, shutil as _sh, hashlib as _h, warnings as _warnings
from pathlib import Path as _P
from sklearn.base import clone as _clone
from sklearn.exceptions import ConvergenceWarning as _CW
from scipy.optimize import minimize_scalar as _min
_begin=time.monotonic()
_seed=int(os.environ['PYTHONHASHSEED'])
_folds=list(StratifiedKFold(n_splits=5,shuffle=True,random_state=_seed).split(X_train_text,y_train))
_nb_oof=np.zeros((len(y_train),3));_nb_query=np.zeros((len(X_test_text),3))
_fold_id=np.full(len(y_train),-1);_warn=0
for _fold,(_ti,_vi) in enumerate(_folds):
    _word=_clone(tfidf_word);_char=_clone(tfidf_char)
    _xt=sparse.hstack([_word.fit_transform(X_train_text[_ti]),_char.fit_transform(X_train_text[_ti])]).tocsr()
    _xv=sparse.hstack([_word.transform(X_train_text[_vi]),_char.transform(X_train_text[_vi])]).tocsr()
    _xq=sparse.hstack([_word.transform(X_test_text),_char.transform(X_test_text)]).tocsr()
    _pv=np.zeros((len(_vi),3));_pq=np.zeros((len(X_test_text),3))
    for _class in range(3):
        _yy=(y_train[_ti]==_class)
        _pos=1+np.asarray(_xt[_yy].sum(axis=0)).ravel()
        _neg=1+np.asarray(_xt[~_yy].sum(axis=0)).ravel()
        _ratio=np.log((_pos/_pos.sum())/(_neg/_neg.sum()))
        _model=LogisticRegression(C=4.,solver='liblinear',max_iter=1000,tol=1e-4,random_state=_seed)
        with _warnings.catch_warnings(record=True) as _caught:
            _warnings.simplefilter('always',_CW)
            _model.fit(_xt.multiply(_ratio).tocsr(),_yy)
        _warn+=sum(issubclass(_w.category,_CW) for _w in _caught)
        assert list(_model.classes_)==[False,True]
        _pv[:,_class]=_model.predict_proba(_xv.multiply(_ratio).tocsr())[:,1]
        _pq[:,_class]=_model.predict_proba(_xq.multiply(_ratio).tocsr())[:,1]
    _nb_oof[_vi]=safe_clip(_pv);_nb_query+=safe_clip(_pq)/5
    _fold_id[_vi]=_fold
    print('NB_REFERENCE_FOLD_DONE',_fold,flush=True)
assert (_fold_id>=0).all() and _warn==0
_original=safe_clip((1-best_w)*oof_tfidf_c+best_w*oof_emb_c)
def _loss(_w):return float(log_loss(y_train,safe_clip((1-_w)*_original+_w*_nb_oof)))
_opt=_min(_loss,bounds=(0.,1.),method='bounded',options={'xatol':1e-9,'maxiter':100})
assert _opt.success
# Include exact endpoints and prefer smaller weight on exact ties.
_weight=min([0.,float(_opt.x),1.],key=lambda _w:(_loss(_w),_w))
_pred=safe_clip((1-_weight)*test_prob_final+_weight*_nb_query)
_sh.copyfile('submission.csv','original.csv')
_submission=submission.copy();_submission[classes]=_pred
_submission.to_csv('calibrated.csv',index=False)
np.savez('public-calibration.private.npz',original_oof=_original,nb_oof=_nb_oof,labels=y_train,fold_id=_fold_id,
    query_original=test_prob_final,query_nb=_nb_query,query_blend=_pred)
_receipt=dict(role='KNOWN_NB_RATIO_LOGISTIC_REFERENCE_NOT_CALIBRATION_OR_AGENT',fold_seed=_seed,weight=_weight,
    public_original_loss=_loss(0.),public_nb_loss=_loss(1.),public_blend_loss=_loss(_weight),
    best_embedding_weight=float(best_w),public_rows=len(y_train),query_rows=len(_pred),classes=classes,
    fits=15,convergence_warnings=_warn,additional_seconds=time.monotonic()-_begin,
    files={n:_h.sha256(_P(n).read_bytes()).hexdigest() for n in ['original.csv','calibrated.csv','public-calibration.private.npz']})
with open('calibration-receipt.json','x') as _f:_j.dump(_receipt,_f,sort_keys=True)
print('NB_REFERENCE_DONE',flush=True)
'''

runner.ROOT=ROOT;runner.SEEDS=SEEDS;runner.tail=tail
runtime=runner.runtime

def prepare():
    assert not ROOT.exists()
    assert sha(PREV/'plan.json')=='bb2652e5957b6e043138c1c50de95874c487a8ea4fd5e72bb164fe6e03fd8a94'
    previous=read(PREV/'plan.json');ROOT.mkdir(mode=0o700)
    for rel,h in previous['files'].items():
        if not(rel.startswith(('source/','forets_','opencl-vendors/')) or rel in ('v6_runtime.py','calibration_opportunity_20261003.py')):continue
        assert sha(PREV/rel)==h
        dest=ROOT/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(PREV/rel,dest)
    shutil.copyfile(__file__,ROOT/SOURCE)
    for name in ('bin','configs','starts'):(ROOT/name).mkdir()
    shutil.copyfile(PREV/'starts/parent.private.json',ROOT/'starts/parent.private.json')
    (ROOT/'bin/singularity').write_text(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(ROOT)!r})\nfrom nb_ratio_opportunity_20261003 import runtime\nruntime().task_runtime()\n')
    os.chmod(ROOT/'bin/singularity',0o700)
    for i,seed in enumerate(SEEDS):
        cfg=read(PREV/'configs/0.json');(ROOT/f'episode-{i}').mkdir()
        cfg['id']=f'nb-ratio-opportunity-{i}';cfg['logger']['output_dir']=str(ROOT/f'episode-{i}/native-log')
        cfg['metadata'].update(seed=seed,base_path=str(ROOT/'source'),script_id='nb-ratio-opportunity-20261003')
        cfg['interpreter']['env']['PYTHONHASHSEED']=str(seed);cfg['task']['cache_dir']=str(ROOT/'no-official-data')
        write(ROOT/f'configs/{i}.json',cfg)
    batch=(PREV/'run.sbatch').read_text().replace(str(PREV),str(ROOT)).replace('calibration-opportunity','nb-ratio-opportunity').replace('calibration_opportunity_20261003.py',SOURCE).replace('00:20:00','00:25:00').replace('1140s','1440s')
    (ROOT/'run.sbatch').write_text(batch)
    write(ROOT/'plan.json',dict(protocol='known-nb-ratio-logistic-opportunity-v1',commit=runner.COMMIT,
        seeds=SEEDS,runs=3,task='spooky-author-identification',classifier_fits=45,
        files={str(f.relative_to(ROOT)):sha(f) for f in ROOT.rglob('*') if f.is_file()},
        fixed='Unchanged parent, same image/hardware/public split. NB C4 liblinear, alpha1 ratios, parent word+char settings, 5-fold ensemble. No hyperparameter grid.',
        only_training_labels='Every vocabulary, IDF and NB ratio fits fold-train only. Blend selected on public OOF. External development labels unopened until closure.',
        output_names='calibrated.csv is the NB blend for runner compatibility; not temperature calibration',
        seeds_note='Parent CV/fit42 remains fixed; NB folds vary. Distinct-query hashes must be reported; same underlying dataset is not 3 tasks.',
        endpoint='Original-minus-public-selected-NB-blend development logloss, raw NB diagnostic also reported; no external winner selection.',
        opportunity_gate='all3 valid, median blend improvement >=0.005, no negative seed; conditional request CI must also be reported, not a confirmation test',
        cap_seconds=300,allocation_seconds=1500,gpus=2,gpu_hours_cap=3000/3600,paid_api=0,base_model_updated=False,
        limitation='Known NB-weighted logistic variant, not exact NB-SVM or novel agent. Historical selected strong parent; adaptive reused D_search. NB adds fits and fold ensemble: not a single classifier-coefficient ablation or equal-cost E2E win.'))
    cpu()

def cpu():
    import ast,numpy as np,pandas as pd,tempfile,time
    from scipy.sparse import csr_matrix
    from sklearn.linear_model import LogisticRegression
    p=runner.check();m=runtime()
    from dojo.config_dataclasses.run import RunConfig
    for i in range(3):
        cfg=RunConfig.load_from_json(ROOT/f'configs/{i}.json');cfg.validate()
        assert not Path(cfg.task.private_dir).exists()
    ast.parse(read(ROOT/'starts/parent.private.json')['code']+tail())
    x=csr_matrix(np.tile([[3.,0.,1.],[0.,3.,1.]],(20,1)));y=np.tile([True,False],20)
    pos=1+np.asarray(x[y].sum(0)).ravel();neg=1+np.asarray(x[~y].sum(0)).ravel()
    r=np.log(pos/pos.sum())-np.log(neg/neg.sum())
    assert r[0]>0 and r[1]<0 and abs(r[2])<1e-12
    model=LogisticRegression(C=4,solver='liblinear',random_state=1).fit(x.multiply(r).tocsr(),y)
    assert (model.predict(x.multiply(r).tocsr())==y).all()
    # Exercise the actual appended branch, including fold vectorizers, fitting,
    # blend selection and serialization, on synthetic public data before GPU use.
    from scipy import sparse
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import log_loss
    classes=['EAP','HPL','MWS'];labels=np.tile(np.arange(3),40)
    texts=np.array([['raven dark night','cosmic ancient fear','life human friend'][c]+' token'+str(i) for i,c in enumerate(labels)])
    raw=np.full((120,3),1/3);query=raw[:9];submission=pd.DataFrame(query,columns=classes);submission.insert(0,'id',np.arange(9))
    scope=dict(np=np,pd=pd,time=time,os=os,sparse=sparse,LogisticRegression=LogisticRegression,
        StratifiedKFold=StratifiedKFold,log_loss=log_loss,X_train_text=texts,X_test_text=texts[:9],y_train=labels,
        tfidf_word=TfidfVectorizer(min_df=2,ngram_range=(1,2)),tfidf_char=TfidfVectorizer(min_df=2,analyzer='char_wb',ngram_range=(3,5)),
        best_w=0,oof_tfidf_c=raw,oof_emb_c=raw,test_prob_final=query,classes=classes,submission=submission,
        safe_clip=lambda q:np.clip(q,1e-15,1-1e-15)/np.clip(q,1e-15,1-1e-15).sum(1,keepdims=True))
    old=os.getcwd();old_seed=os.environ.get('PYTHONHASHSEED');os.environ['PYTHONHASHSEED']='103901'
    try:
        with tempfile.TemporaryDirectory(prefix='nb-reference-fixture-') as tmp:
            os.chdir(tmp);submission.to_csv('submission.csv',index=False);exec(tail(),scope)
            rr=read(Path('calibration-receipt.json'));assert rr['public_blend_loss']<rr['public_original_loss'] and rr['fits']==15
            for f,h in rr['files'].items():assert sha(f)==h
    finally:
        os.chdir(old)
        if old_seed is None:os.environ.pop('PYTHONHASHSEED',None)
        else:os.environ['PYTHONHASHSEED']=old_seed
    subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    receipt=dict(status='PASS',typed_configs=3,ratio_sign_fixture=True,actual_tail_synthetic=True,plan_sha256=sha(ROOT/'plan.json'))
    write(ROOT/'cpu.json',receipt);print(json.dumps(receipt))

def submit():
    plan=runner.check();m=runtime();assert not (ROOT/'submit-intent.json').exists()
    assert read(ROOT/'cpu.json')['plan_sha256']==sha(ROOT/'plan.json') and sha(m.infra.TASK_IMAGE)==m.infra.IMAGE_SHA
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=25).split()
    assert not set(jobs)-{'12535'}
    with (ROOT/'capacity.tmp').open('xb') as f:os.posix_fallocate(f.fileno(),0,256*1024**2)
    (ROOT/'capacity.tmp').unlink();write(ROOT/'submit-intent.json',dict(utc=m.utc(),plan_sha256=sha(ROOT/'plan.json')))
    r=subprocess.run(['sbatch','--parsable','--chdir='+str(ROOT),'--output='+str(ROOT/'allocation-%j.out'),'--error='+str(ROOT/'allocation-%j.err'),str(ROOT/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=r.stdout.strip().split(';')[0]
    if r.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; no retry')
    write(ROOT/'launch.json',dict(job=job,plan_sha256=sha(ROOT/'plan.json')))
    print(json.dumps(dict(status='SUBMITTED',job=job,gpu_hours_cap=plan['gpu_hours_cap'])))

def controller():
    runner.check();m=runtime();assert read(ROOT/'launch.json')['job']==os.environ['SLURM_JOB_ID']
    def run(i):
        ep=ROOT/f'episode-{i}'
        cmd=['srun','--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=6','--gres=gpu:1','--time=00:09:00',str(PY),'-B',str(ROOT/SOURCE),'worker','--index',str(i)]
        with (ep/'worker.private.log').open('xb') as f:r=subprocess.run(cmd,env=m.infra.clean_env(),stdout=f,stderr=f,timeout=550)
        write(ep/'closed.json',dict(returncode=r.returncode));return r.returncode
    with ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(run,range(3)))
    write(ROOT/'closed.json',dict(returncodes=codes,utc=m.utc()))
    if any(codes):raise RuntimeError('worker failure')

if __name__=='__main__':
    os.umask(0o077);a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','submit','controller','worker','status']);a.add_argument('--index',type=int);args=a.parse_args()
    if args.mode=='worker':runner.worker(args.index)
    elif args.mode=='status':runner.status()
    else:globals()[args.mode]()
