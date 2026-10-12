"""Independent 48-run, 13 GPU-hour conditional effort-allocation screen.

This is not a new reasoning-routing claim: Ares directly covers that broad idea.
Question: can cheap proposals plus reasoning AFTER failure beat both constant
code-generation modes under equal total serving+execution wall-clock cost?
"""
import argparse,copy,json,os,re,secrets,shutil,subprocess,sys
from pathlib import Path
DONOR=Path('/research/d7/spc/yzyang4/scheduling-feedback-parent-20261012-v1')
sys.path.insert(1,str(DONOR))
import generation_joint_trial_20261012 as base
import joint_generation_policy_20261012 as old_policy
import feedback_effort_policy_20261012 as policy
from lifecycle_pilot import read,write,sha
R=DONOR.parent/'scheduling-feedback-effort-20261012-v2'
CAP=7470
FAILED=DONOR.parent/'scheduling-feedback-effort-20261012-v1'
NAME=Path(__file__).name
NAMES=(NAME,'feedback_effort_policy_20261012.py','feedback_effort_readout_20261012.py',
       'test_feedback_effort_20261012.py','deferred_alarm_transaction_20261012.py',
       'test_deferred_alarm_transaction_20261012.py','feedback_effort_native_cpu_20261012.py')

def schedule():
    return [dict(index=8*b+2*lane+k,block=b,lane=lane,slot=2*lane+k,repeat=b//3,
        arm=arm,task=task,seed=213101+100*(b//3)+2*lane+k)
        for b,arm in enumerate(policy.ORDER) for lane in range(4) for k,task in enumerate(base.c.trial.TASKS)]

def install_hooks(row,ep,deadline):
    base.BASE_HOOK(row,ep,deadline)
    policy.install(row,ep,deadline,read(R/'warm.private.json')[row['task']])

def configure():
    base.R=R;base.CAP=CAP;base.NAME=NAME;base.schedule=schedule;base.install_hooks=install_hooks
    base.configure();old_policy.initialize=policy.initialize

host=base.host

def prepare(commit):
    assert re.fullmatch('[a-f0-9]{40}',commit)
    failure=read(FAILED/'readout-v1/summary.json')
    assert read(FAILED/'launch.json')['job']=='17736' and failure['complete']==0 and failure['scores_recomputed']==0
    assert failure['gpu_seconds']==1968 and not any(FAILED.glob('episode-*/effort.jsonl'))
    assert sha(DONOR/'plan.json')=='e6d41cd7b40598f349e7956d3daaf610d85c5e00170b4d358b9e5cfdaa9910ee'
    closed=read(DONOR/'partial-readout-v1/summary.json')
    assert closed['predeclared_success_gate_met'] is False
    p=read(DONOR/'plan.json');assert all(sha(DONOR/n)==h for n,h in p['files'].items())
    R.mkdir(mode=0o700)
    for n in p['files']:
        if n.startswith('configs/'):continue
        dst=R/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/n,dst)
    (R/'dev-views').symlink_to((DONOR/'dev-views').resolve(),target_is_directory=True)
    (R/'configs').mkdir()
    for b in range(6):(R/f'block-{b}/service-cache/tmp').mkdir(parents=True)
    scorer=R/'image_scorer.py';scorer.write_text(scorer.read_text().replace(str(DONOR),str(R)))
    for row in schedule():
        i=row['index'];ep=R/f'episode-{i}';(ep/'work/input_cache').mkdir(parents=True)
        cfg=json.loads(json.dumps(read(DONOR/f'configs/{i}.json')).replace(str(DONOR),str(R)))
        cfg['id']='feedback-effort-'+str(i);cfg['metadata'].update(seed=row['seed'],script_id='feedback-effort-20261012')
        cfg['interpreter']['env']['PYTHONHASHSEED']=str(row['seed'])
        cfg['task']['search_only_dev_scorer_sha256']=sha(scorer)
        for role,op in cfg['solver']['operators'].items():
            # Native configuration calls the analysis operator "analyze".
            enabled=policy.thinking(row['arm'],role)
            kw=op['llm']['generation_kwargs'];kw.update(seed=row['seed'],reasoning_effort='medium' if enabled else 'none')
            kw['extra_body']['chat_template_kwargs']['enable_thinking']=enabled
        write(R/f'configs/{i}.json',cfg)
    for n in NAMES:shutil.copyfile(Path(__file__).with_name(n),R/n)
    shim=R/'bin/singularity';shim.write_text(f'#!{base.c.trial.PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(__file__).stem} import host\nhost().task_runtime()\n');shim.chmod(0o700)
    with (R/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    (R/'.service.env').chmod(0o600)
    sb=R/'run.sbatch';s=sb.read_text().replace(str(DONOR),str(R)).replace('r14-feedback-parent','r14-feedback-effort').replace('feedback_parent_trial_20261012.py controller',NAME+' controller')
    s=s.replace('#SBATCH --time=02:10:00','#SBATCH --time=02:04:30')
    sb.write_text(s);subprocess.run(['bash','-n',str(sb)],check=True)
    assert '#SBATCH --time=02:04:30' in s
    for cache in ('vllm','triton'):
        src=DONOR/'block-0/service-cache'/cache
        if src.is_dir():shutil.copytree(src,R/'block-0/service-cache'/cache,symlinks=True)
    p.update(source_commit=commit,source_parent_commit=p['source_commit'],source_donor_plan_sha256=sha(DONOR/'plan.json'),
        schedule=schedule(),allocation_seconds=CAP,gpu_hours_cap=CAP*6/3600,combined_gpu_seconds_cap=1968+CAP*6,
        prior_failures=[dict(job='17736',gpu_seconds=1968,started=8,complete=0,model_calls=0)],new_window_gpu_seconds_cap=46800,
        primary='Best timely externally valid score per task/pool, common supplied warm start included.',
        single_change='Inference effort for code roles: all medium; all nonthinking; nonthinking Improve plus medium Debug. Analyze remains medium. Shared best-parent greedy, FIFO completion priority, prompts, caps, seeds, images and data fixed.',
        common_repairs='Python SIGALRM deferral across short locked state transactions; no extra score time. v2 only adds native async call support to the common effort recorder. Old17736 and its48 assigned rows remain separately closed; explicit zero-outcome entry amendment announced before new batch. No strategy, seeds, prompts or within-pool budgets change.',
        practical_margin={'denoising-dirty-documents':.001,'aerial-cactus-identification':0.0},
        advance='All48 normal with six equal pools and actual mode receipts. feedback_think must beat both constant modes by denoising RMSE>=.001 in BOTH pool repeats, and not lose aerial AUC; otherwise stop this recipe. More generated/valid candidates alone cannot pass.',
        limitation='Exploratory two already-observed development tasks, aerial near ceiling only regression control. Conditional refinement, not from-scratch or official test. Two pool repeats, not48 independent samples. CoT-retry and Ares are direct prior art; this is known-strategy baseline qualification, not novelty or SOTA superiority. No claim that faster generation implies improvement.',
        stop='No intermediate outcomes. Fixed48; infrastructure failure stops later pools, all failures retained, no replacement or rescue.',
        preflight_history='New effort-timing hypothesis; waiting and stale-repair opportunity schemes rejected. CPU real operator path, mode-only config comparisons, signal interruption tests and tokenizer template distinction required.')
    p['files']={n:sha(R/n) for n in p['files']}
    p['files'].update({n:sha(R/n) for n in NAMES})
    write(R/'plan.json',p)
    cp=subprocess.run([str(base.c.trial.PY),'-B',str(R/NAME),'preflight'],cwd=R,capture_output=True)
    (R/'preflight.private.log').write_bytes(cp.stdout+cp.stderr)
    if cp.returncode:raise RuntimeError('CPU preflight failed; no submission')
    print(json.dumps(read(R/'preflight.json')))

def preflight():
    p=base.c.trial.check();base.c.trial.cpu()
    for row in schedule():
        ref=next(r for r in schedule() if r['seed']==row['seed'] and r['arm']=='medium')
        a,b=(read(R/f"configs/{r['index']}.json") for r in (row,ref))
        assert base.c.trial.t.scientific(policy.normalize(a))==base.c.trial.t.scientific(policy.normalize(b))
        assert a['solver']['time_limit_secs']==1020
        for role,op in a['solver']['operators'].items():
            kw=op['llm']['generation_kwargs'];assert kw['max_tokens']==8192 and kw['bounded_request_timeout_seconds']==600
            enabled=policy.thinking(row['arm'],role)
            assert kw['extra_body']['chat_template_kwargs']['enable_thinking'] is enabled
            assert kw['reasoning_effort']==('medium' if enabled else 'none')
    subprocess.run([str(base.c.trial.PY),'-B','-m','unittest','test_feedback_effort_20261012','test_deferred_alarm_transaction_20261012','test_feedback_parent_20261012','-v'],cwd=R,check=True)
    from feedback_parent_readout_20261012 import native_cpu_test
    native_cpu_test(R,host,install_hooks)
    for arm in policy.ARMS:
        subprocess.run([str(base.c.trial.PY),'-B',str(R/'feedback_effort_native_cpu_20261012.py'),str(R),arm],cwd=R,check=True)
    # Actual shipped tokenizer template, never an inferred low/medium mapping.
    model=DONOR.parent/'local-qwen27b-20260914-zcx1k1dy/model'
    from jinja2.sandbox import ImmutableSandboxedEnvironment
    tc=read(model/'tokenizer_config.json');template=tc['chat_template']
    if not isinstance(template,str):raise ValueError('unexpected template interface')
    env=ImmutableSandboxedEnvironment(trim_blocks=True,lstrip_blocks=True)
    env.globals['raise_exception']=lambda x:(_ for _ in ()).throw(ValueError(x))
    compiled=env.from_string(template)
    values=[]
    for enabled in (False,True):
        rendered=compiled.render(messages=[{'role':'user','content':'Return one Python print statement.'}],add_generation_prompt=True,enable_thinking=enabled,tools=None)
        values.append(rendered)
    assert values[0]!=values[1] and '</think>' in values[0][-100:] and '<think>' in values[1][-100:]
    write(R/'preflight.json',dict(source_commit=p['source_commit'],plan_sha256=sha(R/'plan.json'),configs=48,mode_only_pairs=32,
        native_expand_parse_debug_checkpoint=True,native_async_recorder_arms=3,signal_tests=4,mode_tests=7,parent_tests=17,tokenizer_modes_distinct=True,
        tokenizer_config_sha256=sha(model/'tokenizer_config.json'),no_gpu=True,no_model_calls=True,gpu_hours_cap=CAP*6/3600,
        prior_failed_gpu_seconds=1968,window_gpu_hours_cap=(1968+CAP*6)/3600))

configure()
if __name__=='__main__':
    os.umask(0o077);os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','preflight','submit','controller','service','lane','worker'])
    ap.add_argument('--commit');ap.add_argument('--block',type=int);ap.add_argument('--lane',type=int);ap.add_argument('--index',type=int);a=ap.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='preflight':preflight()
    elif a.mode=='submit':base.c.submit()
    elif a.mode=='controller':base.controller()
    elif a.mode=='service':base.c.trial.service(a.block)
    elif a.mode=='lane':base.lane(a.block,a.lane)
    else:base.c.worker(a.index)
