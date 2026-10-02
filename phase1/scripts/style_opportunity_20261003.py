"""One final fixed nonlexical complement reference, not an agent contribution."""
import argparse,ast,hashlib,importlib.util,json,os,shutil,sys
from pathlib import Path
B=Path('/research/d7/spc/yzyang4');PARENT=B/'nb-ratio-opportunity-20261003-v1'
ROOT=B/'style-opportunity-20261003-v1';SOURCE='style_opportunity_20261003.py'
NB_SHA='12106a3f2d50fbd54e337e8ab33563817960049fd753b7cedb9970ed1011a397'
assert hashlib.sha256((PARENT/'nb_ratio_opportunity_20261003.py').read_bytes()).hexdigest()==NB_SHA
sys.path.insert(0,str(PARENT))
import nb_ratio_opportunity_20261003 as runner
read=runner.read;write=runner.write;sha=runner.sha;PY=runner.PY
SEEDS=(104001,104002,104003)

def tail():
    return '''
import json as _j,shutil as _sh,hashlib as _h,re
from pathlib import Path as _P
from sklearn.ensemble import HistGradientBoostingClassifier as _HGB
from scipy.optimize import minimize_scalar as _min
_begin=time.monotonic();_seed=int(os.environ['PYTHONHASHSEED'])
# No word identities, external dictionaries, pretrained models or query labels.
def _style(text):
    words=re.findall(r"[A-Za-z]+",text);lengths=np.array([len(w) for w in words] or [0],dtype=float)
    n=max(len(text),1);nw=max(len(words),1)
    sentences=[s for s in re.split(r'[.!?]+',text) if s.strip()]
    counts=[len(re.findall(r'[A-Za-z]+',s)) for s in sentences] or [0]
    out=[np.log1p(len(text)),np.log1p(len(words)),lengths.mean(),lengths.std(),float(np.median(lengths)),
         sum(len(w)>6 for w in words)/nw,sum(len(w)<=3 for w in words)/nw,len(set(w.lower() for w in words))/nw,
         sum(c.isupper() for c in text)/n,sum(c.isdigit() for c in text)/n,sum(c.isspace() for c in text)/n,
         sum(w.isupper() for w in words)/nw,sum(w.istitle() for w in words)/nw,
         np.log1p(len(sentences)),float(np.mean(counts)),float(np.std(counts))]
    out += [text.count(c)/n for c in list(',;:!?-().')+[chr(34),chr(39)]]
    out += [len(re.findall(p,text))/n for p in [r'\\.\\.\\.',r'--',r'\\s{2,}',r'\\n']]
    return out
_sx=np.array([_style(t) for t in X_train_text]);_sq=np.array([_style(t) for t in X_test_text])
assert _sx.shape[1]==31 and np.isfinite(_sx).all() and np.isfinite(_sq).all()
_oof=np.zeros((len(y_train),3));_query=np.zeros((len(X_test_text),3));_fold_id=np.full(len(y_train),-1)
for _fold,(_ti,_vi) in enumerate(StratifiedKFold(n_splits=5,shuffle=True,random_state=_seed).split(_sx,y_train)):
    _model=_HGB(max_iter=120,max_leaf_nodes=15,learning_rate=.05,l2_regularization=5.,min_samples_leaf=30,
        early_stopping=False,random_state=_seed)
    _model.fit(_sx[_ti],y_train[_ti]);assert list(_model.classes_)==[0,1,2]
    _oof[_vi]=_model.predict_proba(_sx[_vi]);_query+=_model.predict_proba(_sq)/5
    _fold_id[_vi]=_fold
    print('STYLE_REFERENCE_FOLD_DONE',_fold,flush=True)
_original=safe_clip((1-best_w)*oof_tfidf_c+best_w*oof_emb_c)
def _loss(w):return float(log_loss(y_train,safe_clip((1-w)*_original+w*_oof)))
_opt=_min(_loss,bounds=(0.,1.),method='bounded',options={'xatol':1e-9,'maxiter':100});assert _opt.success
_w=min([0.,float(_opt.x),1.],key=lambda w:(_loss(w),w))
_pred=safe_clip((1-_w)*test_prob_final+_w*_query)
_sh.copyfile('submission.csv','original.csv');_sub=submission.copy();_sub[classes]=_pred;_sub.to_csv('calibrated.csv',index=False)
# Fixed compatibility keys shared with the already reviewed readout; nb means
# the alternative reference here, which is style HGB, NOT an NB classifier.
np.savez('public-calibration.private.npz',original_oof=_original,nb_oof=_oof,labels=y_train,fold_id=_fold_id,
    query_original=test_prob_final,query_nb=_query,query_blend=_pred)
_receipt=dict(role='KNOWN_STYLE_HGB_REFERENCE_NOT_NB_OR_AGENT',fold_seed=_seed,weight=_w,
    public_original_loss=_loss(0.),public_nb_loss=_loss(1.),public_blend_loss=_loss(_w),feature_count=_sx.shape[1],
    best_embedding_weight=float(best_w),public_rows=len(y_train),query_rows=len(_pred),classes=classes,
    fits=5,convergence_warnings=0,additional_seconds=time.monotonic()-_begin,
    files={n:_h.sha256(_P(n).read_bytes()).hexdigest() for n in ['original.csv','calibrated.csv','public-calibration.private.npz']})
with open('calibration-receipt.json','x') as _f:_j.dump(_receipt,_f,sort_keys=True)
print('STYLE_REFERENCE_DONE',flush=True)
'''

runner.ROOT=ROOT;runner.SOURCE=SOURCE;runner.SEEDS=SEEDS
runner.runner.ROOT=ROOT;runner.runner.SEEDS=SEEDS;runner.runner.tail=tail
runtime=runner.runtime

def prepare():
    import inspect,subprocess
    assert not ROOT.exists() and sha(PARENT/'plan.json')=='b810f31f70ea89e81bf1a1557544c0e9fe072ce6534fdb1449665be7f12e53fc'
    pp=read(PARENT/'plan.json');ROOT.mkdir(mode=0o700)
    for rel,h in pp['files'].items():
        if rel.startswith(('configs/','bin/')) or rel=='run.sbatch':continue
        assert sha(PARENT/rel)==h
        dst=ROOT/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(PARENT/rel,dst)
    shutil.copyfile(__file__,ROOT/SOURCE)
    for name in ('bin','configs'):(ROOT/name).mkdir()
    (ROOT/'bin/singularity').write_text(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(ROOT)!r})\nfrom style_opportunity_20261003 import runtime\nruntime().task_runtime()\n');os.chmod(ROOT/'bin/singularity',0o700)
    for i,seed in enumerate(SEEDS):
        cfg=read(PARENT/'configs/0.json');(ROOT/f'episode-{i}').mkdir()
        cfg['id']=f'style-opportunity-{i}';cfg['logger']['output_dir']=str(ROOT/f'episode-{i}/native-log')
        cfg['metadata'].update(seed=seed,base_path=str(ROOT/'source'),script_id='style-opportunity-20261003')
        cfg['interpreter']['env']['PYTHONHASHSEED']=str(seed);cfg['task']['cache_dir']=str(ROOT/'no-official-data')
        write(ROOT/f'configs/{i}.json',cfg)
    batch=(PARENT/'run.sbatch').read_text().replace(str(PARENT),str(ROOT)).replace('nb-ratio-opportunity','style-opportunity').replace('nb_ratio_opportunity_20261003.py',SOURCE)
    (ROOT/'run.sbatch').write_text(batch)
    plan=dict(pp);plan.update(protocol='known-nonlexical-style-opportunity-v1',seeds=SEEDS,classifier_fits=15,
        files={str(f.relative_to(ROOT)):sha(f) for f in ROOT.rglob('*') if f.is_file()},
        fixed='31 fixed nonlexical style statistics; HistGradientBoosting max_iter120/15leaves/lr.05/l2=5/minleaf30/noearlystop; 5-fold query ensemble; no sweep',
        only_training_labels='Style features are stateless functions of individual text. Each classifier fits fold-train only. Blend selected on public OOF. No external labels before closure.',
        external_dependency=dict(path=str(PARENT/'nb_ratio_opportunity_20261003.py'),sha256=NB_SHA),
        output_names='calibrated.csv means style blend; NPZ/receipt nb keys mean style reference only for shared reader compatibility',
        seeds_note='Parent CV/fit42 fixed; style folds use104001-104003. Same dataset, not three tasks.',
        endpoint='Original minus publicly selected style blend; fixed raw style diagnostic; no external winner selection.',
        limitation='Last fixed complement opportunity check in this window. Known stylometry+GBDT, not novel method or automated discovery. Reused adaptive development set and historically selected incumbent. Added fits are not an equal-cost E2E method win.')
    write(ROOT/'plan.json',plan)
    # Reuse the COMPLETE synthetic tail smoke, changing only the explicit new
    # classifier count and providing re for raw text statistics.
    runner.tail=tail
    src=inspect.getsource(runner.cpu)
    assert src.count("rr['fits']==15")==1
    src=src.replace("rr['fits']==15","rr['fits']==5").replace('import ast,numpy as np,pandas as pd,tempfile,time','import ast,numpy as np,pandas as pd,tempfile,time,re')
    assert src.count('scope=dict(np=np,pd=pd,time=time,os=os,')==1
    src=src.replace('scope=dict(np=np,pd=pd,time=time,os=os,','scope=dict(re=re,np=np,pd=pd,time=time,os=os,')
    old_texts="['raven dark night','cosmic ancient fear','life human friend'][c]+' token'+str(i)"
    assert src.count(old_texts)==1
    src=src.replace(old_texts,"['LOWER? REALLY? YES!','a very long extraordinary unpunctuated description','I. See. It.'][c]+' token'+str(i)")
    src=src.replace("prefix='nb-reference-fixture-'","prefix='style-reference-fixture-'")
    src=src.replace("ratio_sign_fixture=True","shared_ratio_sign_fixture=True,style_feature_count=31")
    exec(compile(src,'style_cpu_smoke','exec'),runner.__dict__);runner.cpu()

if __name__=='__main__':
    os.umask(0o077);a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','submit','controller','worker','status']);a.add_argument('--index',type=int);x=a.parse_args()
    if x.mode=='prepare':prepare()
    elif x.mode=='worker':runner.runner.worker(x.index)
    elif x.mode=='status':runner.runner.status()
    else:getattr(runner,x.mode)()
