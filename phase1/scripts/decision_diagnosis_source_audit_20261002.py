"""Static, outcome-blind baseline provenance; cannot prove semantic feature safety."""
import ast, hashlib, json
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/decision-diagnosis-20261002-v1')
def read(p): return json.loads(p.read_bytes())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=read(R/'plan.json'); out=[]
    for i,s in enumerate(p['starts']):
        path=R/'starts'/f'{i}.private.json'; source=read(path)['code']; tree=ast.parse(source)
        literals={n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)}
        suspicious=sorted(x for x in literals if len(x)<120 and any(k in x.lower() for k in ('giver','retrieval','username','flair')))
        imports=sorted({n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module})
        imports+=sorted({a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names})
        out.append(dict(task=s['task'],code_sha256=hashlib.sha256(source.encode()).hexdigest(),
            code_lines=len(source.splitlines()),imports=imports,suspicious_column_literals=suspicious,
            reflective_column_access=any(isinstance(n,ast.Attribute) and n.attr in ('columns','select_dtypes') for n in ast.walk(tree))))
    result=dict(plan_sha256=sha(R/'plan.json'),starts=out,
        scope='Static literal/import inventory only; strings can be exclusion lists, and reflective accesses are unresolved. No result values opened.')
    with (R/'source-audit.json').open('x') as f: json.dump(result,f,sort_keys=True,indent=2)
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
