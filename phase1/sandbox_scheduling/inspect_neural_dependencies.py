"""Fixed four-task source-only qualification; no execution, grades or selection by outcomes."""
import ast
import json
import signal
from pathlib import Path
import census as c

TASKS=('aerial-cactus-identification','denoising-dirty-documents','leaf-classification','seti-breakthrough-listen')

def main():
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('bounded source read')));signal.alarm(180)
 selected=json.loads(c.read_pinned(c.SAMPLE,'11b3f7c9c28119b612f332af6b6ddfc6fabd02a4f7694912576e615871ed8039'))['selected']
 records={}
 for filename,pin in c.PINS.items():
  rows=[r for r in selected if r['task'] in TASKS and r['file']==filename]
  if not rows:continue
  obj=json.loads(c.read_pinned(c.ROOT/filename,pin))
  for row in rows:
   for code in c.get_pair(obj,row):
    h=c.sha(code.encode());key=(row['task'],h)
    if key in records:continue
    tree=ast.parse(code);calls=[];constants=[];classes=[]
    for n in ast.walk(tree):
     if isinstance(n,ast.Call):
      name=c.dotted(n.func)
      if any(s in name.lower() for s in ('pretrained','create_model','resnet','efficientnet','mobilenet','load_state','torch.load','urlretrieve','download','conv2d','linear','fit','dataloader')):
       calls.append(dict(line=n.lineno,name=name,keywords=[dict(name=k.arg,literal=c.literal(k.value)) for k in n.keywords if k.arg in ('pretrained','weights','batch_size','num_workers','device','task_type')]))
     elif isinstance(n,ast.ClassDef):classes.append(dict(name=n.name,bases=[c.dotted(b) for b in n.bases]))
    records[key]=dict(task=row['task'],source_sha256=h,imports=sorted({(n.module or '').split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}|{a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}),classes=classes,calls=calls)
  del obj
 print(json.dumps(dict(tasks=list(TASKS),programs=sorted(records.values(),key=lambda r:(r['task'],r['source_sha256'])),
  gpu_executions=0,score_fields_read=False,dependency_occurrences_not_runtime_qualification=True),sort_keys=True))

if __name__=='__main__':main()
