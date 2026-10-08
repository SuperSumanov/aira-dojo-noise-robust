"""Fixed-public-sample syntax screen; not execution or resource-effect evidence.

Flow-insensitive, lexical-name propagation only. Aliasing/reassignment/closures,
reachability and arbitrary calls remain unresolved. Export hashes/line numbers,
never code, outcomes or prediction values. This extends the prior R14 census,
not a new mechanism or a claim that programs change under actual co-location.
"""
import ast
from collections import Counter
import json
from pathlib import Path
import signal
import sys
import time

import census as c

CLOCK={'time.time','time.monotonic','time.perf_counter','time.process_time'}
RESOURCE={'torch.cuda.mem_get_info','torch.cuda.get_device_properties',
          'torch.cuda.memory_allocated','torch.cuda.memory_reserved',
          'os.cpu_count','multiprocessing.cpu_count','psutil.cpu_count',
          'torch.cuda.is_available','torch.cuda.device_count'}
SCOPES=(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef,ast.Lambda)


def inspect(code):
    tree=ast.parse(code)
    aliases={}
    for n in ast.walk(tree):
        if isinstance(n,ast.Import):
            for x in n.names:aliases[x.asname or x.name.split('.')[0]]=x.name if x.asname else x.name.split('.')[0]
        elif isinstance(n,ast.ImportFrom):
            for x in n.names:aliases[x.asname or x.name]=(n.module or '')+'.'+x.name

    def source(n):
        if not isinstance(n,ast.Call):return set()
        name=c.dotted(n.func);head,sep,tail=name.partition('.')
        resolved=aliases.get(head,head)+(sep+tail if sep else '')
        if resolved in CLOCK:return {'clock'}
        if resolved in RESOURCE:return {resolved}
        return set()

    def scope_nodes(root):
        pending=list(ast.iter_child_nodes(root))
        while pending:
            n=pending.pop()
            if isinstance(n,SCOPES):continue
            yield n;pending.extend(ast.iter_child_nodes(n))

    rows=[]
    roots=[tree]+[n for n in ast.walk(tree) if isinstance(n,SCOPES)]
    for root in roots:
        nodes=list(scope_nodes(root));taints={}
        def tags(expr):
            found=set()
            for n in ast.walk(expr):
                found.update(source(n))
                if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load):found.update(taints.get(n.id,set()))
            return found
        changed=True
        while changed:
            changed=False
            for n in nodes:
                if not isinstance(n,(ast.Assign,ast.AnnAssign,ast.NamedExpr)) or n.value is None:continue
                targets=n.targets if isinstance(n,ast.Assign) else [n.target]
                values=tags(n.value)
                for target in targets:
                    for v in ast.walk(target):
                        if isinstance(v,ast.Name) and isinstance(v.ctx,ast.Store):
                            old=taints.setdefault(v.id,set());before=len(old);old.update(values)
                            changed|=len(old)!=before
        for n in nodes:
            if not isinstance(n,(ast.If,ast.While,ast.IfExp)):continue
            found=tags(n.test)
            if not found:continue
            body=n.body if isinstance(n.body,list) else [n.body]
            descendants=[v for b in body for v in ast.walk(b)]
            rows.append(dict(line=n.lineno,scope_line=getattr(root,'lineno',0),
                kind=type(n).__name__,sources=sorted(found),
                has_break=any(isinstance(v,ast.Break) for v in descendants),
                has_return=any(isinstance(v,ast.Return) for v in descendants),
                has_assignment=any(isinstance(v,(ast.Assign,ast.AnnAssign,ast.AugAssign)) for v in descendants)))
    return sorted(rows,key=lambda r:(r['line'],r['scope_line']))


def main(output):
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('120s screen cap')))
    signal.alarm(120);start=time.monotonic()
    structure=json.loads(c.read_pinned(c.STRUCTURE,c.STRUCTURE_SHA))
    sample=c.read_pinned(c.SAMPLE,structure['sample_sha256'])
    selected=json.loads(sample)['selected'];programs={}
    for filename,pin in c.PINS.items():
        receipt=json.loads(c.read_pinned(c.ROOT/(filename+'.download.json')))
        if receipt['sha256']!=pin or receipt['credential_categories']:raise ValueError('unclean source receipt')
        obj=json.loads(c.read_pinned(c.ROOT/filename,pin))
        for row in selected:
            if row['file']!=filename:continue
            for code in c.get_pair(obj,row):
                key=(row['task'],c.sha(code.encode()))
                if key not in programs:programs[key]=dict(task=key[0],source_sha256=key[1],branches=inspect(code))
        del obj
    counts=Counter();tasks={}
    for r in programs.values():
        kinds={s for b in r['branches'] for s in b['sources']}
        counts.update(kinds)
        for kind in kinds:tasks.setdefault(kind,set()).add(r['task'])
    summary=dict(status='syntax_screen_not_runtime_or_novelty',programs=len(programs),
        tasks=len({x['task'] for x in programs.values()}),pairs=len(selected),
        program_branch_counts=dict(counts),task_branch_counts={k:len(v) for k,v in tasks.items()},
        sample_sha256=c.sha(sample),analyzer_sha256=c.sha(Path(__file__).read_bytes()),
        source_pins=c.PINS,elapsed_seconds=time.monotonic()-start,
        candidate_executions=0,gpu_calls=0,outcome_fields_accessed=False,
        limits=['flow-insensitive lexical-name approximation; false positives and negatives possible',
                'functions not followed; outer-scope variable flows not resolved',
                'related public sample endpoints, not independent runs or representative production prevalence',
                'manual review needed before any resource-dependent behavior claim'])
    output.mkdir(mode=0o700,exist_ok=False)
    c.save(output/'summary.json',summary);c.save(output/'branches.json',list(programs.values()))
    print(json.dumps(summary,sort_keys=True))


if __name__=='__main__':main(Path(sys.argv[1]))
