"""Frozen public-only page retrieval controls; outside CUDA-required R14.

Purpose: test the importance of source-page duplication, NOT claim a new MLE
method, a fair R14 arm, or an independent unseen-page generalization result.
Four predeclared controls: clean/noisy prototypes x raw/highpass cosine.
All query predictions are sealed before DEV references are opened. No fitting
to DEV labels; no protected files, official test, model service or GPU usage.
"""
import os
for _k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_k]='2'
import hashlib,json,time
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

B=Path('/research/d7/spc/yzyang4')
PUBLIC=B/'scheduling-image-live-2plus4-20261011-v1/dev-views/denoising-dirty-documents/public'
OUT=B/'page-retrieval-diagnostic-20261018-v1'
MODES=('clean_raw','clean_highpass','noisy_raw','noisy_highpass')

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,x):
    with Path(p).open('x') as f:json.dump(x,f,sort_keys=True,indent=2,allow_nan=False)
def pix(p):return np.asarray(Image.open(p).convert('L'),dtype=np.uint8)
def feature(x,highpass):
    a=x.astype(np.float64)/255
    if highpass:a=a-gaussian_filter(a,1.5,mode='reflect')
    a=a.ravel();a=a-a.mean();norm=np.linalg.norm(a)
    assert norm>0
    return a/norm
def predict(public,out):
    """This function can read only the supplied public subtree; no reference input."""
    t=time.monotonic();public,out=Path(public),Path(out)
    assert public==PUBLIC and not out.exists()
    out.mkdir(mode=0o700)
    names=sorted(p.name for p in (public/'train').glob('*.png'))
    query=sorted(p.name for p in (public/'test').glob('*.png'))
    noisy=[pix(public/'train'/n) for n in names]
    clean=[pix(public/'train_cleaned'/n) for n in names]
    ident=[hashlib.sha256(a.tobytes()).hexdigest() for a in clean]
    assert len(names)==92 and len(query)==11 and all(a.shape==b.shape for a,b in zip(noisy,clean))
    public_inputs={str(p.relative_to(public)):sha(p) for d in ('train','train_cleaned','test')
                   for p in sorted((public/d).glob('*.png'))}
    proto={}
    for mode in MODES:
        arr=clean if mode.startswith('clean') else noisy
        byshape={}
        for i,x in enumerate(arr):
            byshape.setdefault(x.shape,[]).append(i)
        proto[mode]={shape:(ids,np.stack([feature(arr[i],'highpass' in mode) for i in ids]))
                     for shape,ids in byshape.items()}
    selected=[];train_controls=[]
    for mode in MODES:
        full={}
        for n in query:
            x=pix(public/'test'/n);ids,m=proto[mode][x.shape]
            z=feature(x,'highpass' in mode);sim=m@z
            best=int(np.argmax(sim));i=ids[best]
            order=np.argsort(-sim,kind='stable')
            # Unique-page runner up, not another corruption of the same page.
            other=next((int(j) for j in order if ident[ids[j]]!=ident[i]),None)
            selected.append({'mode':mode,'query':n,'train':names[i],'clean_pixel_sha256':ident[i],
                             'clean_png_sha256':sha(public/'train_cleaned'/names[i]),
                             'cosine':float(sim[best]),
                             'different_page_margin':float(sim[best]-sim[other]) if other is not None else None})
            full[n]=clean[i]
        np.savez_compressed(out/(mode+'.prediction.private.npz'),**full)
        # Public-training counterfactuals: remove this rendering vs entire page.
        for j,x in enumerate(noisy):
            ids,m=proto[mode][x.shape];sim=m@feature(x,'highpass' in mode)
            for exclusion in ('leave_rendering_out','leave_page_out'):
                allowed=[k for k,i in enumerate(ids) if (i!=j if exclusion=='leave_rendering_out' else ident[i]!=ident[j])]
                if not allowed:raise ValueError('empty eligible prototype set')
                k=max(allowed,key=lambda k:(float(sim[k]),-k));i=ids[k]
                err=(clean[i].astype(np.float64)-clean[j].astype(np.float64))/255
                train_controls.append({'mode':mode,'exclusion':exclusion,'query':names[j],
                                       'exact_page':ident[i]==ident[j],
                                       'sse':float(np.sum(err*err)),'pixels':int(err.size)})
    put(out/'selection.private.json',selected)
    put(out/'train-controls.private.json',train_controls)
    seal={'protocol':'source-page-retrieval-diagnostic-v1','code_sha256':sha(__file__),
          'modes':list(MODES),'sigma':1.5,'selection':'cosine argmax, sorted filename tie-break',
          'input_scope':str(public),'public_input_sha256':public_inputs,
          'files':{p.name:sha(p) for p in out.iterdir() if p.is_file()},
          'predict_seconds':time.monotonic()-t,'no_dev_references_read':True,
          'limits':['CPU diagnostic violates old R14 CUDA-trained-model requirement; NOT a fair arm in that experiment.',
                    'Controls change retrieval representation/prototype source, not a novel algorithm.',
                    'Public LOO folds overlap; no independent sample-count or generalization claim.']}
    put(out/'prediction-seal.json',seal)
    print(json.dumps({'prediction_sealed':True,'seal_sha256':sha(out/'prediction-seal.json'),
                      'query_images':len(query),'public_train_images':len(names),
                      'public_clean_pixel_unique':len(set(ident)),'predict_seconds':seal['predict_seconds']}))

def audit(out):
    """Separate trusted audit stage, never calls predict or changes its outputs."""
    t=time.monotonic();out=Path(out);seal=json.loads((out/'prediction-seal.json').read_text())
    assert seal['code_sha256']==sha(__file__)
    assert all(sha(out/k)==h for k,h in seal['files'].items())
    view=PUBLIC.parent;manifest=json.loads((view/'manifest.json').read_text())
    assert manifest['not_official_test'] and manifest['reserved_content_not_copied']
    refs=view/'search-reference'
    assert all(sha(refs/n)==h for n,h in manifest['search_reference_files'].items())
    rows=[]
    for mode in MODES:
        with np.load(out/(mode+'.prediction.private.npz'),allow_pickle=False) as pred:
            assert set(pred.files)==set(manifest['query_ids'])
            for n in manifest['query_ids']:
                y=pix(refs/n);p=pred[n];assert y.shape==p.shape and p.dtype==np.uint8
                d=(p.astype(np.float64)-y.astype(np.float64))/255
                rows.append({'mode':mode,'query':n,'sse':float(np.sum(d*d)),
                             'pixels':int(d.size),'pixel_exact':bool(np.array_equal(y,p))})
    train=json.loads((out/'train-controls.private.json').read_text())
    groups=[]
    for mode in MODES:
        rr=[r for r in rows if r['mode']==mode]
        groups.append({'mode':mode,'images':len(rr),'exact_images':sum(r['pixel_exact'] for r in rr),
                       'rmse':float(np.sqrt(sum(r['sse'] for r in rr)/sum(r['pixels'] for r in rr))),
                       'pixels':sum(r['pixels'] for r in rr),
                       'public_controls':[{ 'exclusion':ex,'images':len(tt),
                         'exact_images':sum(r['exact_page'] for r in tt),
                         'rmse':float(np.sqrt(sum(r['sse'] for r in tt)/sum(r['pixels'] for r in tt)))}
                          for ex in ('leave_rendering_out','leave_page_out')
                          for tt in [[r for r in train if r['mode']==mode and r['exclusion']==ex]]]})
    safe={'status':'CLOSED_DIAGNOSTIC_NOT_E2E','groups':groups,
          'prediction_seal_sha256':sha(out/'prediction-seal.json'),'source_sha256':sha(__file__),
          'view_sha256':sha(view/'manifest.json'),'predict_seconds':seal['predict_seconds'],
          'audit_seconds':time.monotonic()-t,'gpu_seconds':0,'paid_api':0,
          'training_data': 'only public train/noisy and train_cleaned',
          'limits':seal['limits']+['Known reused DEV; not a new generalization set.',
             'Template retrieval can exploit the observed training/reference page dependency; no general MLE improvement claim.']}
    put(out/'audit.private.json',rows);put(out/'summary.safe.json',safe)
    print(json.dumps(safe))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('action',choices=['predict','audit']);a=p.parse_args()
    if a.action=='predict':predict(PUBLIC,OUT)
    else:audit(OUT)
