"""No-execution inspection of two hash-fixed, from-scratch public neural sources."""
import ast
import argparse
import json
from pathlib import Path
import census as c

ap=argparse.ArgumentParser()
ap.add_argument('--task',choices=('aerial-cactus-identification','denoising-dirty-documents'))
ap.add_argument('--part',choices=('settings','main','helpers'),default='settings')
args=ap.parse_args()

WANTED={
 'aerial-cactus-identification':'c0888120b84c72f433712fb1c103f9e10e6ff18d84f5a15198d34b1159991369',
 'denoising-dirty-documents':'0d7b2d191f2dd2e4dd7b28a6c3d678eb321eb3f008abdefab538703a71bbc3f9',
}
selected=json.loads(c.read_pinned(c.SAMPLE,'11b3f7c9c28119b612f332af6b6ddfc6fabd02a4f7694912576e615871ed8039'))['selected']
found={}
for filename,pin in c.PINS.items():
 rows=[r for r in selected if r['task'] in WANTED and r['file']==filename]
 if not rows:continue
 obj=json.loads(c.read_pinned(c.ROOT/filename,pin))
 for row in rows:
  for code in c.get_pair(obj,row):
   if c.sha(code.encode())==WANTED[row['task']]:found[row['task']]=code
 del obj
if set(found)!=set(WANTED):raise ValueError('fixed source missing')
result=[]
for task,code in sorted(found.items()):
 if args.task and args.task!=task:continue
 tree=ast.parse(code);functions=[];literal_settings=[]
 for n in tree.body:
  if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and ((args.part=='main' and n.name=='main') or (args.part=='helpers' and n.name!='main')):
   functions.append(dict(name=n.name,line=n.lineno,source=ast.unparse(n)))
  if isinstance(n,ast.Assign) and args.part=='settings':
   for target in n.targets:
    if isinstance(target,ast.Name) and (target.id.isupper() or any(t in target.id.lower() for t in ('epoch','batch','patch','seed','budget','debug','train_dir','data_dir','test_dir'))):
     literal_settings.append(dict(line=n.lineno,name=target.id,value=ast.unparse(n.value)))
 public=c.BASE/'mle-bench-data'/task/'prepared/public'
 result.append(dict(task=task,source_sha256=WANTED[task],public_exists=public.is_dir(),
  public_top_level=[dict(name=p.name,is_dir=p.is_dir(),bytes=p.stat().st_size if p.is_file() else None) for p in sorted(public.iterdir())] if public.is_dir() else [],
  source_functions=functions,literal_settings=literal_settings))
print(json.dumps(result,sort_keys=True))
