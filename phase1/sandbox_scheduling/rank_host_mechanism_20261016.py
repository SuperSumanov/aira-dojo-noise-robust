"""Closed18819 post-hoc host spacing/AST scope, no new execution or scoring."""
import ast
import hashlib
import json
from pathlib import Path
import statistics
from closed_clock_screen_20261016 import SECRET

R=Path('/research/d7/spc/yzyang4/clock-rank-20261016-v1')
PIN='4c22748699952da0b79bf862e1db5e785b7d2a9fb951bb26ee9c21be47ca3306'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def timing(steps):
    assert steps and all(s['end']>=s['start'] for s in steps)
    span=steps[-1]['end']-steps[0]['start'];gaps=[b['start']-a['end'] for a,b in zip(steps,steps[1:])]
    assert span>0 and all(x>=0 for x in gaps)
    return dict(steps=len(steps),host_envelope_seconds=span,steps_per_host_envelope_second=len(steps)/span,
        between_host_calls_median=statistics.median(gaps),between_host_calls_max=max(gaps),
        host_gaps_over_one_second=sum(x>1 for x in gaps),
        optimizer_names=sorted({x['optimizer'] for x in steps}),
        gradient_parameter_counts=sorted({x['gradient_parameters'] for x in steps}))
def guards(code):
    assert not SECRET.search(code),'credential shape: withhold source'
    tree=ast.parse(code);parents={child:parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    out=[]
    for n in ast.walk(tree):
        if not isinstance(n,(ast.If,ast.While)):continue
        if not any(isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr in ('time','monotonic','perf_counter') for x in ast.walk(n.test)):continue
        if isinstance(n,ast.If) and not any(isinstance(x,(ast.Break,ast.Return)) for b in n.body+n.orelse for x in ast.walk(b)):continue
        ancestor=parents.get(n);loops=[]
        while ancestor is not None:
            if isinstance(ancestor,ast.For):
                names=[x.id.lower() for x in ast.walk(ancestor.target) if isinstance(x,ast.Name)]
                kind='fold' if any('fold' in s for s in names) else 'epoch' if any('epoch' in s for s in names) else 'other'
                loops.append(kind)
            ancestor=parents.get(ancestor)
        out.append(dict(enclosing_loop_kinds=loops,numeric_literals=[x.value for x in ast.walk(n.test) if isinstance(x,ast.Constant) and type(x.value) in (int,float)]))
    return out
def main():
    assert sha(R/'plan.json')==PIN and (R/'closed.json').exists()
    p=read(R/'plan.json');rows=[]
    assert read(R/'readout-20261016-v1/summary.json')['complete']==16
    for row in p['schedule']:
        rows.append(dict(index=row['index'],program=row['program'],block=row['block'],mode=row['mode'],
            **timing(read(R/f"episode-{row['index']}/gpu-training.json")['host_step_intervals'])))
    out=dict(posthoc=True,source_sha256=sha(Path(__file__)),plan_sha256=PIN,rows=rows,
        static_guard_scopes=[dict(program=i,guards=guards((R/f'programs/{i}.private.py').read_text())) for i in range(4)],
        boundary='Host call spacing includes data loading, forward/backward, validation and synchronization; it is NOT kernel throughput. Static loop-name heuristic is not a runtime branch/epoch/fold trace. No inference about SchedMate evictions from these averages.')
    dest=R/'host-mechanism-20261016.safe.json'
    with dest.open('x') as f:json.dump(out,f,indent=2,allow_nan=False)
    print(json.dumps(out))
if __name__=='__main__':main()
