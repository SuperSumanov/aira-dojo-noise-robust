"""Closed-only, score-masked trace inspection. No raw examples or predictions."""
import argparse,ast,hashlib,json,re
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/public-example-feedback-20261003-v1')
PLAN='40e6bc3301c1db52fa09a794577c0b5dc95533302b0e460a044942a6485c5376'
SECRET=re.compile(rb'(?:sk-[A-Za-z0-9_.-]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|Bearer\s+\S{16,})',re.I)
def read(p):
    raw=p.read_bytes()
    assert not SECRET.search(raw),'credential-shaped source; suppress'
    return json.loads(raw)
def mask(text):
    # Do not expose scalar scores in rationale before independently recording mechanism.
    return re.sub(r'(?<![A-Za-z_])[-+]?\d*\.\d+(?:[eE][-+]?\d+)?','<decimal>',text)
def outline(code):
    try:tree=ast.parse(code)
    except SyntaxError:return {'parse':False}
    calls=sorted({ast.unparse(x.func) for x in ast.walk(tree) if isinstance(x,ast.Call)})
    assignments=[]
    for n in tree.body:
        if isinstance(n,ast.Assign):assignments.append(','.join(ast.unparse(x) for x in n.targets)+' <- '+type(n.value).__name__)
        if isinstance(n,(ast.FunctionDef,ast.ClassDef)):assignments.append(type(n).__name__+': '+n.name)
    return dict(parse=True,calls=calls,top_level=assignments)
def main():
    a=argparse.ArgumentParser();a.add_argument('indices',nargs='+',type=int);a.add_argument('--code-step',type=int);a.add_argument('--task-metric',action='store_true');x=a.parse_args()
    assert hashlib.sha256((R/'plan.json').read_bytes()).hexdigest()==PLAN
    assert read(R/'closed.json')['service_closed'] and (R/'all-closed.json').exists()
    for i in x.indices:
        assert i in range(8)
        if x.task_metric:
            p=R/f'episode-{i}/action-1/request.private.json'
            q=read(p)['prompt']
            task=q.split('\nTASK:\n',1)[1].split('\nSUCCESSFUL CODE LEDGER:\n',1)[0]
            lines=[line for line in task.splitlines() if re.search(r'log.?loss|auc|lower|higher|minimi|maximi|evaluat|metric',line,re.I)]
            print(json.dumps(dict(index=i,request_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),task_sha256=hashlib.sha256(task.encode()).hexdigest(),task_metric_lines=lines),sort_keys=True))
            continue
        for step in range(1,7):
            if x.code_step is not None and step!=x.code_step:continue
            d=R/f'episode-{i}/action-{step}'
            if not (d/'generation.private.json').exists():continue
            raw=read(d/'generation.private.json')['response']
            blocks=re.findall(r'```python\s*\n(.*?)```',raw,re.S)
            outside=re.sub(r'```python\s*\n.*?```','',raw,flags=re.S)
            result=read(d/'result.json') if (d/'result.json').exists() else {}
            out=dict(index=i,step=step,format=read(d/'format.json')['status'],
                     kind=result.get('kind'),execution_success=result.get('execution_success'),
                     timed_out=result.get('timed_out'),reason=mask(outside)[:2200],
                     code_sha256=hashlib.sha256(blocks[0].encode()).hexdigest() if len(blocks)==1 else None,
                     outline=outline(blocks[0]) if len(blocks)==1 else {'blocks':len(blocks)})
            if x.code_step is not None and len(blocks)==1:out['code']=blocks[0]
            print(json.dumps(out,ensure_ascii=False,sort_keys=True))
if __name__=='__main__':main()
