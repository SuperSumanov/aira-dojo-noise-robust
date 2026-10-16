"""Static screen on CLOSED18770 only. No candidate content or credentials export.

Clock-dependent break/return and while tests are evidence of a POSSIBLE
resource-sensitive work budget, not proof of runtime dependence or a speedup.
Misses library-internal limits and dynamic code; observations only.
"""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT=Path('/research/d7/spc/yzyang4/scheduling-pooling-20261016-v3')
PIN='a7cc9780c927cdeac3fc1effb214643a387353122e1fa542d3a40116b248d477'
SECRET=re.compile(r'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())

def screen(code):
    if SECRET.search(code):return dict(credential_shape_hit=True,parsed=False)
    try:tree=ast.parse(code)
    except SyntaxError:return dict(credential_shape_hit=False,parsed=False)
    modules={'time'}; funcs=set()
    for n in ast.walk(tree):
        if isinstance(n,ast.Import):
            modules.update(a.asname or a.name for a in n.names if a.name=='time')
        if isinstance(n,ast.ImportFrom) and n.module=='time':
            funcs.update(a.asname or a.name for a in n.names if a.name in ('time','monotonic','perf_counter'))
    def clock(n):
        if not isinstance(n,ast.Call):return False
        f=n.func
        return (isinstance(f,ast.Name) and f.id in funcs or
                isinstance(f,ast.Attribute) and isinstance(f.value,ast.Name)
                and f.value.id in modules and f.attr in ('time','monotonic','perf_counter'))
    tainted=set()
    def dependent(n):
        return any(clock(x) or isinstance(x,ast.Name) and x.id in tainted for x in ast.walk(n))
    # Conservative name-level propagation; not an interprocedural proof.
    for _ in range(len(list(ast.walk(tree)))+1):
        before=len(tainted)
        for n in ast.walk(tree):
            if isinstance(n,(ast.Assign,ast.AnnAssign)) and n.value is not None and dependent(n.value):
                targets=n.targets if isinstance(n,ast.Assign) else [n.target]
                for t in targets:tainted.update(x.id for x in ast.walk(t) if isinstance(x,ast.Name))
        if len(tainted)==before:break
    guards=0
    for n in ast.walk(tree):
        if isinstance(n,ast.While) and dependent(n.test):guards+=1
        if isinstance(n,ast.If) and dependent(n.test):
            if any(isinstance(x,(ast.Break,ast.Return,ast.Raise)) for branch in n.body+n.orelse for x in ast.walk(branch)):
                guards+=1
    return dict(credential_shape_hit=False,parsed=True,clock_calls=sum(clock(n) for n in ast.walk(tree)),
                clock_exit_guards=guards)

def main():
    assert sha(ROOT/'plan.json')==PIN
    assert read(ROOT/'readout-20261016-v1/summary.json')['complete']==32
    plan=read(ROOT/'plan.json');groups={}
    for row in plan['schedule']:
        g=groups.setdefault((row['block'],row['task']),Counter())
        ep=ROOT/f"episode-{row['index']}";codes={}
        journal=ep/'checkpoint/journal.jsonl'
        for line in journal.read_text().splitlines():
            n=json.loads(line);code=n.get('code')
            if isinstance(code,str):codes[hashlib.sha256(code.encode()).hexdigest()]=code
        for p in ep.glob('candidate-*.json'):
            if '.private.' in p.name:continue
            c=read(p)
            if c['elapsed_seconds']>1020:continue
            g['timely_returns']+=1
            valid=c.get('valid') is True and c.get('exit_code')==0 and not c.get('timed_out')
            g['valid_returns']+=int(valid)
            code=codes.get(c['code_sha256'])
            if code is None:g['unmatched_code']+=1;continue
            s=screen(code)
            g['matched_code']+=1
            for k,v in s.items():g[k]+=int(v)
            if s.get('clock_exit_guards',0):g['programs_with_clock_exit_guard']+=1
            if valid:
                g['valid_matched_returns']+=1
                if s.get('clock_exit_guards',0):g['valid_with_clock_exit_guard']+=1
    result=dict(root=str(ROOT),plan_sha256=PIN,source_sha256=sha(Path(__file__)),
        pools=[dict(block=b,task=t,counts=dict(g)) for (b,t),g in sorted(groups.items())],
        boundary='Static conservative clock-dependent exit screen; no runtime causality, library internals, new GPU/API/scoring, raw code or secret values.')
    out=ROOT/'clock-screen-20261016-v2.safe.json'
    with out.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(result))

if __name__=='__main__':main()
