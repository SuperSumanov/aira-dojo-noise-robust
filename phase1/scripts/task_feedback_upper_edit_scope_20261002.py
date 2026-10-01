"""Posthoc first-revision change scope; not a causal mediator analysis."""
import argparse,ast,difflib,hashlib,json,statistics,sys
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/task-feedback-upper-20261002-v1')
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run():
    assert sha(ROOT/'plan.json')=='9fe231e1b9e2da8cb51fadb7ff9844b074c10e8e3dc64d1d1f3be170fb0703a0'
    assert (ROOT/'all-closed.json').exists()
    sys.path.insert(0,str(ROOT));from task_feedback_real_20261001 import m
    m.check();m.setup()
    from dojo.utils.code_parsing import extract_code
    rows=[]
    for s in read(ROOT/'plan.json')['schedule']:
        ep=ROOT/f'episode-{s["index"]}';p=ep/'action-1/generation.private.json'
        row=dict(index=s['index'],task=s['task'],arm=s['arm'],seed=s['seed'],generated=p.exists())
        if p.exists():
            a=extract_code(read(ep/'action-0/node.private.json')['code'])
            b=extract_code(read(p)['response'])
            x=[q.strip() for q in a.splitlines() if q.strip()];y=[q.strip() for q in b.splitlines() if q.strip()]
            removed=added=0
            for tag,i,j,k,l in difflib.SequenceMatcher(None,x,y,autojunk=False).get_opcodes():
                if tag!='equal':removed+=j-i;added+=l-k
            row.update(parent_nonblank_lines=len(x),child_nonblank_lines=len(y),removed_lines=removed,added_lines=added,edit_fraction=(removed+added)/(len(x)+len(y)),parent_code_sha256=hashlib.sha256(a.encode()).hexdigest(),child_code_sha256=hashlib.sha256(b.encode()).hexdigest())
            for name,code in [('parent',a),('child',b)]:
                try:
                    tree=ast.parse(code)
                    imports=sorted({n.module.split('.')[0] if isinstance(n,ast.ImportFrom) and n.module else v.name.split('.')[0] for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom)) for v in n.names})
                    row[name+'_imports']=imports
                except SyntaxError:row[name+'_imports']=None
            result=ep/'action-1/result.json';row['first_revision_valid']=read(result)['valid'] if result.exists() else None
        rows.append(row)
    groups=[]
    for task in sorted({r['task'] for r in rows}):
        for arm in 'ABC':
            z=[r for r in rows if r['task']==task and r['arm']==arm];v=[r['edit_fraction'] for r in z if r.get('generated')]
            groups.append(dict(task=task,arm=arm,planned=len(z),valid_revisions=sum(r.get('first_revision_valid') is True for r in z),edit_fraction_median=statistics.median(v),edit_fraction_sample_variance=statistics.variance(v),values=v))
    return dict(scope='Posthoc first-revision text-change proxy, not semantic correctness, proof of collateral harm, or causally adjusted treatment effect; retain all arms',rows=rows,groups=groups)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=run()
    with a.out.open('x') as f:json.dump(out,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'groups':out['groups'],'scope':out['scope']},sort_keys=True))
