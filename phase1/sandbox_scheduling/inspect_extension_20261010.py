"""Source-only candidate qualification, not executions or observed GPU demand."""
import ast
import json
import signal
import census as c

TASKS={'aerial-cactus-identification','denoising-dirty-documents','seti-breakthrough-listen'}


def main():
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('bounded read')));signal.alarm(180)
    rows=json.loads(c.read_pinned(c.SAMPLE,'11b3f7c9c28119b612f332af6b6ddfc6fabd02a4f7694912576e615871ed8039'))['selected']
    found={}
    for filename,pin in c.PINS.items():
        selected=[r for r in rows if r['file']==filename and r['task'] in TASKS]
        if not selected:continue
        obj=json.loads(c.read_pinned(c.ROOT/filename,pin))
        for row in selected:
            for code in c.get_pair(obj,row):found[(row['task'],c.sha(code.encode()))]=code
    result=[]
    for (task,pin),code in sorted(found.items()):
        tree=ast.parse(code);settings=[];calls=[];timers=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Assign):
                text=ast.unparse(n)
                if any(s in text.lower() for s in ('epoch','batch_size','pretrain','time_budget','runtime','wallclock','num_workers','patches_per','n_folds')):
                    settings.append(text[:240])
            if isinstance(n,ast.Call):
                name=c.dotted(n.func)
                if any(s in name for s in ('optim.','add_argument','read_csv','read_json','np.load')):calls.append(ast.unparse(n)[:360])
            if isinstance(n,(ast.If,ast.While)) and any(isinstance(x,ast.Break) for x in ast.walk(n)):
                test=ast.unparse(n.test)
                if any(s in test.lower() for s in ('time','budget','wall','deadline')):timers.append(test)
        public=c.BASE/'mle-bench-data'/task/'prepared/public'
        result.append(dict(task=task,source_sha256=pin,settings=settings,calls=calls,clock_breaks=timers,
            public_exists=public.is_dir(),public_names=sorted(p.name for p in public.iterdir()) if public.is_dir() else []))
    print(json.dumps(dict(programs=result,no_execution=True,no_score_fields=True)))


if __name__=='__main__':main()
