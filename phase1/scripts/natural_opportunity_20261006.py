"""Fresh-code opportunity screen, not a selector or independent-run confirmation.

Choose by code/dependency/visible-lineage only. Original programs and source seeds
are unchanged. Two cold executions test reproducibility, not training-seed variance.
No launch is authorized by preparing this file or its immutable plan.
"""
import argparse
import ast
import collections
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import external_pair_replay_20261006 as E
import collateral_sample_20261006 as S

B, D, PY = E.B, E.D, E.PY
R = B/'natural-opportunity-20261006-v1'
NAME = Path(__file__).name
TASKS = E.TASKS
SALT = 'independent-opportunity-20261006-v1'
ALLOWED = frozenset(('argparse ast collections copy csv difflib gc hashlib io itertools joblib json math '
    'multiprocessing numpy os pandas pathlib pickle random re scipy shutil sklearn string sys time '
    'traceback typing unicodedata warnings xgboost lightgbm catboost').split())
HELPERS = {'external_pair_replay_20261006.py':'7d81689449a1f0cd37773e66e1bdf8579117485daea82ff50f8ddcdcbb36c0f8',
           'collateral_sample_20261006.py':'e5a63aafd1940b4c8e0119237a07abda7f1c3ba3bdf5f1eb3662f8ea5b272db5'}
sha, read, write, load = E.sha, E.read, E.write, E.load


def components(edges):
    adj = collections.defaultdict(set)
    for a, b in edges:
        adj[a].add(b); adj[b].add(a)
    comp = {}
    for n in sorted(adj):
        if n in comp: continue
        todo, seen = [n], set()
        while todo:
            x = todo.pop()
            if x in seen: continue
            seen.add(x); todo.extend(adj[x]-seen)
        h = S.digest('|'.join(sorted(seen)))
        comp.update({x:h for x in seen})
    return comp


def permitted(obj, filename):
    # Deliberately do not touch feedback, score, runtime or hypothesis fields.
    for row, a, b in S.permitted_pairs(obj, filename):
        if row['task'] not in TASKS: continue
        trees = [ast.parse(c) for c in (a,b)]
        hs = [S.digest(ast.dump(t, include_attributes=False)) for t in trees]
        modules = {(n.module or '').split('.')[0] for t in trees for n in ast.walk(t) if isinstance(n,ast.ImportFrom)}
        modules |= {v.name.split('.')[0] for t in trees for n in ast.walk(t) if isinstance(n,ast.Import) for v in n.names}
        obsolete = any(k.arg=='multi_class' for t in trees for n in ast.walk(t) if isinstance(n,ast.Call) for k in n.keywords)
        reason = 'dependency' if modules-ALLOWED else 'obsolete_api' if obsolete else None
        yield dict(**row, parent_ast=hs[0], child_ast=hs[1], exclusion=reason)


def choose(rows, old):
    selected, coverage = [], []
    for task in TASKS:
        rs = [r for r in rows if r['task']==task]
        comp = components((r['parent_ast'],r['child_ast']) for r in rs)
        old_keys = {(x['file'],x['loop']) for x in old if x['task']==task}
        blocked = {comp[r['parent_ast']] for r in rs if (r['file'],r['loop']) in old_keys}
        eligible = [r for r in rs if r['exclusion'] is None and comp[r['parent_ast']] not in blocked and r['parent_ast']!=r['child_ast']]
        rank = lambda r:S.digest('|'.join([SALT,task,r['base_sha256'],r['code_sha256']]))
        used, files, picks = set(), set(), []
        for r in sorted(eligible,key=rank):
            c = comp[r['parent_ast']]
            if c in used or r['file'] in files: continue
            used.add(c); files.add(r['file'])
            picks.append(dict(**r, visible_component=c, selection_rank=rank(r)))
            if len(picks)==2: break
        assert len(picks)==2, 'Insufficient pre-outcome source coverage; do not replace task'
        selected.extend(picks)
        coverage.append(dict(task=task, all_edges=len(rs), parent_asts=len({r['parent_ast'] for r in rs}),
            visible_components=len(set(comp.values())), blocked_components=len(blocked),
            eligible_edges=len(eligible), exclusion_counts=dict(collections.Counter(r['exclusion'] or 'supported_imports' for r in rs))))
    return selected, coverage


def source_population():
    assert sha(S.OUT/'structure.json')==E.PIN
    assert sha(S.OUT/'sample.json')==read(S.OUT/'structure.json')['sample_sha256']
    rows=[]
    for fn,h in S.PINS.items():
        assert sha(S.ROOT/fn)==h
        raw=(S.ROOT/fn).read_bytes(); assert not E.SECRET.search(raw)
        rows.extend(permitted(json.loads(raw),fn))
    return choose(rows,read(S.OUT/'sample.json')['selected'])


def schedule(): return read(R/'plan.json')['schedule']


def check():
    p=read(R/'plan.json')
    assert len(p['schedule'])==16 and p['gpu_hours_cap']==3
    for rel,h in p['files'].items(): assert sha(R/rel)==h,rel
    return p


def runtime():
    m=load('natural_opportunity_runtime',R/'runtime.py'); m.R=R; m.setup(); return m


def tests():
    c=components([('a','b'),('b','c'),('x','y')])
    assert c['a']==c['c'] and c['a']!=c['x']
    class Forbidden:
        def __str__(self): raise AssertionError('outcome touched')
        def __bool__(self): raise AssertionError('outcome touched')
    obj={TASKS[0]:{'loop_1':dict(base_code='x=1',code='x=2',feedback=Forbidden(),valid_score=Forbidden())}}
    assert len(list(permitted(obj,'Trace_1.json')))==1
    fixture=[]; old=[]
    for task in TASKS:
        for k in range(3):
            fixture.append(dict(task=task,file=f'Trace_{k+1}.json',loop='loop_1',
                parent_ast=f'{task}-{k}a',child_ast=f'{task}-{k}b',
                base_sha256=f'{task}-{k}a',code_sha256=f'{task}-{k}b',exclusion=None))
        old.append(dict(task=task,file='Trace_3.json',loop='loop_1'))
    x,coverage=choose(fixture,old)
    y,_=choose(list(reversed(fixture)),old)
    assert x==y and len(x)==4 and all(r['file']!='Trace_3.json' for r in x)
    assert all(r['blocked_components']==1 and r['eligible_edges']==2 for r in coverage)
    assert E.tests()['exact_source_payload']
    return dict(status='PASS', component_fixture=True, forbidden_field_sentinel=True,
                frozen_rank_order=True,old_component_exclusion=True,exact_wrapper=True,
                interpretation='Fixed-source-seed restarts, not independent training seeds')


def prepare(commit):
    assert re.fullmatch('[a-f0-9]{40}',commit) and not R.exists()
    for name,h in HELPERS.items(): assert sha(Path(__file__).with_name(name))==h
    tests()
    selected,coverage=source_population()
    assert sha(D/'plan.json')=='fed6f8c812fc49db8acc459b460a10bbe962cbe10b8a2172f5dff06c7686a624'
    R.mkdir(mode=0o700)
    for rel,h in read(D/'plan.json')['files'].items():
        if not rel.startswith(('source/','forets_','opencl-vendors/')): continue
        assert sha(D/rel)==h
        dest=R/rel; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(D/rel,dest)
    original=(D/'runtime.py').read_bytes(); assert S.digest(original)==E.RUNTIME_SHA
    pattern=b"re.fullmatch('episode-[0-7]',ep.name)"
    assert original.count(pattern)==1
    with (R/'runtime.py').open('xb') as f:
        f.write(original.replace(pattern,b"re.fullmatch('episode-(?:[0-9]|1[0-5])',ep.name)"))
    helper=E.F/'run_collateral_factorial_20261006.py'
    assert sha(helper)==read(E.F/'plan.json')['files'][helper.name]
    body=helper.read_text(); assert body.count('with ExperimentDeadline(390).activate():')==1
    with (R/'worker_helper.py').open('x') as f:
        f.write(body.replace('with ExperimentDeadline(390).activate():','with ExperimentDeadline(450).activate():'))
    for name in [NAME,'analyze_natural_opportunity_20261006.py',*HELPERS]: shutil.copyfile(Path(__file__).with_name(name),R/name)
    for name in ('configs','bin'): (R/name).mkdir()
    with (R/'bin/singularity').open('x') as f:
        f.write(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom natural_opportunity_20261006 import runtime\nruntime().task_runtime()\n')
    os.chmod(R/'bin/singularity',0o700)
    for case,row in enumerate(selected):
        data=read(S.ROOT/row['file'])[row['task']][row['loop']]
        folder=R/f'case-{case}.private'; folder.mkdir()
        for arm,key in [('P','base_code'),('C','code')]:
            code=data[key]; assert S.digest(code)==row['base_sha256' if arm=='P' else 'code_sha256']
            wrapped=E.wrap(code); compile(wrapped,'original-wrapped-source','exec')
            with (folder/f'{arm}.py').open('x') as f: f.write(wrapped)
    rows=[]
    for repeat in range(2):
        for case,row in enumerate(selected):
            for arm in (('P','C') if (repeat+case)%2==0 else ('C','P')):
                i=len(rows); ep=R/f'episode-{i}'; ep.mkdir()
                s=dict(index=i,case=case,repeat=repeat,arm=arm,task=row['task'],seed=117601+case,
                    code_sha256=sha(R/f'case-{case}.private/{arm}.py'),
                    original_sha256=row['base_sha256' if arm=='P' else 'code_sha256'])
                rows.append(s)
                cfg=read(D/'configs'/('0.json' if row['task']==TASKS[0] else '2.json'))
                cfg['id']=f'natural-opportunity-{i}'
                cfg['logger'].update(output_dir=str(ep/'native-log'),write_env_vars=False,use_wandb=False,print_config=False,use_console=False)
                cfg['metadata'].update(seed=s['seed'],base_path=str(R/'source'),git_commit_id=commit,script_id='natural-opportunity-20261006')
                cfg['task'].update(cache_dir=str(R/'no-official-data'),results_output_dir=str(ep/'native-log/results'))
                cfg['interpreter'].update(timeout=300,working_dir=str(ep/'action-0/work'))
                cfg['interpreter']['env'].update(PYTHONHASHSEED=str(s['seed']),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
                write(R/'configs'/f'{i}.json',cfg)
    batch=f'''#!/bin/bash
#SBATCH --job-name=natural-opportunity
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=12
#SBATCH --time=01:30:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 5320s {PY} -B {R}/{NAME} controller
'''
    with (R/'run.sbatch').open('x') as f: f.write(batch)
    write(R/'plan.json',dict(protocol='fresh-parent-opportunity-screen-v1',source_commit=commit,
        files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file()},
        schedule=rows,selected=selected,coverage=coverage,source_pins=S.PINS,selection_salt=SALT,
        old_sample_sha256=sha(S.OUT/'sample.json'),task_image_sha256=read(D/'preflight.json')['task_image_sha256'],
        assigned=16,parents=4,tasks=2,restarts=2,program_seconds=300,worker_seconds=450,step_seconds=480,
        allocation_seconds=5400,gpus=2,gpu_hours_cap=3,paid_api_calls=0,generator_calls=0,base_training=False,
        primary='For every assigned parent, both original-code restart pairs: oriented child-parent gain, execution validity, prediction repeatability and full worker time. All failures retained.',
        meaningful_gain={TASKS[0]:.005,TASKS[1]:.01},time_ratio_ceiling=1.5,
        screening_gate='Both restarts exceed the task-specific gain threshold; conditional paired 98.75% interval lower bound >0; median child/parent worker-time ratio <=1.5. This is an engineering screening criterion, not universal utility.',
        uncertainty='Paired development-example bootstrap, 4000 replicates, seed 117699, stratified AUC; median gain across restart pairs. Bonferroni four-parent intervals. Conditional on selected programs and reused view; not correction for historical task adaptation, training uncertainty or shared search memory.',
        investment_gate='No selector is trained. At least one qualifying parent in each task would justify proposing a separately budgeted genuinely fresh-source/seed and equal-cost HPO comparison. No automatic expansion.',
        cost='Report every assigned run, failure, cold startup, elapsed program/worker/allocation time. Original program creation costs unknown; no same-budget search-method victory claimed.',
        independence='Different visible AST components and source trace files within each task, excluding components touching the old 80-pair sample. GOME shares success memory and source graph may omit edges: NOT proof of independent physical runs or fresh test tasks.',
        seed_boundary='Source-coded RNG seeds preserved exactly. Wrapper seed is identical across repeats. Cold reruns do NOT establish robustness across training seeds.',
        fairness='Only the entire natural parent/child program changes. Identical task view/scorer/image/hardware class/caps; reversed P/C order in second repeat. This does not isolate any constituent edit.',
        protected_opened=False,outcome_timing='After all workers close and predictions freeze; external scorer only. Never read public-source outcome fields.',
        stopping='No replacement, compatibility repair, added seed, changed cap, or automatic retries. Prepared is not permission to launch.'))
    runtime()
    from dojo.config_dataclasses.run import RunConfig
    signatures={}
    for s in rows:
        cfg=RunConfig.load_from_json(R/'configs'/f"{s['index']}.json");cfg.validate()
        assert cfg.task.data_dir==cfg.task.public_dir and '/search-only-dev-' in cfg.task.data_dir
        assert not Path(cfg.task.private_dir).exists() and not cfg.interpreter.read_only_binds
        assert sha(cfg.task.search_only_dev_scorer_path)==cfg.task.search_only_dev_scorer_sha256
        raw=read(R/'configs'/f"{s['index']}.json")
        t=copy.deepcopy(raw['task']); t.pop('results_output_dir')
        it=copy.deepcopy(raw['interpreter']); it.pop('working_dir')
        sig=json.dumps([t,it],sort_keys=True)
        assert s['case'] not in signatures or signatures[s['case']]==sig
        signatures[s['case']]=sig
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    write(R/'preflight.json',dict(status='PASS',typed_configs=16,matched_parent_groups=4,
        plan_sha256=sha(R/'plan.json'),tests=tests(),all_sources_unchanged=True,
        task_image_sha256=read(D/'preflight.json')['task_image_sha256'],
        checklist='Artifact-bound knob; AST/wrapper tests; old component exclusion; per-task denominators; matched image/views/caps; no learned checkpoint; fixed selection before outcomes; original RNG preserved; credential scan; 8*480<5400; source/missingness limits explicit; no shell rc interpolation; immutable plan/selection.'))
    print(json.dumps(dict(status='PREPARED_NOT_LAUNCHED',plan_sha256=sha(R/'plan.json'),assigned=16,gpu_hours_cap=3,coverage=coverage)))


def worker(i):
    x=load('natural_opportunity_worker',R/'worker_helper.py')
    x.R=R;x.check=check;x.schedule=schedule;x.runtime=runtime;x.worker(i)


def controller():
    check();m=runtime();assert read(R/'launch.json')['job']==os.environ['SLURM_JOB_ID']
    def one(i):
        ep=R/f'episode-{i}'
        if (ep/'closed.json').exists(): return read(ep/'closed.json')['returncode']
        assert not (ep/'native.json').exists(),'Started without closure; no retry'
        cmd=['srun','--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=6','--gres=gpu:1',
             '--time=00:08:00',str(PY),'-B',str(R/NAME),'worker','--index',str(i)]
        with (ep/'worker.private.log').open('xb') as f:
            q=subprocess.run(cmd,env=m.infra().clean_env(),stdout=f,stderr=f)
        write(ep/'closed.json',dict(returncode=q.returncode));return q.returncode
    with ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(one,range(16)))
    write(R/'closed.json',dict(returncodes=codes,assigned=16))


def submit():
    # The only launch path additionally requires a separately recorded approval.
    assert read(R/'approval.json')['approved_gpu_hours_cap']==3
    p=check();m=runtime();assert sha(m.TASK_IMAGE)==p['task_image_sha256']
    assert read(R/'preflight.json')['plan_sha256']==sha(R/'plan.json')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=25).split()
    assert not set(jobs)-{'12535'}
    with (R/'capacity.tmp').open('xb') as f:os.posix_fallocate(f.fileno(),0,64*1024**2)
    (R/'capacity.tmp').unlink()
    write(R/'submit-intent.json',dict(plan_sha256=sha(R/'plan.json')))
    q=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),
        '--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=q.stdout.strip().split(';')[0];assert q.returncode==0 and job.isdigit(),'Ambiguous submission; no retry'
    write(R/'launch.json',dict(job=job,plan_sha256=sha(R/'plan.json')))
    print(json.dumps(dict(job=job,status='SUBMITTED',gpu_hours_cap=3)))


def status():
    check(); print(json.dumps(dict(assigned=16,
        launch=read(R/'launch.json') if (R/'launch.json').exists() else None,
        started=sum((R/f'episode-{i}/native.json').exists() for i in range(16)),
        completed=sum((R/f'episode-{i}/completed.json').exists() for i in range(16)),
        workers_closed=sum((R/f'episode-{i}/closed.json').exists() for i in range(16)),
        batch_closed=(R/'closed.json').exists())))


if __name__=='__main__':
    os.umask(0o077)
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['tests','prepare','check','submit','worker','controller','status'])
    p.add_argument('--commit');p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='worker':worker(a.index)
    elif a.mode=='tests':print(json.dumps(tests()))
    else:globals()[a.mode]()
