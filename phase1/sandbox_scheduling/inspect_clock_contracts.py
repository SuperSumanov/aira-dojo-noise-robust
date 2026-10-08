"""Read fixed public clock-branch sources; syntax/conditions, never outcomes."""
import ast
import json
import signal
from pathlib import Path
import census as c
from lifecycle_pilot import read,sha,write

def main():
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('source review cap')));signal.alarm(180)
 structure=c.BASE/'scheduling-branch-screen-20261008-v1/review-v1/structures.json'
 if sha(structure)!='1797cba7a4230634f8f192d55e58d8e06f052e2b9568b5a0318b928c5576e730':raise ValueError('screen pin')
 selected=json.loads(c.read_pinned(c.SAMPLE,'11b3f7c9c28119b612f332af6b6ddfc6fabd02a4f7694912576e615871ed8039'))['selected'];reviews=read(structure)
 wanted={r['source_sha256']:r for r in reviews if any(b['break_lines'] for b in r['branches'])}
 found={}
 for filename,pin in c.PINS.items():
  rows=[r for r in selected if r['task'] in {v['task'] for v in wanted.values()} and r['file']==filename]
  if not rows:continue
  obj=json.loads(c.read_pinned(c.ROOT/filename,pin))
  for row in rows:
   for code in c.get_pair(obj,row):
    h=c.sha(code.encode())
    if h in wanted:found[h]=code
  del obj
 if set(found)!=set(wanted):raise ValueError('source missing')
 result=[]
 for h,code in sorted(found.items()):
  tree=ast.parse(code);parents={child:parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
  lines={b['line'] for b in wanted[h]['branches'] if b['break_lines']};branches=[]
  for node in ast.walk(tree):
   if getattr(node,'lineno',None) not in lines or not isinstance(node,(ast.If,ast.While)):continue
   scope=[];current=node
   while current in parents:
    current=parents[current]
    if isinstance(current,(ast.If,ast.While)):scope.append(dict(kind=type(current).__name__,condition=ast.unparse(current.test)))
    elif isinstance(current,(ast.FunctionDef,ast.AsyncFunctionDef)):scope.append(dict(kind='function',name=current.name,args=ast.unparse(current.args)))
   branches.append(dict(line=node.lineno,condition=ast.unparse(node.test),scope=scope,
                        branch_assignments=[ast.unparse(n) for n in node.body if isinstance(n,(ast.Assign,ast.AnnAssign))]))
  assignments=[]
  for n in ast.walk(tree):
   if isinstance(n,(ast.Assign,ast.AnnAssign)):
    text=ast.unparse(n)
    if any(v in text.lower() for v in ('time','budget','debug','epoch','wall','deadline','remaining','watchdog')):
     assignments.append(dict(line=n.lineno,source=text[:600]))
    if isinstance(n.value,ast.Dict):
     for key,value in zip(n.value.keys,n.value.values):
      if isinstance(key,ast.Constant) and isinstance(key.value,str) and any(s in key.value for s in ('budget','deadline','watchdog')):
       assignments.append(dict(line=n.lineno,source=ast.unparse(key)+': '+ast.unparse(value)))
  result.append(dict(task=wanted[h]['task'],source_sha256=h,branches=branches,relevant_assignments=assignments))
 report=dict(programs=result,source_only=True,no_reachability_or_quality_claim=True)
 out=c.BASE/'scheduling-branch-screen-20261008-v1/clock-contracts-v1'
 out.mkdir(mode=0o700,exist_ok=False);write(out/'summary.json',report)
 print(json.dumps(dict(programs=len(result),report_sha256=sha(out/'summary.json'),
  timers=[dict(task=r['task'],source_sha256=r['source_sha256'],settings=[a for a in r['relevant_assignments']
    if any(x in a['source'] for x in ('optional_time_budget_seconds', 'watchdog_limit_s =','TIME_BUDGET_SECONDS =','WALL_CLOCK_LIMIT_SEC =','MAX_WALLCLOCK_MINUTES =','MAX_RUNTIME_SECONDS ='))]) for r in result]),sort_keys=True))

if __name__=='__main__':main()
