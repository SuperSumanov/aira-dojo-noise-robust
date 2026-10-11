"""Public-training-only image development views; no official/test input access.

80/10/10 deterministic identifier split. Reserved 10% is not copied or scored.
Only the public view is container-bound. D_search references stay on trusted host.
"""
import csv, hashlib, json, math, shutil, zipfile
from pathlib import Path

TASKS=('aerial-cactus-identification','denoising-dirty-documents')

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()

def split(names):
    if len(names)!=len(set(names)) or len(names)<30:raise ValueError('duplicate/insufficient IDs')
    if any(Path(n).name!=n for n in names):raise ValueError('unsafe ID')
    ordered=sorted(names,key=lambda n:hashlib.sha256(('r14-image-dev-20261011:'+n).encode()).digest())
    a=8*len(names)//10;b=9*len(names)//10
    return ordered[:a],ordered[a:b],ordered[b:]

def write(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,sort_keys=True,allow_nan=False)

def write_csv(path,columns,rows):
    with Path(path).open('x',newline='') as f:
        w=csv.writer(f);w.writerow(columns);w.writerows(rows)

def prepare(base,out):
    from PIL import Image
    out=Path(out);out.mkdir(mode=0o700)
    specs={}
    for task in TASKS:
        source=Path(base)/task/'prepared/public';root=out/task
        public=root/'public';public.mkdir(parents=True);private=root/'search-reference';private.mkdir(mode=0o700)
        pins={};dimensions={}
        if task==TASKS[0]:
            with (source/'train.csv').open(newline='') as f:
                r=csv.DictReader(f);assert r.fieldnames==['id','has_cactus'];rows=list(r)
            labels={r['id']:int(r['has_cactus']) for r in rows};assert len(labels)==len(rows)
            train,query,reserved=split(list(labels))
            assert set(labels[n] for n in train)==set(labels[n] for n in query)=={0,1}
            for sub in ('train','test'):(public/sub).mkdir()
            pins={str(source/n):digest(source/n) for n in ('train.csv','train.zip')}
            wanted=set(train+query);members={}
            with zipfile.ZipFile(source/'train.zip') as z:
                for info in z.infolist():
                    n=Path(info.filename).name
                    if info.is_dir() or n not in wanted:continue
                    assert info.filename in (n,'train/'+n) and n not in members and info.file_size<2*1024**2
                    members[n]=info
                assert set(members)==wanted
                for n in train+query:
                    dest=public/('train' if n in set(train) else 'test')/n
                    with dest.open('xb') as f:f.write(z.read(members[n]))
                    with Image.open(dest) as im:assert im.size==(32,32);im.verify()
            write_csv(public/'train.csv',['id','has_cactus'],[(n,labels[n]) for n in train])
            write_csv(public/'test.csv',['id'],[(n,) for n in query])
            write_csv(public/'sample_submission.csv',['id','has_cactus'],[(n,.5) for n in query])
            write_csv(private/'labels.csv',['id','has_cactus'],[(n,labels[n]) for n in query])
            description=('Train an image classifier for cactus presence using train/*.jpg and train.csv. Images are 32x32 RGB. '
                         'Predict probabilities for test/*.jpg, in sample_submission.csv ID order. Metric: ROC AUC, higher is better. '
                         'Write /workspace/submission.csv with id,has_cactus. This is a training-only development split, not official test. '
                         'Use a real PyTorch CUDA-trained model; no external downloads or pretrained model downloads. You may use your own training-only validation split. '
                         'Keep training short enough to finish each execution within 300 seconds. GPU memory may be shared; do not infer a dedicated card.\n')
            lower=False;metric='auc'
        else:
            names=[p.name for p in (source/'train').iterdir() if p.is_file() and p.suffix=='.png']
            train,query,reserved=split(names)
            for sub in ('train','train_cleaned','test'):(public/sub).mkdir()
            for n in train+query:
                noisy=source/'train'/n;clean=source/'train_cleaned'/n
                with Image.open(noisy) as im:dimensions[n]=im.size;im.verify()
                with Image.open(clean) as im:assert im.size==dimensions[n];im.verify()
                pins[str(noisy)]=digest(noisy);pins[str(clean)]=digest(clean)
                shutil.copyfile(noisy,public/('train' if n in set(train) else 'test')/n)
                shutil.copyfile(clean,(public/'train_cleaned' if n in set(train) else private)/n)
            def pixel_rows(value=False):
                for n in query:
                    w,h=dimensions[n]
                    for y in range(1,h+1):
                        for x in range(1,w+1):
                            ident=f'{int(Path(n).stem)}_{y}_{x}'
                            yield (ident,.5) if value else (ident,)
            write_csv(public/'test.csv',['id'],pixel_rows())
            write_csv(public/'sample_submission.csv',['id','value'],pixel_rows(True))
            description=('Remove noise from grayscale document images. Train on paired train/*.png and train_cleaned/*.png. '
                         'Predict clean grayscale values for test/*.png. Match sample_submission.csv exactly: id,value, '
                         'id = image_number_row_column with one-based row and column; values in [0,1]. Write /workspace/submission.csv. '
                         'Metric: pixel RMSE, lower is better. This is a training-only development split, not official test. '
                         'Use a real PyTorch CUDA-trained model, e.g. a small convolutional network trained on patches. '
                         'No external downloads; internal validation uses training pairs only. Each execution must finish within 300 seconds. '
                         'GPU memory may be shared; do not infer a dedicated card.\n')
            lower=True;metric='rmse'
        (public/'description.md').write_text(description)
        manifest=dict(task=task,split_seed='r14-image-dev-20261011',train_ids=train,query_ids=query,reserved_ids=reserved,
            reserved_content_not_copied=True,query_dimensions={n:dimensions[n] for n in query if n in dimensions},
            source_files=pins,public_files={str(p.relative_to(public)):digest(p) for p in public.rglob('*') if p.is_file()},
            search_reference_files={str(p.relative_to(private)):digest(p) for p in private.iterdir() if p.is_file()},
            not_official_test=True,not_confirmation=True)
        write(root/'manifest.json',manifest)
        specs[task]=dict(view=str(root),view_sha=digest(root/'manifest.json'),lower_is_better=lower,metric_name=metric)
    write(out/'spec.json',specs)
    return specs

class InvalidSubmissionError(ValueError):pass

def score_at(base,spec,task,submission):
    import numpy as np
    import pandas as pd
    from PIL import Image
    from sklearn.metrics import roc_auc_score
    item=spec[task];root=Path(base)/item['view'];manifest=root/'manifest.json'
    if digest(manifest)!=item['view_sha']:raise RuntimeError('development manifest drift')
    m=json.loads(manifest.read_text())
    for n,h in m['search_reference_files'].items():
        if digest(root/'search-reference'/n)!=h:raise RuntimeError('reference drift')
    try:df=pd.read_csv(submission,dtype={'id':str})
    except Exception:raise InvalidSubmissionError('submission schema/readability') from None
    field='has_cactus' if task==TASKS[0] else 'value'
    if list(df.columns)!=['id',field]:raise InvalidSubmissionError('submission schema/readability')
    expected=pd.read_csv(root/'public/test.csv',dtype={'id':str})['id']
    if df['id'].isna().any() or df['id'].duplicated().any() or len(df)!=len(expected) or set(df['id'])!=set(expected):
        raise InvalidSubmissionError('submission ID coverage')
    try:pred=df.set_index('id').loc[expected,field].to_numpy(dtype=float)
    except Exception:raise InvalidSubmissionError('nonnumeric prediction') from None
    if not np.isfinite(pred).all() or (pred<0).any() or (pred>1).any():raise InvalidSubmissionError('invalid prediction value')
    if task==TASKS[0]:
        truth=pd.read_csv(root/'search-reference/labels.csv',dtype={'id':str}).set_index('id').loc[expected,'has_cactus'].to_numpy()
        value=float(roc_auc_score(truth,pred))
    else:
        truth=np.concatenate([np.asarray(Image.open(root/'search-reference'/n).convert('L'),dtype=np.float64).ravel()/255 for n in m['query_ids']])
        if len(truth)!=len(pred):raise RuntimeError('reference pixel coverage')
        value=float(np.sqrt(np.mean((truth-pred)**2)))
    if not math.isfinite(value):raise RuntimeError('nonfinite score')
    return {item['metric_name']:value,'submission_sha256':digest(submission),'view_manifest_sha256':item['view_sha'],'rows':len(pred),'split':'D_search_development_only'}
