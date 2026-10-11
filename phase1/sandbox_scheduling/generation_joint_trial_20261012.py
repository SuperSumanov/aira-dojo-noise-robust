"""Bounded three-policy warm-start development experiment, 48 assigned runs.

Six reversed-order pools share one local service, 6 GPUs x 7920s maximum;
including failed17673's476s, below the original6x8400s total allocation cap.
This estimates conditional refinement from a supplied common checkpoint,
not from-scratch performance, and not a complete published-baseline replica.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import subprocess
import sys
import time
import traceback

# During preparation reuse the exact closed native harness, not a newer
# checkout's same-named source. The prepared directory takes precedence later.
_closed = Path('/research/d7/spc/yzyang4/scheduling-image-deadline-replication-20261012-v1')
if _closed.exists() and Path(__file__).parent != Path('/research/d7/spc/yzyang4/scheduling-generation-joint-20261012-v3'):
    sys.path.insert(1, str(_closed))
import image_live_cpu_repair_20261011 as c
from lifecycle_pilot import read, write, sha
from joint_generation_policy_20261012 import ARMS

OLD = c.trial.B/'scheduling-image-deadline-replication-20261012-v1'
OLD_PIN = '23f368399f6c735ef81142ec46831ae4e9f45d58d80edf5d2559b4cbb7a22ea6'
R = c.trial.B/'scheduling-generation-joint-20261012-v3'
NAME = Path(__file__).name
CAP = 7920
RUN = 1020
SLOT = 1180
ORDER = ('continuation', 'cost', 'joint', 'joint', 'cost', 'continuation')
BASE_HOOK = c.trial.install_hooks
BASE_HOST = c.trial.host


def schedule():
    return [dict(index=8*b+2*lane+k, block=b, lane=lane, slot=2*lane+k,
        repeat=b//3, arm=arm, task=task, seed=212401+100*(b//3)+2*lane+k)
        for b, arm in enumerate(ORDER) for lane in range(4) for k, task in enumerate(c.trial.TASKS)]


def install_hooks(row, ep, deadline):
    BASE_HOOK(row, ep, deadline)
    from joint_generation_policy_20261012 import install
    install(row, ep, deadline, read(R/'warm.private.json')[row['task']])


def host():
    return BASE_HOST()


def configure():
    c.R=R; c.CAP=CAP; c.host=host
    c.trial.R=R; c.trial.CAP=CAP; c.trial.RUN_SECONDS=RUN; c.trial.SLOT_SECONDS=SLOT
    c.trial.NAME=NAME; c.trial.schedule=schedule; c.trial.install_hooks=install_hooks


def warm_sources():
    """First accepted externally valid node in fixed batch/run/step order.

    No score-ranking or late outcome selection. Candidate code stays remote.
    Historical checkpoint construction is a shared sunk initialization input.
    """
    from image_dev_data_20261011 import score_at
    BATCHES=(('17592','scheduling-image-live-2plus4-20261011-v3',32,
        '95825b54b256eb69f7a2a372db66c4f63b4c0d9840d3253f5ade5685f448fe66',
        '7918c85f5257a82d66e28d52c9a557e7c924ed2e0dc5a5f4ef7b0131f6a84a9c'),)
    found={}; receipts={}
    for job, name, size, pp, sp in BATCHES:
        root=c.trial.B/name
        assert sha(root/'plan.json')==pp and sha(root/'readout-v1/summary.json')==sp
        plan=read(root/'plan.json'); spec=read(root/'dev-views/spec.json')
        for row in plan['schedule']:
            task=row['task']
            if task in found: continue
            ep=root/f"episode-{row['index']}"
            nodes=[read_json_line(x) for x in (ep/'checkpoint/journal.jsonl').read_text().splitlines() if x]
            for node in nodes:
                if node.get('is_buggy') is not False or not isinstance(node.get('metric'),(int,float)): continue
                code_hash=hashlib.sha256(node['code'].encode()).hexdigest()
                cs=[read(p) for p in sorted(ep.glob('candidate-*.json')) if '.private.' not in p.name]
                cs=[r for r in cs if r['code_sha256']==code_hash and r['valid'] and r['exit_code']==0 and not r['timed_out'] and r['elapsed_seconds']<=plan['run_seconds'] and abs(r['score']-node['metric'])<1e-12]
                if not cs: raise ValueError('accepted warm node lacks external candidate receipt')
                metric=spec[task]['metric_name']; matches=[]
                for p in sorted(ep.glob('scored-*.json')):
                    rec=read(p)['receipt']
                    if abs(rec[metric]-node['metric'])<1e-12:
                        got=score_at(root,spec,task,ep/(p.stem+'.private.csv'))
                        assert got['submission_sha256']==rec['submission_sha256'] and abs(got[metric]-rec[metric])<1e-12
                        matches.append(dict(receipt_sha256=sha(p),submission_sha256=rec['submission_sha256']))
                if not matches: raise ValueError('warm score not independently grounded')
                found[task]={k:node.get(k) for k in ('code','plan','analysis','_term_out','exec_time','metric','metric_maximize')}
                found[task]['code_sha256']=code_hash
                assert isinstance(found[task]['_term_out'],list) and node['exec_time']>0
                receipts[task]=dict(job=job,root=str(root),run=row['index'],step=node['step'],
                    journal_sha256=sha(ep/'checkpoint/journal.jsonl'),code_sha256=code_hash,
                    score=node['metric'],exec_time=node['exec_time'],grounded=matches,
                    rule='first accepted node in frozen batch/run/step order; no score ranking')
                break
    assert set(found)==set(c.trial.TASKS)
    return found,receipts


def read_json_line(line):
    from lifecycle_pilot import SECRET
    if SECRET.search(line.encode()): raise ValueError('credential shaped warm source refused')
    return json.loads(line)


def prepare(commit):
    assert re.fullmatch('[a-f0-9]{40}',commit) and sha(OLD/'plan.json')==OLD_PIN
    p=read(OLD/'plan.json'); assert read(OLD/'completion-closed.json')['summary_sha256']=='99ae98964305d29a444d7d5ba86c347395f70ef96280e2cf53b47491c5ae569c'
    assert all(sha(OLD/n)==h for n,h in p['files'].items())
    warm,receipts=warm_sources()
    R.mkdir(mode=0o700)
    for name in p['files']:
        if name.startswith('configs/'):continue
        dst=R/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(OLD/name,dst)
    (R/'dev-views').symlink_to((OLD/'dev-views').resolve(),target_is_directory=True)
    (R/'configs').mkdir()
    for b in range(6):(R/f'block-{b}/service-cache/tmp').mkdir(parents=True)
    write(R/'warm.private.json',warm);write(R/'warm-receipt.json',receipts)
    scorer=R/'image_scorer.py';scorer.write_text(scorer.read_text().replace(str(OLD),str(R)))
    for row in schedule():
        i=row['index'];ep=R/f'episode-{i}';(ep/'work/input_cache').mkdir(parents=True)
        cfg=read(OLD/f'configs/{i%8}.json');cfg=json.loads(json.dumps(cfg).replace(str(OLD),str(R)))
        cfg['id']='generation-joint-'+str(i);cfg['metadata'].update(seed=row['seed'],script_id='generation-joint-20261012')
        cfg['solver'].update(checkpoint_path=str(ep/'checkpoint'),time_limit_secs=RUN,stop_after_first_valid=False)
        cfg['logger']['output_dir']=str(ep/'native-log');cfg['task'].update(results_output_dir=str(ep/'native-task-results'),search_only_dev_scorer_sha256=sha(scorer))
        cfg['interpreter']['working_dir']=str(ep/'work');cfg['interpreter']['env']['PYTHONHASHSEED']=str(row['seed'])
        for op in cfg['solver']['operators'].values():op['llm']['generation_kwargs'].update(seed=row['seed'],bounded_request_timeout_seconds=600)
        write(R/f'configs/{i}.json',cfg)
    change=c.trial.change
    driver=R/'image_live_2plus4_20261011.py';s=driver.read_text()
    s=change(s,"TIME_LIMIT='15 minutes',TIME_LIMIT_SECS='900'","TIME_LIMIT='17 minutes',TIME_LIMIT_SECS='1020'")
    s=change(s,'timeout=990','timeout=1110')
    s=change(s,'episode-(?:[0-9]|[12][0-9]|3[01])','episode-(?:[0-9]|[123][0-9]|4[0-7])')
    s=change(s,"limit=1 if rows[0]['arm']=='fifo1' else 2","limit=1")
    s=change(s,'dict(configs=32,paired_equal=16,no_kernel=True','dict(configs=48,paired_equal=32,no_kernel=True')
    driver.write_text(s)
    hooks=R/'live_runtime_hooks.py';s=change(hooks.read_text(),'0 <= index <= 31','0 <= index <= 47')
    hooks.write_text(change(s,'(int(job) % 400) * 40 + index','(int(job) % 300) * 64 + index'))
    mcts=R/'source/src/dojo/solvers/mcts/mcts.py'
    mcts.write_text(change(mcts.read_text(),'response["is_bug"] or (not node.exit_code == 0)', '(not node.exit_code == 0)'))
    names=(NAME,'joint_generation_policy_20261012.py','test_joint_generation_20261012.py')
    for name in names:shutil.copyfile(Path(__file__).with_name(name),R/name)
    shim=R/'bin/singularity';shim.write_text(f'#!{c.trial.PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(__file__).stem} import host\nhost().task_runtime()\n');shim.chmod(0o700)
    with (R/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    (R/'.service.env').chmod(0o600)
    sb=f'''#!/bin/bash
#SBATCH --job-name=r14-gen-joint
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu3
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:6
#SBATCH --cpus-per-task=24
#SBATCH --hint=nomultithread
#SBATCH --time=02:12:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=30s 7860s {c.trial.PY} -B {R/NAME} controller
'''
    (R/'run.sbatch').write_text(sb);subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    p.update(source_commit=commit,source_parent_commit=p['source_commit'],source_donor_plan_sha256=OLD_PIN,
        schedule=schedule(),planned=48,allocation_seconds=CAP,gpu_hours_cap=CAP*6/3600,combined_gpu_seconds_cap=(CAP+476)*6,
        run_seconds=RUN,slot_seconds=SLOT,execution_permits=1,generation_permits_per_task=2,
        independent_pool_pairs=2,request_seconds=600,service_restart_between_blocks=False,
        primary='Best native accepted D_search endpoint per task/pool including the common supplied warm start; joint must beat BOTH matched references, per-task deltas and all assigned runs.',
        secondary='Per-seed endpoint improvement over common start; completed cycles, policy choice divergence, waits, cost, all failure denominators.',
        single_change='Pre-generation priority across same-task chains: continuation versus past improvement probability/cycle cost versus identical rule adding current lane residual wait after generation.',
        practical_margin={t:0.001 for t in c.trial.TASKS},
        advance='Exploratory signal only if all six equal pools and48 starts valid, real scarce admission/choice divergence, no task-repeat loss against either reference and same task gains >=.001 against both references in both repeats. Otherwise no automatic expansion.',
        limitation='Checkpoint-conditional refinement; shared sunk warm construction excluded from online budget, no from-scratch cost/quality claim. Two reused development tasks; two reversed-order pool repeats, not48 independent scheduling replicates. Small explicit cost/resource baseline adaptations, not full CostAda/MARS/SchedMate.',
        warm_start=receipts,stop='Stop remaining pools on infrastructure/identity/cleanup failure; retain48. No outcome-dependent replacement/seed rescue; no API or base training.')
    p['common_repairs']='Deterministic external validity replaces known unreliable LLM is_bug veto in all arms; not a treatment. Warm checkpoint/candidate queue1/request600/persistent service all common.'
    p['preflight_history']='v1 CPU-only path-list assertion failed. v2/17673 failed before generation: warm root incremented current_step before native log_journal indexed the node. Its preflight had stubbed log_journal and missed this path. v3 uses actual native logging+checkpoint serialization, same source/input/seed/arm rules; pool1180 and cap7920 contain the earlier476s allocation within original8400s total. All old files retained.'
    failed=c.trial.B/'scheduling-generation-joint-20261012-v2'
    assert read(failed/'launch.json')['job']=='17673' and read(failed/'closed.json')['complete']==0
    assert not any((failed/f'generation-{b}/events.jsonl').exists() for b in range(6))
    p['prior_failures']=[dict(job='17673',elapsed_seconds=476,gpu_seconds=2856,generated_candidates=0,
        plan_sha256=sha(failed/'plan.json'),closure_sha256=sha(failed/'closed.json'))]
    # Reuse only offline compilation products, copying rather than modifying
    # the closed failed batch. No generated prompt/response exists in it.
    shutil.copytree(failed/'block-0/service-cache',R/'block-0/service-cache',dirs_exist_ok=True)
    p['files']={n:sha(R/n) for n in p['files'] if not n.startswith('configs/')}
    p['files'].update({f'configs/{i}.json':sha(R/f'configs/{i}.json') for i in range(48)})
    for n in names+('warm.private.json','warm-receipt.json'):p['files'][n]=sha(R/n)
    write(R/'plan.json',p)
    checked=subprocess.run([str(c.trial.PY),'-B',str(R/NAME),'preflight'],cwd=R,capture_output=True)
    (R/'preflight.private.log').write_bytes(checked.stdout+checked.stderr)
    if checked.returncode:raise RuntimeError('CPU preflight failed; inspect whitelisted frames in remote private log')
    print(json.dumps(read(R/'preflight.json')))


def preflight():
    p=c.trial.check();c.trial.cpu()
    rows=schedule()
    for row in rows:
        ref=next(r for r in rows if r['seed']==row['seed'] and r['arm']=='continuation')
        a,b=(read(R/f"configs/{r['index']}.json") for r in (row,ref))
        assert c.trial.t.scientific(a)==c.trial.t.scientific(b)
        assert a['solver']['time_limit_secs']==RUN and not a['solver']['stop_after_first_valid']
        assert all(op['llm']['generation_kwargs']['bounded_request_timeout_seconds']==600 for op in a['solver']['operators'].values())
    subprocess.run([str(c.trial.PY),'-B','-m','unittest','test_joint_generation_20261012','-v'],cwd=R,check=True)
    # Real frozen MCTS constructor/root hook without GPU or a model call.
    m=host();m.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.solvers.mcts.mcts import MCTS
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.core.tasks.constants import TASK_DESCRIPTION
    from dojo.utils.experiment_deadline import ExperimentDeadline
    from omegaconf import OmegaConf
    from joint_generation_policy_20261012 import initialize,install
    row=rows[0];cfg=RunConfig.load_from_json(R/'configs/0.json');task=MLEBenchTask(cfg.task)
    # Use an isolated CPU-only hook directory, not the future live queue.
    fixture=R/'cpu-hook-fixture';fixture.mkdir();ep=fixture/'episode-0';ep.mkdir()
    warm=read(R/'warm.private.json');initialize(fixture/'generation-0',rows[:8],warm)
    install(row,ep,ExperimentDeadline(10),warm[row['task']])
    cfg.solver.checkpoint_path=str(fixture/'checkpoint');cfg.logger.output_dir=str(fixture/'native-log')
    from dojo.utils.logger import config_logger
    config_logger(cfg)
    solver=MCTS(OmegaConf.structured(cfg.solver),{TASK_DESCRIPTION:task.task_description,'lower_is_better':task._search_only_lower_is_better})
    native_log=solver.log_journal
    def real_log_and_save():native_log();solver.save_checkpoint()
    solver.log_journal=real_log_and_save;solver.create_root_node()
    assert len(solver.journal.nodes)==2 and solver.journal.get_best_node().metric.value==warm[row['task']]['metric']
    saved=[json.loads(s) for s in (fixture/'checkpoint/journal.jsonl').read_text().splitlines()]
    assert len(saved)==solver.state.current_step==2 and saved[1]['metric']==warm[row['task']]['metric']
    path=solver.search_policy(solver.root_node);assert path[-1].code==warm[row['task']]['code']
    # Run the real permit wrapper, with only its operator stubbed (no LLM).
    import dojo.solvers.mcts.mcts as mm
    original_op=mm.execute_op_plan_code
    mm.execute_op_plan_code=lambda *args,**kwargs:('fixture plan','print(1)',[])
    try:
        child=solver._improve(path[-1]);assert child.code=='print(1)'
    finally:mm.execute_op_plan_code=original_op
    gs=read(fixture/'generation-0/state.json');assert not gs['active'] and not gs['waiting']
    write(R/'preflight.json',dict(source_commit=p['source_commit'],plan_sha256=sha(R/'plan.json'),
        configs=48,matched_comparisons=32,real_frozen_warm_root=True,no_gpu=True,no_model_calls=True))
    print(json.dumps(read(R/'preflight.json')))


def lane(block, requested):
    from resource_gpu_identity import gpu_uuids
    logical=requested
    if block:
        devices=[read(R/f'block-0/lane-{i}-native.json')['gpu_uuid'] for i in range(4)]
        assert len(set(devices))==4;logical=devices.index(gpu_uuids(1)[0])
    c.trial.lane(block,logical)
    for row in schedule():
        if (row['block'],row['lane'])!=(block,logical):continue
        ep=R/f"episode-{row['index']}";cl=read(ep/'closed.json')
        events=[json.loads(x) for x in (ep/'events.jsonl').read_text().splitlines()] if (ep/'events.jsonl').exists() else []
        if cl['returncode']!=0 and not any(e['event']=='generation_started' for e in events):raise RuntimeError('pre-generation infrastructure failure')


def controller():
    from joint_generation_policy_20261012 import initialize
    c.trial.check();c.trial.activate_helpers();m=host();m.setup();job=os.environ['SLURM_JOB_ID']
    begin=time.monotonic();attempted=[];error=None;server=None;workers=[];logs=[]
    for _ in range(40):
        if (R/'launch.json').exists():break
        time.sleep(.25)
    assert read(R/'launch.json')['job']==job
    env=m.infra().clean_env();base=['srun','--exclusive','--nodes=1','--ntasks=1','--hint=nomultithread']
    try:
        slog=(R/'block-0/service.private.log').open('xb');logs.append(slog)
        server=subprocess.Popen(base+['--cpus-per-task=8','--gres=gpu:2','--time=02:19:00',str(c.trial.PY),'-B',str(R/NAME),'service','--block','0'],env=env,stdout=slog,stderr=slog,start_new_session=True)
        while time.monotonic()-begin<600:
            if server.poll() is not None:raise RuntimeError('service died')
            try:
                if {r['id'] for r in m.api('/v1/models')['data']}=={'qwen3.8-27b'}:break
            except Exception:pass
            time.sleep(2)
        else:raise TimeoutError('service startup')
        write(R/'service-ready.json',dict(startup_seconds=time.monotonic()-begin))
        for block in range(6):
            if CAP-(time.monotonic()-begin)<SLOT+90:raise TimeoutError('full pool budget')
            bd=R/f'block-{block}';start=time.monotonic();wall=time.time();workers=[]
            if block:write(bd/'service-native.json',read(R/'block-0/service-native.json'))
            initialize(R/f'generation-{block}',[r for r in schedule() if r['block']==block],read(R/'warm.private.json'))
            attempted.append(block)
            for i in range(4):
                log=(bd/f'lane-{i}.private.log').open('xb');logs.append(log)
                workers.append(subprocess.Popen(base+['--cpus-per-task=4','--gres=gpu:1','--time=00:20:00',str(c.trial.PY),'-B',str(R/NAME),'lane','--block',str(block),'--lane',str(i)],env=env,stdout=log,stderr=log,start_new_session=True))
            while any(w.poll() is None for w in workers):
                if server.poll() is not None:raise RuntimeError('service died')
                if time.monotonic()-start>SLOT-40:raise TimeoutError('pool cleanup budget')
                time.sleep(2)
            codes=[w.returncode for w in workers];write(bd/'steps.json',dict(returncodes=codes))
            assert codes==[0]*4,'lane infrastructure failure'
            from live_identity import cores
            ids=[read(bd/f'lane-{i}-native.json') for i in range(4)]
            assert len({r['gpu_uuid'] for r in ids})==4
            sets=[cores(r['cpu_topology']) for r in ids]+[cores(read(bd/'service-native.json')['cpu_topology'])]
            assert all(not sets[i]&sets[j] for i in range(5) for j in range(i))
            gs=read(R/f'generation-{block}/state.json');assert not gs['active'] and not gs['waiting']
            # No result values are used to choose whether to run the next pool.
            active=time.monotonic()-start
            while time.monotonic()-start<SLOT:time.sleep(min(1.,SLOT-(time.monotonic()-start)))
            write(bd/'budget-slot.json',dict(reserved_seconds=SLOT,actual_seconds=time.monotonic()-start,active_seconds=active,start=wall,gpus=6))
    except BaseException as exc:
        error=dict(type=type(exc).__name__,frames=[dict(file=Path(f.filename).name,line=f.lineno,function=f.name) for f in traceback.extract_tb(exc.__traceback__)])
        raise
    finally:
        for worker in workers:
            if worker.poll() is None:
                worker.send_signal(signal.SIGTERM)
                try:worker.wait(timeout=15)
                except subprocess.TimeoutExpired:os.killpg(worker.pid,signal.SIGKILL);worker.wait(timeout=10)
        if server is not None:c.trial.t.stop_service(server,0,job)
        for log in logs:log.close()
        rows=[]
        for row in schedule():
            ep=R/f"episode-{row['index']}";out=dict(row,source_commit=read(R/'plan.json')['source_commit'],status='not_started')
            if (ep/'closed.json').exists():out.update(read(ep/'closed.json'));out['status']='incomplete'
            if (ep/'finished.json').exists():
                f=read(ep/'finished.json');out.update(f)
                out['status']='complete' if out.get('returncode')==0 and out.get('cleanup_verified') and f['status'] in ('completed','budget_exhausted') else 'incomplete'
            rows.append(out)
        write(R/'runs.json',rows)
        with (R/'runs.csv').open('x',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=sorted({k for r in rows for k in r}));writer.writeheader();writer.writerows(rows)
        write(R/'closed.json',dict(planned=48,attempted_blocks=attempted,complete=sum(r['status']=='complete' for r in rows),error=error,elapsed_seconds=time.monotonic()-begin))


configure()
if __name__=='__main__':
    os.umask(0o077);os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','preflight','submit','controller','service','lane','worker']);p.add_argument('--commit');p.add_argument('--block',type=int);p.add_argument('--lane',type=int);p.add_argument('--index',type=int);a=p.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='preflight':preflight()
    elif a.mode=='submit':c.submit()
    elif a.mode=='service':c.trial.service(a.block)
    elif a.mode=='lane':lane(a.block,a.lane)
    elif a.mode=='worker':c.worker(a.index)
    else:controller()
