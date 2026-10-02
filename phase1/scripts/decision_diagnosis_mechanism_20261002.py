"""Inspect pre-result proposals/check observations without candidate outcome files."""
import argparse, ast, hashlib, json, re
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/decision-diagnosis-20261002-v1')
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
def safe_read(p):
    raw=p.read_bytes()
    if SECRET.search(raw): raise ValueError('credential shape withheld')
    return json.loads(raw)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def inspect(index,include_code=False):
    s=next(x for x in safe_read(R/'plan.json')['schedule'] if x['index']==index)
    ep=R/f'episode-{index}'; output={'index':index,'task':s['task'],'arm':s['arm'],'reads_candidate_scores':False}
    first=ep/'action-1/generation.private.json'; obs=ep/'action-1/node.private.json'; final=ep/'action-2/generation.private.json'
    if first.exists():
        response=safe_read(first)['response']; output['first_plan']=response.split('```',1)[0]
        if response.strip().splitlines()[0].strip()=='CHECK':
            if include_code: output['check_program']=response.split('```python',1)[-1].rsplit('```',1)[0]
            if obs.exists(): output['check_observation']=safe_read(obs)['terminal'][-12000:]
    if final.exists():
        generation=safe_read(final); response=generation['response']; output['final_plan_before_execution']=response.split('```',1)[0]
        output['final_usage']=generation.get('usage',{})
        output['final_fence_count']=response.count('```')
        blocks=re.findall(r'```python\s*\n(.*?)```',response,re.S)
        output['final_has_one_python_block']=len(blocks)==1
        if len(blocks)==1:
            try:
                tree=ast.parse(blocks[0]); output['final_imports']=sorted({n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module})
                output['final_function_names']=[n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
                parent=safe_read(R/'starts'/f'{s["start"]}.private.json')['code']
                output['ast_changed']=ast.dump(tree)!=ast.dump(ast.parse(parent))
            except SyntaxError: output['final_syntax']='INVALID'
    output['bindings']={str(p.relative_to(R)):sha(p) for p in (first,obs,final) if p.exists()}
    print(json.dumps(output,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('index',type=int);p.add_argument('--code',action='store_true');a=p.parse_args();inspect(a.index,a.code)
