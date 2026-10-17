"""Classic patch/multiscale LightGBM positive controls, NOT a new method.

Executed inside the same AIRA task image as CNN controls. No evaluation labels,
external data, nearest-page lookup, pretrained weights or LLM calls.
"""
import csv
import json
import os
import time
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, median_filter, minimum_filter, maximum_filter
from lightgbm import LGBMRegressor

started = time.monotonic()
root = Path('/workspace/data')  # Native AIRA readonly bind, verified in launcher.
assert (root/'train').is_dir() and (root/'train_cleaned').is_dir()
seed = int(os.environ['PAGE_STUDY_SEED'])
mode = os.environ['PAGE_STUDY_MODEL']
assert mode in ('patch', 'multiscale')
rng = np.random.default_rng(seed)

def image(p):
    with Image.open(p) as im: return np.array(im.convert('L'), dtype=np.float32)/255

def features(x):
    h,w=x.shape; padded=np.pad(x,1,mode='reflect')
    planes=[padded[j:j+h,i:i+w] for j in range(3) for i in range(3)]
    if mode=='multiscale':
        for sigma in (1,3,9):
            sm=gaussian_filter(x,sigma,mode='reflect')
            planes.extend((sm,x-sm))
        for size in (3,9):
            planes.extend((median_filter(x,size,mode='reflect'),
                           minimum_filter(x,size,mode='reflect'),
                           maximum_filter(x,size,mode='reflect')))
    return np.stack(planes,axis=-1).reshape(-1,len(planes))

names=sorted(p.name for p in (root/'train').glob('*.png'))
assert names
# Uniform rendering sampling; identical training rows in the two feature arms.
xs=[];ys=[]
for n in names:
    x,y=image(root/'train'/n),image(root/'train_cleaned'/n)
    assert x.shape==y.shape
    ix=rng.choice(x.size,size=min(2048,x.size),replace=False)
    xs.append(features(x)[ix]);ys.append(y.ravel()[ix])
X,Y=np.concatenate(xs),np.concatenate(ys)
model=LGBMRegressor(n_estimators=400,learning_rate=.05,num_leaves=31,max_depth=-1,
                   min_child_samples=20,reg_lambda=1.,random_state=seed,n_jobs=2,
                   deterministic=True,force_col_wise=True,verbosity=-1)
model.fit(X,Y)
fit_seconds=time.monotonic()-started
with Path('/workspace/submission.csv').open('w',newline='') as f:
    out=csv.writer(f);out.writerow(['id','value'])
    for n in sorted((root/'test').glob('*.png')):
        x=image(n);h,w=x.shape
        pred=np.clip(model.predict(features(x)),0,1).reshape(h,w)
        out.writerows((f'{int(n.stem)}_{j+1}_{i+1}',float(pred[j,i]))
                      for j in range(h) for i in range(w))
Path('pixel_training.json').write_text(json.dumps(dict(model=mode,seed=seed,
    training_images=len(names),training_pixels=len(Y),features=X.shape[1],
    fit_seconds=fit_seconds,total_seconds=time.monotonic()-started,
    versions=dict(numpy=np.__version__,lightgbm=__import__('lightgbm').__version__),
    no_cuda_training_expected=True)))
