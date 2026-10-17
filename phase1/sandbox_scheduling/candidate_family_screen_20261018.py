"""Read-only hypothesis screen of three CLOSED, owned development batches.

No program execution, raw code export, new label access, or scoring calls.
Spelling-level AST summaries are not semantic proofs or causal evidence.
"""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import time

BASE = Path('/research/d7/spc/yzyang4')
BATCHES = ('scheduling-pooling-20261016-v3', 'scheduling-colocation-20261016-v1',
           'scheduling-selective-20261017-v1')
SECRET = re.compile(r'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})|[?&](?:access_?token|token|api_?key|secret|password|signature|sig)=[^\s&#]+')
APIS = {'Conv2d','ConvTranspose2d','Linear','BatchNorm2d','LayerNorm','GroupNorm',
        'MaxPool2d','AvgPool2d','AdaptiveAvgPool2d','Dropout','Dropout2d','Sigmoid',
        'ReLU','LeakyReLU','GELU','MSELoss','L1Loss','BCEWithLogitsLoss','CrossEntropyLoss',
        'Adam','AdamW','SGD','RMSprop','StepLR','CosineAnnealingLR','ReduceLROnPlateau',
        'OneCycleLR','LambdaLR','ExponentialLR','LinearLR','SequentialLR','DataLoader',
        'RandomCrop','RandomResizedCrop','RandomHorizontalFlip','RandomVerticalFlip',
        'ColorJitter','Normalize','Resize','RandomRotation','ToTensor','mse_loss',
        'interpolate','pad','sigmoid','clip','clamp','median_filter','gaussian_filter',
        'GaussianBlur','fastNlMeansDenoising','RandomForestRegressor',
        'ExtraTreesRegressor','LGBMRegressor','HistGradientBoostingRegressor'}

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
def name(x):
    if isinstance(x,ast.Name): return x.id
    if isinstance(x,ast.Attribute): return name(x.value)+'.'+x.attr
    return ''
def number(x):
    if isinstance(x,ast.Constant) and isinstance(x.value,(int,float,bool)):
        return x.value
    if isinstance(x,(ast.Tuple,ast.List)) and len(x.elts)<=5:
        v=[number(z) for z in x.elts]
        if all(z is not None for z in v):return v
    return None
def structure(code):
    assert not SECRET.search(code), 'credential-shape hit; emit nothing'
    tree=ast.parse(code); calls=[]; clock=0; epochs=[]; returns=[]
    for n in ast.walk(tree):
        if isinstance(n,ast.Call):
            full=name(n.func); short=full.rsplit('.',1)[-1]
            if short in APIS:
                calls.append({'api':short,'args':[number(a) for a in n.args],
                              'kwargs':{k.arg:number(k.value) for k in n.keywords
                                        if k.arg and number(k.value) is not None}})
            if full in ('time.time','time.monotonic','time.perf_counter'):clock+=1
        if isinstance(n,ast.For) and isinstance(n.iter,ast.Call) and name(n.iter.func)=='range':
            vals=[number(a) for a in n.iter.args]
            if isinstance(n.target,ast.Name) and re.search('epoch',n.target.id,re.I):
                epochs.append(vals)
        if isinstance(n,ast.FunctionDef) and n.name=='forward':
            for r in ast.walk(n):
                if isinstance(r,ast.Return):
                    returns.append({'binary_add':isinstance(r.value,ast.BinOp) and isinstance(r.value.op,ast.Add),
                                    'binary_sub':isinstance(r.value,ast.BinOp) and isinstance(r.value.op,ast.Sub)})
    return {'calls':calls,'clock_calls':clock,'epoch_range_numeric':epochs,
            'forward_return_shapes':returns}

def main():
    t=time.monotonic(); rows=[]; inputs={}
    for b in BATCHES:
        root=BASE/b
        assert (root/'closed.json').is_file()
        plan=read(root/'plan.json'); assert len(plan['schedule'])==32
        inputs[str(root/'plan.json')]=sha(root/'plan.json')
        for r in plan['schedule']:
            ep=root/f"episode-{r['index']}"
            for p in sorted(ep.glob('candidate-*.json')):
                if '.private.' in p.name:continue
                c=read(p)
                if not(c['elapsed_seconds']<=1020 and c.get('valid') is True and
                       c.get('exit_code')==0 and not c.get('timed_out')):continue
                raw=p.with_name(p.stem+'.private.json'); code=read(raw)['code']
                assert hashlib.sha256(code.encode()).hexdigest()==c['code_sha256']
                inputs[str(raw)]=sha(raw)
                rows.append({'batch':b,'index':r['index'],'task':r['task'],
                             'candidate':int(p.stem.split('-')[1]),
                             'code_sha256':c['code_sha256'],'structure':structure(code)})
    groups=[]
    for task in sorted({r['task'] for r in rows}):
        rr=[r for r in rows if r['task']==task]
        unique={r['code_sha256']:r for r in rr}
        groups.append({'task':task,'returns':len(rr),'unique_code':len(unique),
                       'unique_programs_with_api':dict(sorted(Counter(a for r in unique.values()
                          for a in {x['api'] for x in r['structure']['calls']}).items()))})
    out={'source_sha256':sha(Path(__file__)),'inputs':inputs,'rows':rows,'groups':groups,
         'elapsed_seconds':time.monotonic()-t,'limits':[
             'AST spellings may miss aliases/library internals; return syntax does not prove residual learning.',
             'No scores, labels, candidate execution, train-state recovery, or treatment effect measured.']}
    dest=BASE/'quota-queue-source-20261017-ymOz45'/'candidate-family-screen-20261018.safe.json'
    with dest.open('x') as f:json.dump(out,f,sort_keys=True,indent=2,allow_nan=False)
    print(json.dumps({'path':str(dest),'sha256':sha(dest),'groups':groups}))

if __name__=='__main__':main()
