"""Outcome-blind structural qualification on explicitly completed development runs.

No model, candidate execution or metric values. Partial variants are hypothetical
programs, not proven valid repairs. Existing source contents stay remote/private.
"""
import ast
import difflib
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

B=Path('/research/d7/spc/yzyang4')
OUT=B/'edit-factorization-census-20261002-v1'
ROOTS={
 'task-feedback-real-20261001-v6':'15751d3b52bdc42617df02006ce724635f4bf49df6e477686769fd1979d53403',
 'task-feedback-upper-20261002-v1':'9fe231e1b9e2da8cb51fadb7ff9844b074c10e8e3dc64d1d1f3be170fb0703a0',
 'task-feedback-local-edit-20261002-v1':'7bd84ff0e867043b2787d5c07af867eff50370f4e7b6bafa811ef215196c4139',
}
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def tree(s):return ast.parse(s)
def key(n):return ast.dump(n,include_attributes=False)

def factor(parent,child):
    a,b=tree(parent),tree(child)
    ops=difflib.SequenceMatcher(a=[key(n) for n in a.body],b=[key(n) for n in b.body],autojunk=False).get_opcodes()
    edits=[v for v in ops if v[0]!='equal']
    def variant(chosen):
        body=[];i=0
        for op,a0,a1,b0,b1 in ops:
            if op=='equal':body.extend(a.body[a0:a1])
            else:
                body.extend(b.body[b0:b1] if i in chosen else a.body[a0:a1]);i+=1
        result=ast.Module(body=body,type_ignores=[]);ast.fix_missing_locations(result)
        compile(result,'factored-candidate','exec')
        return ast.unparse(result)+'\n'
    assert key(tree(variant(set())))==key(a)
    assert key(tree(variant(set(range(len(edits))))))==key(b)
    cut=(len(edits)+1)//2
    choices=[set(range(cut)),set(range(cut,len(edits)))]
    partial=[variant(c) for c in choices]
    return dict(edit_blocks=len(edits),parent_statements=len(a.body),child_statements=len(b.body),
                split='first ceil(m/2) vs remaining top-level AST edit blocks; source order, no metric',
                distinct_variants=len({key(tree(s)) for s in [parent,child,*partial]}),
                partial_sha256=[hashlib.sha256(s.encode()).hexdigest() for s in partial]),partial

def main():
    os.umask(0o077);OUT.mkdir()
    origin=B/'task-feedback-real-20261001-v6'
    sys.path.insert(0,str(origin));import task_feedback_real_20261001 as runtime
    runtime.setup()
    from dojo.utils.code_parsing import extract_code
    plan=dict(source_sha256=sha(Path(__file__)),roots=ROOTS,score_values_used_for_selection=False,
              question='Do completed proposals support automatic four-vertex edit factorization before any outcome selection?',
              selection='all returned follow-up proposals whose actual parent was valid; all arms retained',
              split='ordered top-level AST LCS edit blocks into first ceil(m/2) and remainder',
              gpu=0,api_calls=0,fits=0,limitations='structure only; no execution validity, causal benefit, new method or novelty claim')
    (OUT/'plan.json').write_text(json.dumps(plan,sort_keys=True,indent=2)+'\n')
    rows=[]
    for basename,expected in ROOTS.items():
        root=B/basename
        assert sha(root/'plan.json')==expected and (root/'all-closed.json').exists()
        schedule=read(root/'plan.json')['schedule']
        for s in schedule:
            ep=root/f'episode-{s["index"]}';assert (ep/'closed.json').exists()
            last=None;best=None;debug_streak=0;cache={}
            actions=sorted(ep.glob('action-*'),key=lambda p:int(p.name.split('-')[1]))
            for action in actions:
                step=int(action.name.split('-')[1]);node=action/'node.private.json';result=action/'result.json'
                if not node.exists() or not result.exists():break
                raw=node.read_bytes();assert not SECRET.search(raw),'credential-bearing node withheld'
                code=json.loads(raw)['code'];digest=hashlib.sha256(code.encode()).hexdigest()
                # Existing JSON has scores as well. Parsing does not make this an
                # unopened dataset; no score/facts field is referenced for selection,
                # factorization, or reporting. Only approved development runs here.
                metadata=read(result)
                valid=bool(metadata['valid']);kind=metadata['kind']
                assert metadata['code_sha256']==digest
                if step:
                    parent=last
                    if cache[last]['valid'] or (debug_streak>=2 and best is not None):parent=best;debug_streak=0
                    assert parent is not None
                    assert kind==('improve' if cache[parent]['valid'] else 'debug')
                    debug_streak=debug_streak+1 if kind=='debug' else 0
                    if cache[parent]['valid']:
                        r=dict(batch=basename,task=s['task'],episode=s['index'],step=step,parent_step=parent,
                               arm=s['arm'],generation_seed=s['seed'],parent_raw_sha256=cache[parent]['sha'],child_raw_sha256=digest)
                        try:pcode=extract_code(cache[parent]['code']);ccode=extract_code(code)
                        except Exception as error:
                            r.update(status='NATIVE_EXTRACTION_REJECTED',error_type=type(error).__name__)
                            rows.append(r);cache[step]=dict(valid=valid,code=code,sha=digest);last=step
                            if (action/'selected.json').exists():assert valid;best=step
                            continue
                        try:details,partial=factor(pcode,ccode)
                        except (SyntaxError,ValueError,TypeError) as error:
                            r.update(status='UNRESOLVED_SYNTAX',error_type=type(error).__name__)
                        else:
                            r.update(status='FACTORIZABLE_AST',**details)
                            if details['edit_blocks']>=2 and details['distinct_variants']==4:
                                ident=f'{len(rows):03d}';folder=OUT/(ident+'.private');folder.mkdir()
                                for name,text in zip(('parent','child','left','right'),(pcode,ccode,*partial)):
                                    (folder/(name+'.py')).write_text(text)
                        rows.append(r)
                cache[step]=dict(valid=valid,code=code,sha=digest);last=step
                if (action/'selected.json').exists():
                    assert valid;best=step
    summary=dict(plan_sha256=sha(OUT/'plan.json'),rows=rows,denominator=len(rows),
                 four_distinct=sum(r.get('distinct_variants')==4 for r in rows),
                 status='STRUCTURAL_ONLY_NO_EXECUTION_OR_EFFECT',metrics_reported=False)
    (OUT/'summary.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')
    counts={}
    for r in rows:
        counts.setdefault(r['task'],dict(proposals=0,four_distinct=0))
        counts[r['task']]['proposals']+=1;counts[r['task']]['four_distinct']+=r.get('distinct_variants')==4
    print(json.dumps(dict(status=summary['status'],denominator=len(rows),four_distinct=summary['four_distinct'],
                          by_task=counts,summary_sha256=sha(OUT/'summary.json')),sort_keys=True))

if __name__=='__main__':main()
