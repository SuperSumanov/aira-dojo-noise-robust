"""Approved independent24-run long-effort screen, <=12.5 full-pool GPU hours.

No automatic retries/expansion. Closed17740 is an immutable infrastructure donor,
not an old result to be rescued. Analyze is medium in every condition.
"""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys

DONOR = Path('/research/d7/spc/yzyang4/scheduling-feedback-effort-20261012-v2')
sys.path.insert(1, str(DONOR))
import generation_joint_trial_20261012 as base
import joint_generation_policy_20261012 as old_policy
import feedback_parent_policy_20261012 as parent
import long_effort_policy_20261013 as policy
from lifecycle_pilot import read, write, sha

R = DONOR.parent/'scheduling-long-effort-20261013-v1'
NAME = Path(__file__).name
NAMES = (NAME, 'long_effort_policy_20261013.py', 'long_effort_readout_20261013.py',
         'test_long_effort_20261013.py', 'long_effort_native_cpu_20261013.py')


def schedule():
    return [dict(index=8*b+2*lane+k, block=b, lane=lane, slot=2*lane+k,
                 repeat=0, arm=arm, task=task, seed=213301+2*lane+k)
            for b, arm in enumerate(policy.ORDER) for lane in range(4)
            for k, task in enumerate(base.c.trial.TASKS)]


def install_hooks(row, ep, deadline):
    base.BASE_HOOK(row, ep, deadline)
    policy.install(row, ep, deadline, read(R/'warm.private.json')[row['task']])


def configure():
    base.R = R
    base.CAP = policy.CAP
    base.RUN = policy.RUN
    base.SLOT = policy.SLOT
    base.NAME = NAME
    base.schedule = schedule
    base.install_hooks = install_hooks
    base.configure()
    old_policy.initialize = parent.initialize


host = base.host


def prepare(commit):
    assert re.fullmatch('[a-f0-9]{40}', commit)
    assert sha(DONOR/'plan.json') == '4b33b157e65ba4b14668dfb9e3309ba2e9173ba62c0d542614ef9bad7befd0fc'
    assert read(DONOR/'closed.json')['complete'] == 48
    p = read(DONOR/'plan.json')
    assert all(sha(DONOR/n) == h for n, h in p['files'].items())
    R.mkdir(mode=0o700)
    for n in p['files']:
        if n.startswith('configs/'):
            continue
        dst = R/n
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DONOR/n, dst)
    (R/'dev-views').symlink_to((DONOR/'dev-views').resolve(), target_is_directory=True)
    (R/'configs').mkdir()
    for b in range(3):
        (R/f'block-{b}/service-cache/tmp').mkdir(parents=True)
    scorer = R/'image_scorer.py'
    scorer.write_text(scorer.read_text().replace(str(DONOR), str(R)))
    change = base.c.trial.change
    for row in schedule():
        i = row['index']
        ep = R/f'episode-{i}'
        (ep/'work/input_cache').mkdir(parents=True)
        cfg = json.loads(json.dumps(read(DONOR/f'configs/{i}.json')).replace(str(DONOR), str(R)))
        cfg['id'] = 'long-effort-'+str(i)
        cfg['metadata'].update(seed=row['seed'], script_id='long-effort-20261013')
        cfg['interpreter']['env']['PYTHONHASHSEED'] = str(row['seed'])
        cfg['solver']['time_limit_secs'] = policy.RUN
        cfg['task']['search_only_dev_scorer_sha256'] = sha(scorer)
        for role, op in cfg['solver']['operators'].items():
            effort = policy.effort(row['arm'], role)
            kw = op['llm']['generation_kwargs']
            kw.update(seed=row['seed'], reasoning_effort=effort,
                      max_tokens=8192 if role == 'analyze' else 32768,
                      bounded_request_timeout_seconds=600 if role == 'analyze' else 1500)
            kw['extra_body']['chat_template_kwargs']['enable_thinking'] = effort != 'none'
        write(R/f'configs/{i}.json', cfg)
    driver = R/'image_live_2plus4_20261011.py'
    s = change(driver.read_text(), "TIME_LIMIT='17 minutes',TIME_LIMIT_SECS='1020'", "TIME_LIMIT='30 minutes',TIME_LIMIT_SECS='1800'")
    s = change(s, 'timeout=1110', 'timeout=1890')
    s = change(s, 'dict(configs=48,paired_equal=32,no_kernel=True', 'dict(configs=24,paired_equal=16,no_kernel=True')
    driver.write_text(s)
    shared = R/'generation_joint_trial_20261012.py'
    s = change(shared.read_text(), 'for block in range(6):', 'for block in range(3):')
    s = change(s, "'--time=00:20:00'", "'--time=00:33:00'")
    s = change(s, "'--time=02:19:00'", "'--time=02:05:00'")
    shared.write_text(change(s, 'dict(planned=48,attempted_blocks=', 'dict(planned=24,attempted_blocks='))
    backend = R/'source/src/dojo/core/solvers/llm_helpers/backends/lite_llm.py'
    s = change(backend.read_text(), 'timeout_seconds <= 600', 'timeout_seconds <= 1500')
    s = change(s, "bounded request timeout must be in (0, 600] seconds", "bounded request timeout must be in (0, 1500] seconds")
    s = change(s, "event['state'] = 'response_returned'", "event['state'] = 'response_returned'\n            event['finish_reason'] = self._field(completion.choices[0], 'finish_reason')")
    backend.write_text(s)
    for name in NAMES:
        shutil.copyfile(Path(__file__).with_name(name), R/name)
    shim = R/'bin/singularity'
    shim.write_text(f'#!{base.c.trial.PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(__file__).stem} import host\nhost().task_runtime()\n')
    shim.chmod(0o700)
    with (R/'.service.env').open('x') as f:
        f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    (R/'.service.env').chmod(0o600)
    sb = R/'run.sbatch'
    s = sb.read_text().replace(str(DONOR), str(R)).replace('r14-feedback-effort', 'r14-long-effort')
    s = change(s, 'feedback_effort_trial_20261012.py controller', NAME+' controller')
    s = change(s, '#SBATCH --time=02:04:30', '#SBATCH --time=02:05:00')
    # Donor retains the earlier watchdog; make new allocation the outer bound.
    s = change(s, '7740s', '7440s')
    sb.write_text(s)
    subprocess.run(['bash', '-n', str(sb)], check=True)
    for cache in ('vllm', 'triton'):
        src = DONOR/'block-0/service-cache'/cache
        if src.is_dir():
            shutil.copytree(src, R/'block-0/service-cache'/cache, symlinks=True)
    p.update(source_commit=commit, source_parent_commit=p['source_commit'],
        source_donor_plan_sha256=sha(DONOR/'plan.json'), schedule=schedule(), planned=24,
        allocation_seconds=policy.CAP, gpu_hours_cap=12.5, combined_gpu_seconds_cap=45000,
        new_window_gpu_seconds_cap=45000, prior_failures=[], run_seconds=policy.RUN,
        slot_seconds=policy.SLOT, request_seconds=1500, independent_pool_pairs=0,
        approval='User approved24 runs,2service+4execution,<=7500allocation seconds,<=12.5GPUh on2026-10-13HK.',
        primary='Best timely externally valid development score per task/pool, including common supplied warm start.',
        single_change='Constant code-role reasoning effort none/medium/xhigh; Analyze medium in all arms. Same model, prompts, greedy shared-parent search, images, data and per-task entitlement.',
        common_repairs='Independent experiment: common code output cap32768,request1500s,run1800s,pool1960s; common backend upper bound1500s and finish_reason receipt. Analyze remains8192/600s. No old readout or threshold amended.',
        advance='Exploratory only: all24 complete and structural/mode gates pass; xhigh must improve denoising pool best by>=.001 against BOTH constants and not lose aerial. Otherwise do not expand this long-effort recipe. One pool per arm cannot confirm replication.',
        limitation='Two reused development tasks, aerial near ceiling is regression only. Fixed medium/xhigh/fast order and shared prefix cache remain confounded with pool. Four seeds within shared task archive are NOT independent pool replicates. Conditional warm-start utility, not from-scratch, model-training payoff, test generalization or a novel algorithm.',
        stop='Fixed24, no intermediate outcome readout; infrastructure failure stops later pools. No replacements, automatic retries or budget reuse.',
        preflight_history='CPU native async/real operator, exacteffort transport/template,common config and timeout bounds, independent readout fixtures; no repeated GPU G0.')
    p['files'] = {n: sha(R/n) for n in p['files'] if not n.startswith('configs/')}
    p['files'].update({f'configs/{i}.json': sha(R/f'configs/{i}.json') for i in range(24)})
    p['files'].update({n: sha(R/n) for n in NAMES})
    write(R/'plan.json', p)
    cp = subprocess.run([str(base.c.trial.PY), '-B', str(R/NAME), 'preflight'], cwd=R, capture_output=True)
    (R/'preflight.private.log').write_bytes(cp.stdout+cp.stderr)
    if cp.returncode:
        raise RuntimeError('CPU preflight failed; no submission')
    print(json.dumps(read(R/'preflight.json')))


def preflight():
    p = base.c.trial.check()
    base.c.trial.cpu()
    for row in schedule():
        ref = next(r for r in schedule() if r['seed'] == row['seed'] and r['arm'] == 'medium')
        a, b = (read(R/f"configs/{r['index']}.json") for r in (row, ref))
        assert base.c.trial.t.scientific(policy.normalize(a)) == base.c.trial.t.scientific(policy.normalize(b))
        assert a['solver']['time_limit_secs'] == 1800 and a['interpreter']['timeout'] == 300
        for role, op in a['solver']['operators'].items():
            kw = op['llm']['generation_kwargs']
            assert kw['reasoning_effort'] == policy.effort(row['arm'], role)
            assert kw['max_tokens'] == (8192 if role == 'analyze' else 32768)
            assert kw['bounded_request_timeout_seconds'] == (600 if role == 'analyze' else 1500)
    subprocess.run([str(base.c.trial.PY), '-B', '-m', 'unittest', 'test_long_effort_20261013', 'test_deferred_alarm_transaction_20261012', '-v'], cwd=R, check=True)
    for arm in policy.ARMS:
        subprocess.run([str(base.c.trial.PY), '-B', str(R/'long_effort_native_cpu_20261013.py'), str(R), arm], cwd=R, check=True)
    write(R/'preflight.json', dict(source_commit=p['source_commit'], plan_sha256=sha(R/'plan.json'),
        configs=24, mode_only_pairs=16, native_async_arms=3, no_gpu=True, no_model_calls=True, gpu_hours_cap=12.5))


configure()
if __name__ == '__main__':
    os.umask(0o077)
    os.environ.update(PYTHON_DOTENV_DISABLED='1', PYTHONDONTWRITEBYTECODE='1')
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['prepare', 'preflight', 'submit', 'controller', 'service', 'lane', 'worker'])
    ap.add_argument('--commit'); ap.add_argument('--block', type=int); ap.add_argument('--lane', type=int); ap.add_argument('--index', type=int)
    a = ap.parse_args()
    if a.mode == 'prepare': prepare(a.commit)
    elif a.mode == 'preflight': preflight()
    elif a.mode == 'submit': base.c.submit()
    elif a.mode == 'controller': base.controller()
    elif a.mode == 'service': base.c.trial.service(a.block)
    elif a.mode == 'lane': base.lane(a.block, a.lane)
    else: base.c.worker(a.index)
