"""Approved32-run deployed-adapter factorial; <=15 full-allocation GPU hours.

Old=the exact unadapted quantized base; new=one preselected shared score-step30
adapter on THAT base. This is not two date-adjacent checkpoints or training ROI.
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

DONOR = Path('/research/d7/spc/yzyang4/scheduling-long-effort-20261013-v1')
sys.path.insert(1, str(DONOR))
import generation_joint_trial_20261012 as base
import joint_generation_policy_20261012 as old_parent
import feedback_parent_policy_20261012 as parent
import weight_effort_policy_20261014 as policy
from lifecycle_pilot import read, write, sha

R = DONOR.parent/'scheduling-weight-effort-20261014-v1'
ADAPTER = DONOR.parent/'weight-effort-adapter-20261014-ynf9spm3/accepted_adapter'
NAME = Path(__file__).name
NAMES = (NAME, 'weight_effort_policy_20261014.py', 'weight_effort_readout_20261014.py',
         'test_weight_effort_20261014.py', 'weight_effort_native_cpu_20261014.py')
WEIGHT_SHA = 'c7666264904a3490958e46cfbb989a22bc52b9a81c9714631751c7bf8445b61f'
CONFIG_SHA = 'f0a0264f243f57a126a9903499ee48984e660a6bf0ad7b3d351431ce4546198e'


def schedule():
    return [dict(index=8*b+2*lane+k, block=b, lane=lane, slot=2*lane+k,
                 repeat=0, arm=arm, task=task, seed=214401+2*lane+k)
            for b, arm in enumerate(policy.ORDER) for lane in range(4)
            for k, task in enumerate(base.c.trial.TASKS)]


def install_hooks(row, ep, deadline):
    base.BASE_HOOK(row, ep, deadline)
    policy.install(row, ep, deadline, read(R/'warm.private.json')[row['task']])


def configure():
    base.R, base.CAP, base.RUN, base.SLOT = R, policy.CAP, policy.RUN, policy.SLOT
    base.NAME, base.schedule, base.install_hooks = NAME, schedule, install_hooks
    base.configure()
    old_parent.initialize = parent.initialize


host = base.host


def prepare(commit):
    assert re.fullmatch('[a-f0-9]{40}', commit)
    assert sha(DONOR/'plan.json') == 'cef33dddaf5973d067b8b7c1b415a1f1512e73b6fae5cdb23deb6a3ed410bd00'
    assert read(DONOR/'closed.json')['complete'] == 24
    assert sha(ADAPTER/'adapter_model.safetensors') == WEIGHT_SHA
    assert sha(ADAPTER/'adapter_config.json') == CONFIG_SHA
    assert read(ADAPTER.parent/'shape-compat.safe.json')['shape_compatible']
    p = read(DONOR/'plan.json')
    assert all(sha(DONOR/n) == h for n, h in p['files'].items())
    R.mkdir(mode=0o700)
    for n in p['files']:
        if n.startswith('configs/'):
            continue
        dst = R/n; dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DONOR/n, dst)
    (R/'dev-views').symlink_to((DONOR/'dev-views').resolve(), target_is_directory=True)
    (R/'configs').mkdir()
    for b in range(4):
        (R/f'block-{b}/service-cache/tmp').mkdir(parents=True)
    scorer = R/'image_scorer.py'
    scorer.write_text(scorer.read_text().replace(str(DONOR), str(R)))
    change = base.c.trial.change
    for row in schedule():
        i = row['index']; ep = R/f'episode-{i}'
        (ep/'work/input_cache').mkdir(parents=True)
        cfg = json.loads(json.dumps(read(DONOR/f"configs/{row['slot']}.json")).replace(str(DONOR), str(R)))
        # Indices24..31 are new; rewrite every run-scoped path, not just id.
        def relocate(value):
            if isinstance(value, str):
                return value.replace(f'episode-{row["slot"]}/', f'episode-{i}/')
            if isinstance(value, list): return [relocate(x) for x in value]
            if isinstance(value, dict): return {k: relocate(v) for k, v in value.items()}
            return value
        cfg = relocate(cfg)
        cfg['id'] = 'weight-effort-'+str(i)
        cfg['metadata'].update(seed=row['seed'], script_id='weight-effort-20261014')
        cfg['interpreter']['env']['PYTHONHASHSEED'] = str(row['seed'])
        cfg['solver']['time_limit_secs'] = policy.RUN
        cfg['task']['search_only_dev_scorer_sha256'] = sha(scorer)
        for role, op in cfg['solver']['operators'].items():
            e = policy.effort(row['arm'], role)
            op['llm']['client']['model_id'] = policy.model(row['arm'])
            kw = op['llm']['generation_kwargs']
            kw.update(seed=row['seed'], reasoning_effort=e)
            kw['extra_body']['chat_template_kwargs']['enable_thinking'] = e != 'none'
        write(R/f'configs/{i}.json', cfg)
    driver = R/'image_live_2plus4_20261011.py'
    s = change(driver.read_text(), 'dict(configs=24,paired_equal=16,no_kernel=True', 'dict(configs=32,paired_equal=24,no_kernel=True')
    s = change(s, "'--bind',str(model)+':/model:ro'", "'--bind',str(Path("+repr(str(ADAPTER))+"))+':/adapter:ro','--bind',str(model)+':/model:ro'")
    driver.write_text(s)
    shared = R/'generation_joint_trial_20261012.py'
    s = change(shared.read_text(), 'for block in range(3):', 'for block in range(4):')
    s = change(s, "'--time=02:05:00'", "'--time=02:30:00'")
    s = change(s, "=={'qwen3.8-27b'}", "=={'qwen3.8-27b','qwen3.8-27b-score-step30'}")
    s = change(s, "write(R/'service-ready.json',dict(startup_seconds=time.monotonic()-begin))", "from weight_effort_trial_20261014 import qualify_service\n        qualify_service(m)\n        write(R/'service-ready.json',dict(startup_seconds=time.monotonic()-begin))")
    shared.write_text(change(s, 'dict(planned=24,attempted_blocks=', 'dict(planned=32,attempted_blocks='))
    entry = R/'service_entry.py'
    s = change(entry.read_text(), "'--seed','49']", "'--seed','49','--enable-lora','--max-lora-rank','128','--max-loras','1','--lora-modules','qwen3.8-27b-score-step30=/adapter','--no-enable-prefix-caching']")
    entry.write_text(s)
    for name in NAMES:
        shutil.copyfile(Path(__file__).with_name(name), R/name)
    shim = R/'bin/singularity'
    shim.write_text(f'#!{base.c.trial.PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(__file__).stem} import host\nhost().task_runtime()\n')
    shim.chmod(0o700)
    with (R/'.service.env').open('x') as f:
        f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    (R/'.service.env').chmod(0o600)
    sb = R/'run.sbatch'
    s = sb.read_text().replace(str(DONOR), str(R)).replace('r14-long-effort', 'r14-weight-effort')
    s = change(s, 'long_effort_trial_20261013.py controller', NAME+' controller')
    s = change(s, '#SBATCH --time=02:05:00', '#SBATCH --time=02:30:00')
    s = change(s, '7440s', '8940s')
    sb.write_text(s); subprocess.run(['bash', '-n', str(sb)], check=True)
    for cache in ('vllm', 'triton'):
        src = DONOR/'block-0/service-cache'/cache
        if src.is_dir(): shutil.copytree(src, R/'block-0/service-cache'/cache, symlinks=True)
    p.update(source_commit=commit, source_parent_commit=p['source_commit'],
        source_donor_plan_sha256=sha(DONOR/'plan.json'), schedule=schedule(), planned=32,
        allocation_seconds=policy.CAP, gpu_hours_cap=15, combined_gpu_seconds_cap=54000,
        new_window_gpu_seconds_cap=54000, prior_failures=[], run_seconds=policy.RUN,
        slot_seconds=policy.SLOT, independent_pool_pairs=0,
        approval='Explicit user approved32 runs,2service+4execution,<=9000allocation seconds,<=15GPUh on2026-10-14HK. No automatic retry.',
        primary='New-medium versus old-medium: best timely externally valid development score/task/pool, including IDENTICAL supplied warm start. Fast within-mode contrast is secondary.',
        single_change='Factorial deployed weights (unadapted exact base vs that base+one preselected adapter) x constant code effort none/medium. Analyze effort medium always, weights follow arm for every role.',
        common_repairs='Common service enables rank128 LoRA; prefix caching disabled for ALL conditions to prevent prior-pool prompt-cache carryover. Same base/image/template/data/history/seeds/budget. Other constants inherited from closed18161.',
        advance='Exploratory only: all32 complete and source/identity/model/prompt/cleanup gates pass; new-medium must improve denoising pool best over old-medium by>=.001 and not lose aerial. Secondary fast comparison cannot rescue primary failure. No automatic expansion.',
        limitation='One shared pool/condition, fixed order old-fast/new-medium/new-fast/old-medium; shared service load/order remains a confound. Reused dev tasks; aerial near ceiling is regression only. Adapter exact training revision, training cost and training-set overlap unknown: deployment of supplied adapter only, NOT daily-training causality, amortized total-cost ROI or held-out generalization.',
        stop='Fixed32, no intermediate outcome readout. Infrastructure/adapter/isolation failure stops remaining pools. No replacement/retry/budget reuse.',
        adapter=dict(directory=str(ADAPTER), selected_file_id='1_GXBwH5jRXTnt-lW_-ur4l0rUPBav2ZK',
                     selection='Shared online_thinking_score step30 selected before quality, not date-adjacent checkpoint claim.',
                     weights_sha256=WEIGHT_SHA, config_sha256=CONFIG_SHA, exact_training_revision_known=False),
        common_start_sha256=sha(R/'warm.private.json'), common_start_receipt_sha256=sha(R/'warm-receipt.json'))
    p['model_files'].update({str(ADAPTER/'adapter_model.safetensors'): WEIGHT_SHA, str(ADAPTER/'adapter_config.json'): CONFIG_SHA})
    p['files'] = {n: sha(R/n) for n in p['files'] if not n.startswith('configs/')}
    p['files'].update({f'configs/{i}.json': sha(R/f'configs/{i}.json') for i in range(32)})
    p['files'].update({n: sha(R/n) for n in NAMES})
    write(R/'plan.json', p)
    cp = subprocess.run([str(base.c.trial.PY), '-B', str(R/NAME), 'preflight'], cwd=R, capture_output=True)
    (R/'preflight.private.log').write_bytes(cp.stdout+cp.stderr)
    if cp.returncode: raise RuntimeError('CPU preflight failed; no submission')
    print(json.dumps(read(R/'preflight.json')))


def qualify_service(m):
    """Only synthetic tiny requests, charged to THIS allocation before32 runs."""
    import time
    import requests
    session = requests.Session(); session.trust_env = False
    rows = []
    for alias in (policy.BASE_MODEL, policy.TRAINED_MODEL):
        started = time.monotonic()
        res = session.post('http://127.0.0.1:19475/v1/chat/completions',
            headers={'Authorization': 'Bearer '+m.infra().local_key()},
            json=dict(model=alias, messages=[dict(role='user', content='Reply with the single word READY.')],
                      temperature=0, seed=214400, max_tokens=8, reasoning_effort='none',
                      chat_template_kwargs=dict(enable_thinking=False)), timeout=90)
        assert res.status_code == 200, 'model route qualification failure'
        data = res.json()
        assert data['model'] == alias and data['choices'][0]['message']['content'], 'empty/misrouted model'
        rows.append(dict(model_id=alias, seconds=time.monotonic()-started,
                         output_tokens=data['usage']['completion_tokens'], response_received=True))
    write(R/'adapter-service-qualification.json', dict(rows=rows, synthetic_only=True, quality_claim=False))


def preflight():
    p = base.c.trial.check(); base.c.trial.cpu()
    assert len(schedule()) == 32
    for row in schedule():
        ref = next(r for r in schedule() if r['seed'] == row['seed'] and r['arm'] == 'old_medium')
        a, b = (read(R/f"configs/{r['index']}.json") for r in (row, ref))
        assert base.c.trial.t.scientific(policy.normalize(a)) == base.c.trial.t.scientific(policy.normalize(b))
        assert a['solver']['time_limit_secs'] == 1800 and a['interpreter']['timeout'] == 300
        for role, op in a['solver']['operators'].items():
            assert op['llm']['client']['model_id'] == policy.model(row['arm'])
            kw = op['llm']['generation_kwargs']
            assert kw['reasoning_effort'] == policy.effort(row['arm'], role)
            assert kw['max_tokens'] == (8192 if role == 'analyze' else 32768)
            assert kw['bounded_request_timeout_seconds'] == (600 if role == 'analyze' else 1500)
    subprocess.run([str(base.c.trial.PY), '-B', '-m', 'unittest', 'test_weight_effort_20261014', 'test_deferred_alarm_transaction_20261012', '-v'], cwd=R, check=True)
    for arm in policy.ARMS:
        subprocess.run([str(base.c.trial.PY), '-B', str(R/'weight_effort_native_cpu_20261014.py'), str(R), arm], cwd=R, check=True)
    hashes = [read(R/f'cpu-prompt-{a}.json')['prompt_sha256'] for a in policy.ARMS]
    assert len(set(hashes)) == 1, 'unequal first native Improve prompt/history'
    write(R/'preflight.json', dict(source_commit=p['source_commit'], plan_sha256=sha(R/'plan.json'),
        configs=32, factorial_pairs=24, native_async_arms=4, identical_first_improve_prompt_sha256=hashes[0],
        no_gpu=True, no_model_calls=True, gpu_hours_cap=15))


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
