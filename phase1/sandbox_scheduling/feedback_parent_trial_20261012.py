"""New independent feedback-reservation trial; old failed scheme remains closed."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys

DONOR = Path('/research/d7/spc/yzyang4/scheduling-generation-joint-20261012-v5')
sys.path.insert(1, str(DONOR))
import generation_joint_trial_20261012 as base
import joint_generation_policy_20261012 as old_policy
import feedback_parent_policy_20261012 as policy
from lifecycle_pilot import read, write, sha

R = DONOR.parent/'scheduling-feedback-parent-20261012-v1'
CAP = 7800
NAME = Path(__file__).name
ORDER = ('greedy', 'pending_ucb', 'feedback_gate', 'feedback_gate', 'pending_ucb', 'greedy')


def schedule():
    return [dict(index=8*b+2*lane+k, block=b, lane=lane, slot=2*lane+k, repeat=b//3,
                 arm=arm, task=task, seed=212701+100*(b//3)+2*lane+k)
            for b,arm in enumerate(ORDER) for lane in range(4) for k,task in enumerate(base.c.trial.TASKS)]


def install_hooks(row, ep, deadline):
    base.BASE_HOOK(row, ep, deadline)
    policy.install(row, ep, deadline, read(R/'warm.private.json')[row['task']])


def configure():
    base.R=R; base.CAP=CAP; base.NAME=NAME; base.schedule=schedule
    base.install_hooks=install_hooks
    base.configure()
    old_policy.initialize=policy.initialize
    old_policy.install=policy.install


host = base.host


def prepare(commit):
    assert re.fullmatch('[a-f0-9]{40}', commit)
    assert sha(DONOR/'plan.json')=='e923a7eefe6b69fdf9416bed58cab10218553760351022cc0b31920d039c32db'
    assert read(DONOR/'closed.json')['complete']==48
    p=read(DONOR/'plan.json')
    assert all(sha(DONOR/n)==h for n,h in p['files'].items())
    R.mkdir(mode=0o700)
    for n in p['files']:
        if n.startswith('configs/'):
            continue
        target=R/n; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(DONOR/n,target)
    (R/'dev-views').symlink_to((DONOR/'dev-views').resolve(),target_is_directory=True)
    (R/'configs').mkdir()
    for b in range(6): (R/f'block-{b}/service-cache/tmp').mkdir(parents=True)
    scorer=R/'image_scorer.py'
    scorer.write_text(scorer.read_text().replace(str(DONOR),str(R)))
    for row in schedule():
        i=row['index']; ep=R/f'episode-{i}'; (ep/'work/input_cache').mkdir(parents=True)
        cfg=json.loads(json.dumps(read(DONOR/f'configs/{i}.json')).replace(str(DONOR),str(R)))
        cfg['id']='feedback-parent-'+str(i)
        cfg['metadata'].update(seed=row['seed'],script_id='feedback-parent-20261012')
        cfg['interpreter']['env']['PYTHONHASHSEED']=str(row['seed'])
        cfg['task']['search_only_dev_scorer_sha256']=sha(scorer)
        # Imported evaluated parents count as journal records, not new budget.
        # Equal large cap makes wall-clock, not imported-node count, limiting.
        cfg['solver']['step_limit']=100000
        for op in cfg['solver']['operators'].values():
            op['llm']['generation_kwargs']['seed']=row['seed']
        write(R/f'configs/{i}.json',cfg)
    source=R/'source/src/dojo/solvers/mcts/mcts.py'
    source.write_text(base.c.trial.change(source.read_text(),
        '            # Evaluate the code\n',
        '            # Shared-parent selection happens immediately before generation.\n'
        '            path = [self.root_node, child_node.parents[0]]\n'
        '            # Evaluate the code\n'))
    names=(NAME,'feedback_parent_policy_20261012.py','test_feedback_parent_20261012.py','feedback_parent_readout_20261012.py')
    for n in names: shutil.copyfile(Path(__file__).with_name(n),R/n)
    shim=R/'bin/singularity'
    shim.write_text(f'#!{base.c.trial.PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(__file__).stem} import host\nhost().task_runtime()\n')
    shim.chmod(0o700)
    with (R/'.service.env').open('x') as f:
        f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    (R/'.service.env').chmod(0o600)
    sb=R/'run.sbatch'
    s=sb.read_text().replace(str(DONOR),str(R)).replace('r14-gen-joint','r14-feedback-parent')
    s=s.replace('02:06:00','02:10:00').replace('7500s','7740s')
    s=s.replace('generation_joint_trial_20261012.py controller',NAME+' controller')
    sb.write_text(s); subprocess.run(['bash','-n',str(sb)],check=True)
    for cache in ('vllm','triton'):
        src=DONOR/'block-0/service-cache'/cache
        if src.is_dir(): shutil.copytree(src,R/'block-0/service-cache'/cache,symlinks=True)
    p.update(source_commit=commit,source_parent_commit=p['source_commit'],source_donor_plan_sha256=sha(DONOR/'plan.json'),
        schedule=schedule(),allocation_seconds=CAP,gpu_hours_cap=13,combined_gpu_seconds_cap=CAP*6,
        prior_failures=[],new_window_gpu_seconds_cap=14*3600,
        primary='Best timely externally valid score per task/pool including supplied common start; shared-parent archive common to all arms.',
        single_change='Parent-selection/admission policy: greedy best parent; pending-count UCB; identical pending-UCB with at most one outstanding improvement per code. Analysis/debug completion priority common.',
        common_repairs='No further image/model/validity repair. All arms share scored archive and parent imports; no direct causal comparison against old independent-chain trial. Step cap100000 common, fixed wall clock1020/pool1180.',
        practical_margin={'denoising-dirty-documents':0.001,'aerial-cactus-identification':0.0},
        advance='All48 assigned normal, six equal pools, actual feedback withholding and reservation contract; denoising improves by >=.001 against both references in BOTH repeats; aerial must not lose. Otherwise no automatic expansion.',
        limitation='Two development tasks already inspected; aerial near ceiling is only a regression control. Two reversed-order pool repeats, not48 independent samples. Conditional shared-checkpoint search, not from scratch. Pending-UCB is an explicitly stated archive adaptation of WU-UCT Eq4, not complete paper reproduction; no novelty or SOTA claim.',
        stop='Fixed48; no intermediate score readout, no sample replacement, no retries to rescue outcomes; infrastructure failure stops subsequent pools and retains original denominator.',
        preflight_history='New independent mechanism, replacing request ordering with shared-parent selection and feedback reservation. Old17675 remains closed.')
    p['files']={n:sha(R/n) for n in p['files']}
    for n in names:p['files'][n]=sha(R/n)
    write(R/'plan.json',p)
    cp=subprocess.run([str(base.c.trial.PY),'-B',str(R/NAME),'preflight'],cwd=R,capture_output=True)
    (R/'preflight.private.log').write_bytes(cp.stdout+cp.stderr)
    if cp.returncode: raise RuntimeError('CPU preflight failed; no submission')
    print(json.dumps(read(R/'preflight.json')))


def preflight():
    p=base.c.trial.check(); base.c.trial.cpu()
    for row in schedule():
        ref=next(r for r in schedule() if r['seed']==row['seed'] and r['arm']=='greedy')
        a,b=(read(R/f"configs/{r['index']}.json") for r in (row,ref))
        assert base.c.trial.t.scientific(a)==base.c.trial.t.scientific(b)
        assert a['solver']['step_limit']==100000 and a['solver']['time_limit_secs']==1020
    subprocess.run([str(base.c.trial.PY),'-B','-m','unittest','test_feedback_parent_20261012','-v'],cwd=R,check=True)
    from feedback_parent_readout_20261012 import native_cpu_test
    native_cpu_test(R,host,install_hooks)
    write(R/'preflight.json',dict(source_commit=p['source_commit'],plan_sha256=sha(R/'plan.json'),
        configs=48,matched_comparisons=32,real_native_expand_parse_debug_import=True,no_gpu=True,no_model_calls=True,
        allocation_gpu_hours_cap=13,new_window_cap_gpu_hours=14))


def controller():
    base.controller()
    for b in range(6):
        s=read(R/f'generation-{b}/state.json')
        assert not s['pending'] and not s['active'] and not s['waiting']


configure()
if __name__=='__main__':
    os.umask(0o077); os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','preflight','submit','controller','service','lane','worker'])
    ap.add_argument('--commit');ap.add_argument('--block',type=int);ap.add_argument('--lane',type=int);ap.add_argument('--index',type=int)
    a=ap.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='preflight':preflight()
    elif a.mode=='submit':base.c.submit()
    elif a.mode=='controller':controller()
    elif a.mode=='service':base.c.trial.service(a.block)
    elif a.mode=='lane':base.lane(a.block,a.lane)
    else:base.c.worker(a.index)
