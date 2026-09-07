"""Read fixed old-development structural metadata for cost planning only."""
import collections, hashlib, json, re
from pathlib import Path

P=Path('/research/d7/spc/yzyang4/historical-program-pack-f702ba2-r2-20260907/A-pack.private.json')
raw=P.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='0912a2e6cf8342fe6c209645d2d1b56c142f91a066197fcd5e37d07f8c0955e7'
S=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
assert not S.search(raw)
v=json.loads(raw); assert len(v)==84
rows=[]; costs=collections.Counter(); total=0; count=0
tasks=collections.defaultdict(lambda:{'runs':0,'nonempty_programs':0,'full_cap_gpu_seconds_at_one_gpu':0})
for run in v.values():
    cap=run['full_execution_timeout']; assert type(cap) is int and cap>0
    n=sum(x['nonempty_code'] for x in run['nodes'])
    assert run['source_admitted'] is False
    count+=n; total+=n*cap; costs[cap]+=n
    t=tasks[run['task']];t['runs']+=1;t['nonempty_programs']+=n;t['full_cap_gpu_seconds_at_one_gpu']+=n*cap
assert count==3447 and total==sum(cap*n for cap,n in costs.items())
assert total==sum(t['full_cap_gpu_seconds_at_one_gpu'] for t in tasks.values())
result={'classification':'CONDITIONAL_FULL_REEXECUTION_CAP_PLANNING_NOT_SELECTED_OR_ACTUAL_COST',
 'manifest_sha256':hashlib.sha256(raw).hexdigest(),'runs':len(v),'nonempty_programs':count,
 'gpu_per_program_assumption':1,'sum_full_caps_gpu_seconds':total,'sum_full_caps_gpu_hours':total/3600,
 'program_count_by_full_timeout_seconds':dict(sorted(costs.items())),
 'task_caps':[dict(task=k,**val) for k,val in sorted(tasks.items())],
 'includes_invalid_syntax_programs':True,'old_outcomes_read':False,'programs_selected':0,'programs_executed':0,
 'not_a_budget_approval':True,'excluded_overheads':['queue','environment_start','external_grading','IO','critic_training'],
 'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
assert P.read_bytes()==raw
print(json.dumps(result,sort_keys=True))
