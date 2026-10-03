"""Posthoc, score-free unit experiment on four closed source-loader prefixes.

Executes only allowlisted AST loader loops against inert in-memory schema stubs.
No task files, labels, predictions, models, network, or original code side effects.
This establishes loader semantics, not a repaired agent or task-quality benefit.
"""
import ast,csv,hashlib,itertools,json,re,types
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/automatic-specification-20261003-gpu3-v6')
D=R.parent/'loader-mechanism-20261003-v1'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
NAMES=('train.json','test.json','sampleSubmission.csv')
TARGET='requester_received_pizza'
class Column:
    def notna(self):return self
    def sum(self):return 300
class Frame:
    def __init__(self,name):
        self.name=name
        self.columns=['request_id']+([TARGET] if name!='test.json' else [])+(['text'] if name!='sampleSubmission.csv' else [])
        self.shape=(300,len(self.columns))
    def __getitem__(self,key):
        assert key in self.columns
        return Column()
class Handle(str):
    def __enter__(self):return self
    def __exit__(self,*args):return False
def basename(p):return str(p).rsplit('/',1)[-1]
def readframe(p):
    name=basename(p);assert name in NAMES
    return Frame(name)
def load_prefix(step):
    p=R/f'episode-0/action-{step}/generation.private.json'
    raw=p.read_bytes();assert not SECRET.search(raw)
    code=re.findall(r'```python\s*\n(.*?)```',json.loads(raw)['response'],re.S)
    assert len(code)==1
    tree=ast.parse(code[0]);loops=[]
    for node in tree.body:
        if isinstance(node,ast.For) and isinstance(node.target,ast.Name) and node.target.id=='f':
            loops.append(node)
        elif loops and isinstance(node,ast.If) and ast.unparse(node.test)=='train_df is None':
            loops.append(node)
        elif loops:break
    assert loops and isinstance(loops[0],ast.For)
    subtree=ast.fix_missing_locations(ast.Module(body=loops,type_ignores=[]))
    attributes={'endswith','listdir','path','join','read_csv','DataFrame','load','columns','notna','sum','shape'}
    names={'f','files','df','pd','os','json','open','print','list','path','p','fh','data','d','train_df','test_df','data_dir'}
    for node in ast.walk(subtree):
        assert not isinstance(node,(ast.Import,ast.ImportFrom,ast.FunctionDef,ast.ClassDef,ast.While,ast.Lambda))
        if isinstance(node,ast.Attribute):assert node.attr in attributes
        if isinstance(node,ast.Name):assert node.id in names,node.id
    return compile(subtree,'<schema-only-loader>','exec'),hashlib.sha256(raw).hexdigest(),hashlib.sha256(ast.dump(subtree).encode()).hexdigest()
def run(compiled,order):
    env={'__builtins__':{},'files':list(order),'data_dir':'/schema', 'train_df':None,'test_df':None,
        'pd':types.SimpleNamespace(read_csv=readframe,DataFrame=lambda x:x),
        'os':types.SimpleNamespace(listdir=lambda p:list(order),path=types.SimpleNamespace(join=lambda *s:'/'.join(s))),
        'json':types.SimpleNamespace(load=readframe),'open':lambda p,*a:Handle(p),'print':lambda *a,**k:None,'list':list}
    exec(compiled,env,env)
    return env['train_df'].name,env['test_df'].name if env['test_df'] is not None else None
def main():
    assert json.loads((R/'closed.json').read_bytes())['service_closed']
    assert json.loads((R/'readout-v1/verification.json').read_bytes())['status']=='PASS'
    rows=[];sources=[]
    for step in range(1,5):
        compiled,h,a=load_prefix(step);sources.append(dict(step=step,response_file_sha256=h,loader_ast_sha256=a))
        for order in itertools.permutations(NAMES):
            train,test=run(compiled,order)
            rows.append(dict(step=step,order='|'.join(order),selected_train=train,selected_test=test,correct_training_identity=train=='train.json',
                filename_reference_training_identity='train.json',observed_order=order==NAMES))
    assert len(rows)==24 and all(not r['correct_training_identity'] for r in rows if r['observed_order'])
    assert sum(r['correct_training_identity'] for r in rows if r['step']==1)==0
    assert all(sum(r['correct_training_identity'] for r in rows if r['step']==s)==3 for s in (2,3,4))
    summary=dict(status='POSTHOC_SCHEMA_ONLY_MECHANISM',cases=len(rows),sources=sources,source_summary_sha256=hashlib.sha256((R/'readout-v1/summary.json').read_bytes()).hexdigest(),
        by_step=[dict(step=s,correct_identity=sum(r['correct_training_identity'] for r in rows if r['step']==s),total=6) for s in range(1,5)],
        observed_order_cases=4,observed_order_wrong_identity=4,
        interpretation='First loader always prioritizes sample CSV and skips JSON. The other three select whichever target-bearing file is last. Permutations are exhaustive structural cases, not random trials or independent runs.',
        reference='Explicit filename selection is an elementary reference, not a new algorithm. It repairs identity selection in these schema stubs; no full program was repaired or evaluated.',
        limitations='Posthoc selection of four loaders from one failed source trajectory; same-model/template dependence. No prevalence estimate, causal quality gain, agent belief-change test or novelty claim.',
        gpu_hours=0,model_calls=0,task_model_fits=0,raw_data_read=False)
    assert not D.exists();D.mkdir(mode=0o700)
    with (D/'cases.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary['cases_sha256']=hashlib.sha256((D/'cases.csv').read_bytes()).hexdigest()
    with (D/'summary.json').open('x') as f:json.dump(summary,f,sort_keys=True,indent=2)
    print(json.dumps(summary))
if __name__=='__main__':main()
