"""Do paired seeds also couple first attempted programs? Closed18997 only.

Descriptive after closure, not a new quality gate. No prompt/code/output/labels
exported. Exact bytes and AST identity are not semantic or lineage identity.
"""
import ast,hashlib,json,re
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/scheduling-selective-20261017-v1')
PIN='1783555a7c680021b2a1bae874798f1042c0bfe79d0b11af70fa7f2a75d26e32'
PRIMARY='0bd972126ab1bb9427ea93e446be3d3e245955c8bd5aa7e08778b7afa05c3514'
SECRET=re.compile(r'(?i)sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,}')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
 assert sha(R/'plan.json')==PIN and sha(R/'readout-20261017-v1/summary.json')==PRIMARY
 assert read(R/'closed.json')['complete']==32
 plan=read(R/'plan.json');inputs={r['index']:r for r in read(R/'readout-20261017-v1/input-checks.json')}
 rows=[]
 for spec in plan['schedule']:
  ep=R/f"episode-{spec['index']}"
  paths=sorted(ep.glob('candidate-*.private.json'),key=lambda p:int(p.name.split('-')[-1].split('.')[0]))
  row={k:spec[k] for k in ('index','block','repeat','pool_mode','task','seed')}
  row.update(first_prompt_sha256=inputs[spec['index']]['observed_sha256'],attempted=len(paths),code_sha256=None,ast_sha256=None,ast_parsed=False)
  assert inputs[spec['index']]['passed']
  if paths:
   code=read(paths[0])['code'];assert not SECRET.search(code),'credential-shape hit, do not export'
   row['first_private_sha256']=sha(paths[0]);row['first_candidate_index']=int(paths[0].name.split('-')[-1].split('.')[0])
   row['code_sha256']=hashlib.sha256(code.encode()).hexdigest()
   try:tree=ast.parse(code)
   except SyntaxError:pass
   else:row.update(ast_parsed=True,ast_sha256=hashlib.sha256(ast.dump(tree,include_attributes=False).encode()).hexdigest())
  rows.append(row)
 pairs=[]
 for a in [r for r in rows if r['pool_mode']=='shared']:
  b=next(r for r in rows if r['pool_mode']=='selective' and r['seed']==a['seed'] and r['task']==a['task'])
  assert a['first_prompt_sha256']==b['first_prompt_sha256']
  pairs.append(dict(task=a['task'],repeat=a['repeat'],seed=a['seed'],indices=[a['index'],b['index']],same_prompt=True,
    both_attempted=bool(a['attempted'] and b['attempted']),same_code=bool(a['code_sha256'] and a['code_sha256']==b['code_sha256']),
    both_ast_parsed=a['ast_parsed'] and b['ast_parsed'],same_ast=bool(a['ast_sha256'] and a['ast_sha256']==b['ast_sha256'])))
 assert len(rows)==32 and len(pairs)==16
 result=dict(plan_sha256=PIN,primary_sha256=PRIMARY,source_sha256=sha(Path(__file__)),rows=rows,pairs=pairs,
  totals={k:sum(p[k] for p in pairs) for k in ('same_prompt','both_attempted','same_code','both_ast_parsed','same_ast')},
  boundary='First attempted program, not guaranteed first transport response. Same prompt/seed does not guarantee same proposal under dynamic batching, parsing or failure paths. This does not identify which mechanism caused differences or make the randomized policy contrast invalid. Exact/AST identity is not semantic similarity. No gate, score, execution or source bundle changed.')
 dest=R/'first-program-pairing-20261017.safe.json'
 with dest.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
 print(json.dumps(dict(sha256=sha(dest),totals=result['totals'],pairs=pairs)))
if __name__=='__main__':main()
