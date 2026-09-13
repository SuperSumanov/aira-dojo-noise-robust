"""Small fixed-space AutoML reference, executed inside the unchanged task image.

No LLM, critic, external grader, private label path, or partial-fidelity trial.
Every training subprocess and persisted incumbent is charged to one deadline.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import time

FAMILIES=('rf','extra','hist','logistic','svc','knn')


def encode(x):return (json.dumps(x,sort_keys=True,allow_nan=False)+'\n').encode()
def digest(raw):return hashlib.sha256(raw).hexdigest()


def exclusive(path,raw):
    with Path(path).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())


def specifications(seed,count=64):
    if type(seed) is not int or not 1<=count<=64:raise ValueError('frozen trial count')
    rng=random.Random(seed)
    rows=[dict(family='rf',n_estimators=100,max_depth=12,min_samples_leaf=1,max_features='sqrt',random_state=0,scale=False)]
    for _ in range(count-1):
        family=rng.choice(FAMILIES);p=dict(family=family,random_state=rng.randrange(2**31),scale=family in ('logistic','svc','knn'))
        if family in ('rf','extra'):
            p.update(n_estimators=rng.choice([100,200,400]),max_depth=rng.choice([8,12,20,None]),
                min_samples_leaf=rng.choice([1,2,4]),max_features=rng.choice(['sqrt',.5,1.0]))
        elif family=='hist':p.update(max_iter=rng.choice([50,100,200]),learning_rate=10**rng.uniform(-2,-.5),
            max_leaf_nodes=rng.choice([15,31,63]),l2_regularization=10**rng.uniform(-3,1))
        elif family=='logistic':p.update(C=10**rng.uniform(-3,2),max_iter=1000)
        elif family=='svc':p.update(C=10**rng.uniform(-2,2),gamma=rng.choice(['scale','auto']),kernel=rng.choice(['rbf','poly']))
        else:p.update(n_neighbors=rng.choice([3,5,9,15,25]),weights=rng.choice(['uniform','distance']),p=rng.choice([1,2]))
        rows.append(p)
    return rows


def data_for(task):
    import pandas as pd
    train=pd.read_csv('data/train.csv');test=pd.read_csv('data/test.csv')
    if task=='leaf-classification':
        y=train['species'].astype(str);X=train.drop(columns=['id','species']).copy();Z=test.drop(columns=['id']).copy()
    elif task=='spaceship-titanic':
        y=train['Transported'].astype(str).str.lower().map({'true':1,'false':0})
        if y.isna().any():raise ValueError('label format')
        y=y.astype(int);X=train.drop(columns=['PassengerId','Name','Transported']).copy();Z=test.drop(columns=['PassengerId','Name']).copy()
    else:raise ValueError('task scope')
    for c in X.select_dtypes(include=['object','category','bool']).columns:
        X[c]=X[c].fillna('__MISSING__').astype(str);Z[c]=Z[c].fillna('__MISSING__').astype(str)
    return X,y,Z,test


def pipeline_for(X,spec):
    from sklearn.ensemble import RandomForestClassifier,ExtraTreesClassifier,HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.svm import SVC
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.preprocessing import OrdinalEncoder,StandardScaler
    from sklearn.impute import SimpleImputer
    from sklearn.compose import ColumnTransformer
    from sklearn.pipeline import make_pipeline
    params=dict(spec);family=params.pop('family');scale=params.pop('scale');seed=params.pop('random_state')
    if family=='rf':model=RandomForestClassifier(**params,random_state=seed,n_jobs=6)
    elif family=='extra':model=ExtraTreesClassifier(**params,random_state=seed,n_jobs=6)
    elif family=='hist':model=HistGradientBoostingClassifier(**params,random_state=seed)
    elif family=='logistic':model=LogisticRegression(**params,random_state=seed,n_jobs=1)
    elif family=='svc':model=SVC(**params,random_state=seed,probability=True)
    elif family=='knn':model=KNeighborsClassifier(**params,n_jobs=6)
    else:raise ValueError('family')
    cat=list(X.select_dtypes(include=['object','category','bool']).columns);num=[c for c in X.columns if c not in cat]
    prep=ColumnTransformer([('num',SimpleImputer(strategy='median'),num),
        ('cat',OrdinalEncoder(handle_unknown='use_encoded_value',unknown_value=-1),cat)])
    steps=[prep]+([StandardScaler()] if scale else [])+[model]
    return make_pipeline(*steps)


def better(value,best,task):return best is None or (value<best if task=='leaf-classification' else value>best)


def trial(config_path):
    import pandas as pd
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import log_loss,accuracy_score
    from threadpoolctl import threadpool_limits
    cfg=json.loads(Path(config_path).read_bytes());task=cfg['task'];out=Path(cfg['output'])
    with threadpool_limits(limits=6):
        X,y,Z,test=data_for(task);model=pipeline_for(X,cfg['spec'])
        xt,xv,yt,yv=train_test_split(X,y,test_size=.2,random_state=0,stratify=y)
        model.fit(xt,yt)
        value=float(log_loss(yv,model.predict_proba(xv),labels=model.classes_) if task=='leaf-classification' else accuracy_score(yv,model.predict(xv)))
        if not math.isfinite(value):raise ValueError('non-finite validation')
        candidate=dict(validation=value,improved=better(value,cfg['best_validation'],task),spec=cfg['spec'])
        if candidate['improved']:
            model.fit(X,y)
            if task=='leaf-classification':
                submission=pd.DataFrame(model.predict_proba(Z),columns=model.classes_);submission.insert(0,'id',test['id'].to_numpy())
            else:submission=pd.DataFrame({'PassengerId':test['PassengerId'],'Transported':model.predict(Z).astype(bool)})
            raw=submission.to_csv(index=False).encode();exclusive(out/'submission.csv',raw)
            candidate['submission_sha256']=digest(raw)
        exclusive(out/'trial-result.json',encode(candidate))


def publish(directory,index,raw,metadata,*,deadline_ns,clock=time.monotonic_ns):
    # A promotion that fails its post-fsync clock check remains in the audit
    # log but is not an eligible incumbent.
    data=directory/f'trial-{index:03d}.csv';exclusive(data,raw)
    durable=clock();record=dict(metadata,file=data.name,sha256=digest(raw),durable_ns=durable,
        deadline_ns=deadline_ns,eligible=durable<deadline_ns)
    exclusive(directory/f'trial-{index:03d}.json',encode(record))
    return record


def stop_owned(child):
    if child.poll() is not None:return
    if child.pid<=1 or os.getpgid(child.pid)!=child.pid:raise RuntimeError('owned child group not isolated')
    os.killpg(child.pid,signal.SIGTERM)
    try:child.wait(timeout=3)
    except subprocess.TimeoutExpired:
        if child.poll() is None:os.killpg(child.pid,signal.SIGKILL)
        child.wait(timeout=3)


def search(config_path):
    cfg=json.loads(Path(config_path).read_bytes());task=cfg['task'];deadline=cfg['deadline_ns'];seed=cfg['seed']
    if type(deadline) is not int or deadline<=time.monotonic_ns():raise ValueError('expired total budget')
    trials=Path('classic-trials');trials.mkdir();inc=Path('classic-incumbents');inc.mkdir()
    specs=specifications(seed);exclusive('classic-specifications.json',encode(specs));best=None;rows=[]
    for i,spec in enumerate(specs):
        remaining=(deadline-time.monotonic_ns())/1e9
        if remaining<=5:break
        out=trials/f'{i:03d}';out.mkdir()
        trial_cfg=dict(task=task,output=str(out),spec=spec,best_validation=best)
        path=out/'config.json';exclusive(path,encode(trial_cfg));started=time.monotonic_ns()
        row=dict(index=i,spec_sha256=digest(encode(spec)),started_ns=started,status='unknown',validation=None,published=False)
        with (out/'output.private.log').open('xb') as log:
            child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'trial',str(path)],
                stdout=log,stderr=log,start_new_session=True)
            try:
                child.wait(timeout=min(300,remaining-3))
                row['status']='completed' if child.returncode==0 else 'program_error'
            except subprocess.TimeoutExpired:
                stop_owned(child);row['status']='timeout'
            finally:
                # Also contain the owned trial on an interrupted/erroring wait.
                if child.poll() is None:stop_owned(child)
        result_path=out/'trial-result.json'
        if row['status']=='completed':
            result=json.loads(result_path.read_bytes());value=result['validation'];row['validation']=value
            if result['improved']:
                raw=(out/'submission.csv').read_bytes()
                if digest(raw)!=result['submission_sha256'] or not better(value,best,task):raise ValueError('trial binding')
                receipt=publish(inc,i,raw,dict(task=task,seed=seed,validation=value,spec_sha256=row['spec_sha256']),deadline_ns=deadline)
                if receipt['eligible']:best=value;row['published']=True
        row['finished_ns']=time.monotonic_ns();rows.append(row)
        exclusive(out/'attempt.json',encode(row))
    exclusive('classic-finished.json',encode(dict(task=task,seed=seed,deadline_ns=deadline,attempts=len(rows),
        finished_ns=time.monotonic_ns(),best_validation=best,rows=rows)))


if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1] not in ('trial','search'):raise SystemExit('explicit mode/config required')
    globals()[sys.argv[1]](sys.argv[2])
