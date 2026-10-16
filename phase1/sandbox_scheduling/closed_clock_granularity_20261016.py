"""Post-hoc static exit scope on sealed18807, not a runtime or policy replay.

Rules fixed before reading scope counts. Loop names are lexical hints only.
Report raw/AST source deduplication; do not call AST hashes independent runs.
No raw code, data, predictions or score values leave the remote machine.
"""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from closed_clock_screen_20261016 import SECRET

ROOT=Path('/research/d7/spc/yzyang4/scheduling-colocation-20261016-v1')
PIN='36ce5852b26de2299755c19a8b9711a1f4161d68abd25a3de6cc7687cdde8560'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())

def classify(code):
    assert not SECRET.search(code),'credential-shape hit; withhold'
    tree=ast.parse(code)
    modules={'time'}; funcs=set(); tainted=set()
    nodes=list(ast.walk(tree)); parent={c:n for n in nodes for c in ast.iter_child_nodes(n)}
    for n in nodes:
        if isinstance(n,ast.Import):modules.update(a.asname or a.name for a in n.names if a.name=='time')
        if isinstance(n,ast.ImportFrom) and n.module=='time':
            funcs.update(a.asname or a.name for a in n.names if a.name in ('time','monotonic','perf_counter'))
    def clock(n):
        if not isinstance(n,ast.Call):return False
        f=n.func
        return (isinstance(f,ast.Name) and f.id in funcs or
                isinstance(f,ast.Attribute) and isinstance(f.value,ast.Name) and
                f.value.id in modules and f.attr in ('time','monotonic','perf_counter'))
    def dependent(n):
        return any(clock(x) or isinstance(x,ast.Name) and x.id in tainted for x in ast.walk(n))
    for _ in range(len(nodes)+1):
        before=len(tainted)
        for n in nodes:
            if isinstance(n,(ast.Assign,ast.AnnAssign)) and n.value is not None and dependent(n.value):
                ts=n.targets if isinstance(n,ast.Assign) else [n.target]
                for t in ts:tainted.update(x.id for x in ast.walk(t) if isinstance(x,ast.Name))
        if len(tainted)==before:break
    def chain(n):
        out=[]
        while n in parent:
            n=parent[n]
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)):break
            out.append(n)
        return out
    def label(loop):
        if isinstance(loop,ast.While):return 'while_other'
        if not isinstance(loop,(ast.For,ast.AsyncFor)):return 'no_lexical_loop'
        text=(ast.unparse(loop.target)+' '+ast.unparse(loop.iter)).lower()
        if re.search(r'fold|kfold',text):return 'fold_named'
        if 'epoch' in text:return 'epoch_named'
        if re.search(r'batch|loader|dataloader',text):return 'batch_or_loader_named'
        return 'other_for'
    scopes=Counter()
    for n in nodes:
        if isinstance(n,ast.While) and dependent(n.test):scopes['while_clock_test']+=1
        if not isinstance(n,(ast.Break,ast.Return,ast.Raise)):continue
        ancestors=chain(n)
        guarded=any(isinstance(a,ast.If) and dependent(a.test) for a in ancestors)
        if not guarded:continue
        if isinstance(n,ast.Break):
            loop=next((a for a in ancestors if isinstance(a,(ast.For,ast.AsyncFor,ast.While))),None)
            assert loop is not None,'invalid unscoped break'
            scopes['break:'+label(loop)]+=1
        else:scopes['function_return' if isinstance(n,ast.Return) else 'raise']+=1
    return dict(ast_sha256=hashlib.sha256(ast.dump(tree,include_attributes=False).encode()).hexdigest(),
                exit_scope_counts=dict(scopes),clock_tainted_names=len(tainted))

def main():
    assert sha(ROOT/'plan.json')==PIN and (ROOT/'closed.json').exists()
    rows=[]
    for s in read(ROOT/'plan.json')['schedule']:
        ep=ROOT/f"episode-{s['index']}"
        for p in sorted(ep.glob('candidate-*.json')):
            if '.private.' in p.name:continue
            c=read(p)
            if c['elapsed_seconds']>1020:continue
            private=p.with_name(p.stem+'.private.json')
            code=read(private)['code']
            assert not SECRET.search(code),'credential-shape hit; withhold'
            source=hashlib.sha256(code.encode()).hexdigest()
            assert source==c['code_sha256']
            valid=c['valid'] is True and c['exit_code']==0 and not c['timed_out']
            rows.append(dict(block=s['block'],task=s['task'],source_sha256=source,valid=valid,**classify(code)))
    assert len(rows)==78 and sum(r['valid'] for r in rows)==38
    groups=[]
    for task in sorted({r['task'] for r in rows}):
        for valid_only in (False,True):
            rr=[r for r in rows if r['task']==task and (not valid_only or r['valid'])]
            ast_unique={r['ast_sha256']:r for r in rr}
            groups.append(dict(task=task,valid_only=valid_only,returns=len(rr),
                unique_raw_sources=len({r['source_sha256'] for r in rr}),unique_ast_sources=len(ast_unique),
                ast_sources_with_scope=dict(Counter(k for r in ast_unique.values() for k in r['exit_scope_counts'])),
                ast_sources_without_detected_exit=sum(not r['exit_scope_counts'] for r in ast_unique.values())))
    out=dict(posthoc=True,analysis_sha256=sha(Path(__file__)),plan_sha256=PIN,groups=groups,rows=rows,
        boundary='Lexical labels, conservative name-level clock propagation, no interprocedural proof. Scope hints do not establish that a loop trains a model or that its branch executed. Same AST is only exact normalization, not family/lineage independence. Source counts are conditioned on closed observed returns; not corpus prevalence, E2E gains, new-source confirmation or a new scheduler. Missing static exits do not establish fixed work. No existing readout is modified.')
    with (ROOT/'clock-granularity-20261016.safe.json').open('x') as f:json.dump(out,f,indent=2,allow_nan=False)
    print(json.dumps(dict(analysis_sha256=out['analysis_sha256'],groups=groups,returns=len(rows),valid=sum(r['valid'] for r in rows))))

if __name__=='__main__':main()
