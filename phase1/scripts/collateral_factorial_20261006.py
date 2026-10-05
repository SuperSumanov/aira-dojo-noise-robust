"""Freeze outcome-independent eligibility and four-vertex executable code variants.

Restoring numeric settings is a diagnostic intervention, not semantic equivalence,
an intent oracle, or an already validated search policy. Original failures remain.
"""
import ast
import copy
import json
import os
from pathlib import Path
import sys

import collateral_sample_20261006 as c
import collateral_bindings_20261006 as b

B=Path('/research/d7/spc/yzyang4')
SRC=B/'collateral-local-20261006-v2'
OUT=B/'collateral-factorial-20261006-v1'
SRC_SHA='4c96405a1d58dcddbf228b801cd7516085a56a2d1eae5d9bd601c2384eb452e4'
EXCLUDED={'seed','random_seed','random_state','n_jobs','num_workers','n_splits','n_folds'}
SALT='collateral-106062-four-per-task'


class Locations(b.Bindings):
    def __init__(self):
        super().__init__(); self.locations={}
    def add(self,name,value):
        key='/'.join(self.scope+[name]); self.locations.setdefault(key,[]).append(value)
        super().add(name,value)


def locations(tree):
    v=Locations();v.visit(tree)
    out={}
    for key,vals in v.slots.items():
        if key.rsplit(':',1)[-1].lower() not in EXCLUDED and len(vals)==1 and vals[0] is not None:
            out['binding:'+key]=v.locations[key][0]
    aliases={}
    for n in ast.walk(tree):
        if isinstance(n,ast.ImportFrom):
            for a in n.names:
                if a.name in c.CLASSES:aliases[a.asname or a.name]=a.name
    calls={}
    for n in ast.walk(tree):
        if not isinstance(n,ast.Call):continue
        name=n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else ''
        name=aliases.get(name,name)
        if name in c.CLASSES:calls.setdefault(name,[]).append(n)
    for name,seq in calls.items():
        if len(seq)!=1 or any(k.arg is None for k in seq[0].keywords):continue
        for k in seq[0].keywords:
            if k.arg.lower() not in EXCLUDED and c.literal(k.value) is not None:
                out['call:'+name+':'+k.arg]=k.value
    return out


def make(a,z):
    ta,tz=ast.parse(a),ast.parse(z);aa,zz=locations(ta),locations(tz)
    keys=[k for k in sorted(aa.keys() & zz.keys()) if c.literal(aa[k])!=c.literal(zz[k])]
    # Both interventions use exactly the same predeclared matched literal slots.
    def transplant(target,donor):
        target=copy.deepcopy(target);dd=locations(donor);tt=locations(target)
        replacements={id(tt[k]):copy.deepcopy(dd[k]) for k in keys}
        class Replace(ast.NodeTransformer):
            def visit(self,node):
                if id(node) in replacements:return replacements[id(node)]
                return super().visit(node)
        target=Replace().visit(target);ast.fix_missing_locations(target)
        compile(target,'numeric-transplant','exec')
        return target
    cp,pc=transplant(tz,ta),transplant(ta,tz)
    variants={'P':ta,'C':tz,'CP':cp,'PC':pc}
    for t in variants.values():compile(t,'factorial','exec')
    assert all(c.literal(locations(cp)[k])==c.literal(aa[k]) for k in keys)
    assert all(c.literal(locations(pc)[k])==c.literal(zz[k]) for k in keys)
    return {k:ast.unparse(t)+'\n' for k,t in variants.items()}, [dict(slot=k,parent=c.literal(aa[k])['literal'],child=c.literal(zz[k])['literal']) for k in keys]


def external_dependency(code):
    tree=ast.parse(code)
    return any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in
               ('from_pretrained','load_state_dict_from_url','load_url','download') for n in ast.walk(tree))


def tests():
    a='C=30\nm=LogisticRegression(C=2,random_state=42)\nx=1\n'
    z='C=.1\nm=LogisticRegression(C=3,random_state=41)\nx=2\n'
    v,slots=make(a,z);assert len(slots)==2
    assert 'random_state=41' in v['CP'] and 'x = 2' in v['CP']
    assert 'random_state=42' in v['PC'] and 'x = 1' in v['PC']
    v,slots=make('m=LogisticRegression(C=1); n=LogisticRegression(C=2)', 'm=LogisticRegression(C=3)')
    assert not slots
    v,slots=make('p={"learning_rate":.1}', 'p={"learning_rate":.2}')
    assert len(slots)==1 and '0.1' in v['CP']
    assert external_dependency('x=AutoModel.from_pretrained("x")')
    assert not external_dependency('m=LogisticRegression(C=1)')
    return dict(fixtures=5,status='PASS')


def main():
    os.umask(0o077);raw=(SRC/'summary.json').read_bytes();assert c.digest(raw)==SRC_SHA
    rows=json.loads(raw)['rows'];OUT.mkdir(mode=0o700,exist_ok=False)
    c.save(OUT/'selection-plan.json',dict(source_sha256=SRC_SHA,script_sha256=c.digest(Path(__file__).read_bytes()),
        tests=tests(), salt=SALT, excluded_slots=sorted(EXCLUDED), max_per_task=4,
        eligibility='Existing numeric change, unique code pair, supported literal locations, no static model-download calls, both historical execution times <=150s; no score or success accessor',
        selection='First four SHA256 ranks of parent+child per task among eligible pairs; retain all exclusion counts and original invalid candidates',
        interpretation='Previously examined development data, not fresh confirmation. Four vertices isolate a fixed syntactic parameter bundle; no semantic or optimality guarantee.',
        execution_plan='At most 2 tasks x 4 edges x 4 vertices =32 programs; 240s program cap; two RTX3090; 2h allocation <=4GPUh; no generator/API/base update',
        vertices=dict(P='original parent',C='original child',CP='child with matched parent numeric settings',PC='parent with matched child numeric settings')))
    allrows=[];pools={};payload={}
    for r in rows:
        o={k:r[k] for k in ('batch','task','episode','step','parent_step')}
        if 'private_index' not in r:o['eligibility']='NO_SUPPORTED_NUMERIC_CHANGE';allrows.append(o);continue
        i=r['private_index'];folder=SRC/f'{i:03d}.private';a=(folder/'parent.py').read_text();z=(folder/'child.py').read_text()
        assert c.digest(a)==r['parent_sha256'] and c.digest(z)==r['child_sha256']
        ep=B/r['batch']/f"episode-{r['episode']}"
        # Only cost, not validity, score, selected flags or utility, is inspected.
        times=[json.loads((ep/f'action-{s}/result.json').read_text()).get('exec_seconds') for s in (r['parent_step'],r['step'])]
        v,slots=make(a,z);o.update(private_index=i,original_seconds=times,numeric_slots=slots)
        if r['duplicate_pair']:reason='DUPLICATE'
        elif not slots:reason='NO_ALLOWED_MATCHED_SLOT'
        elif external_dependency(a) or external_dependency(z):reason='STATIC_EXTERNAL_MODEL_DEPENDENCY'
        elif not all(isinstance(t,(int,float)) and 0<=t<=150 for t in times):reason='COST_OUTSIDE_BOUNDED_REPLAY'
        else:reason='ELIGIBLE'
        o['eligibility']=reason;allrows.append(o)
        if reason=='ELIGIBLE':
            h=c.digest('|'.join((SALT,r['parent_sha256'],r['child_sha256'])))
            entry=dict(**o,parent_sha256=r['parent_sha256'],child_sha256=r['child_sha256'],rank=h)
            pools.setdefault(r['task'],[]).append(entry);payload[i]=v
    selected=[]
    for task,seq in sorted(pools.items()):selected.extend(sorted(seq,key=lambda r:r['rank'])[:4])
    for j,r in enumerate(selected):
        r['case']=j;d=OUT/f'case-{j}.private';d.mkdir()
        for arm,code in payload[r['private_index']].items():
            with (d/(arm+'.py')).open('x') as f:f.write(code)
        r['variant_sha256']={arm:c.digest(code) for arm,code in payload[r['private_index']].items()}
    assert len(selected)<=8 and len(pools)<=2
    counts={reason:sum(r['eligibility']==reason for r in allrows) for reason in sorted({r['eligibility'] for r in allrows})}
    c.save(OUT/'selection.json',dict(counts=counts,assigned_edges=len(selected),assigned_programs=4*len(selected),
        selected=selected,all_rows=allrows,plan_sha256=c.digest((OUT/'selection-plan.json').read_bytes())))
    print(json.dumps(dict(counts=counts,assigned_edges=len(selected),assigned_programs=4*len(selected),
        selected=[{k:r[k] for k in ('case','task','private_index','original_seconds')} for r in selected],
        selection_sha256=c.digest((OUT/'selection.json').read_bytes()))))


if __name__=='__main__':
    if sys.argv[1:]==['--tests']:print(json.dumps(tests()))
    else: assert not sys.argv[1:];main()
