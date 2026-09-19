"""Fixed first two Pizza seeds: input readiness, not cached candidate outcomes."""
import hashlib,json,re,tarfile
from pathlib import Path,PurePosixPath
BASE=Path('/research/d7/spc/yzyang4');SOURCE=BASE/'comparison-quarantine-20260919-_tda9fh6'
RUNS={1:'5c3f818a9595bd79',2:'1eee3186d26dcbcd'}
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|Bearer\s+[a-z0-9_.-]{20,})')
def sha(raw):return hashlib.sha256(raw).hexdigest()
nodes_raw=(SOURCE/'qwen-readout-v1/nodes.json').read_bytes()
if sha(nodes_raw)!='370976e31c8a9f501bc75fb7826f529f85b0e34059146291f2e7bb3cab4062c9':raise ValueError('admitted nodes drift')
nodes=json.loads(nodes_raw);wanted={};output={}
for seed,run in RUNS.items():
    n,=[r for r in nodes if r['run']==run and r['group']=='executed' and r['step']==1]
    if n['parents']!=[0] or 'draft' not in n['operators_used']:raise ValueError('prefix structure')
    wanted[n['id']]=(seed,n)
with tarfile.open(SOURCE/'archives/random-acts-of-pizza.tar.gz','r|gz') as archive:
    for member in archive:
        path=PurePosixPath(member.name)
        if not member.isfile():continue
        if path.name=='dojo_config.json' and sha(str(path.parent).encode())[:16] in RUNS.values():
            raw=archive.extractfile(member).read()
            if SECRET.search(raw):raise ValueError('config credential-first')
            cfg=json.loads(raw)['solver'];run=sha(str(path.parent).encode())[:16]
            output.setdefault(run,{})['config']=dict(sha256=sha(raw),max_debug_depth=cfg['max_debug_depth'],use_test_score=cfg['use_test_score'],
                execution_timeout=cfg['execution_timeout'],time_limit_secs=cfg['time_limit_secs'],num_children=cfg['num_children'],critic_top_k=cfg['critic_top_k'])
        elif path.name=='journal.jsonl' and sha(str(path.parent.parent).encode())[:16] in RUNS.values():
            for raw in archive.extractfile(member):
                if SECRET.search(raw):raise ValueError('journal credential-first')
                n=json.loads(raw)
                if n.get('id') not in wanted:continue
                seed,known=wanted[n['id']];run=RUNS[seed]
                code=(n.get('code') or '').encode()
                if sha(code)!=known['code_sha256']:raise ValueError('code identity')
                terminal=n.get('_term_out') or n.get('term_out') or ''
                text=''.join(terminal) if isinstance(terminal,list) else terminal
                errors=re.findall(r'(?m)^\s*((?:\w+Error|Exception):[^\n]*)',text)
                output.setdefault(run,{})['prefix']=dict(seed=seed,node=n['id'],code_sha256=sha(code),log_sha256=sha(text.encode()),
                    exit_code=n.get('exit_code'),error_class=errors[-1].split(':')[0] if errors else None,
                    execution_seconds=n.get('exec_time'),kernel_readiness_failure='Kernel did not become ready' in text or 'Kernel readiness' in text,
                    raw_code_bytes=len(code),cached_alternatives=sum(r['run']==run and r['group']=='unselected' and r['parents']==[0] for r in nodes))
public=BASE/'mle-bench-data/random-acts-of-pizza/prepared/public'
print(json.dumps(dict(fixed_runs=RUNS,public_data_present=public.is_dir(),description_present=(public/'description.md').is_file(),cases=output,
    cached_outcomes_opened=False,new_model_calls=0),indent=2))
