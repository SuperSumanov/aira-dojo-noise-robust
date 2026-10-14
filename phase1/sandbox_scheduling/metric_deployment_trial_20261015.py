"""Approved48-run metric-adapter deployment comparison, <=22.5 full GPUh.

Same fixed public preview/history; old-fast and old-medium are concurrent-batch
controls, not borrowed historical outcomes. No training or paid model API.
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

DONOR=Path('/research/d7/spc/yzyang4/scheduling-weight-confirmation-20261014-v1')
sys.path.insert(1,str(DONOR))
import generation_joint_trial_20261012 as base
import joint_generation_policy_20261012 as old_parent
import feedback_parent_policy_20261012 as parent
import weight_effort_policy_20261014 as policy
from lifecycle_pilot import read,write,sha
from fixed_public_preview_20261014 import load_text,install,digest,public_manifest

R=DONOR.parent/'scheduling-metric-deployment-20261015-v1'
ADAPTER=DONOR.parent/'weight-effort-adapter-metric-20261015-ke666d70/accepted_adapter'
FILE_ID='1w_vb2g8wAZV_NcLPTpRSZgIbi4Bzrkw5'
NAME=Path(__file__).name
ORDER=('old_fast','old_medium','new_medium','new_medium','old_medium','old_fast')
CAP,RUN,SLOT=13500,1800,1960
policy.TRAINED_MODEL='qwen3.8-27b-metric-step30'
BUNDLE=DONOR/'public-preview.private.json'
BUNDLE_SHA='d12d04af8684983be97f5ae6277731a65b505b5034244be34343daee02947006'
DONOR_SHA='316381bce41c9ceb9c34fb165e94996eeeb8c9968eff3cb4e63642fbfa549626'
NAMES=(NAME,'metric_deployment_readout_20261015.py','test_metric_deployment_20261015.py')


def schedule():
    return [dict(index=8*b+2*lane+k,block=b,lane=lane,slot=2*lane+k,
        repeat=b//3,arm=arm,task=task,seed=215001+100*(b//3)+2*lane+k)
        for b,arm in enumerate(ORDER) for lane in range(4)
        for k,task in enumerate(base.c.trial.TASKS)]


def install_hooks(row,ep,deadline):
    base.BASE_HOOK(row,ep,deadline)
    policy.install(row,ep,deadline,read(R/'warm.private.json')[row['task']])
    from dojo.solvers.mcts.mcts import MCTS
    from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
    from live_admission import append_event
    expected=read(R/'input-matrix/summary.safe.json')['rows'][row['index']]
    assert all(expected[k]==row[k] for k in ('index','task','arm','seed'))
    text=load_text(R/'public-preview.private.json',BUNDLE_SHA,row['task'])
    install(MCTS,GenericLLM,text,expected['first_prompt_sha256'],
            lambda e:append_event(ep/'input-gate.jsonl',dict(e,index=row['index'])))


def configure():
    policy.TRAINED_MODEL='qwen3.8-27b-metric-step30'
    base.R,base.CAP,base.RUN,base.SLOT=R,CAP,RUN,SLOT
    base.NAME,base.schedule,base.install_hooks=NAME,schedule,install_hooks
    base.configure()
    old_parent.initialize=parent.initialize


host=base.host


def input_passed(ep,expected):
    path=ep/'input-gate.jsonl'
    events=[json.loads(x) for x in path.read_text().splitlines() if x] if path.exists() else []
    gate=[e for e in events if e['event']=='first_request_input_gate']
    preview=[e for e in events if e['event']=='fixed_public_preview_loaded']
    return (len(gate)==1 and gate[0].get('passed') is True
        and gate[0]['sha256']==gate[0]['expected_sha256']==expected['first_prompt_sha256']
        and bool(preview) and all(e['sha256']==expected['preview_sha256'] for e in preview))


def lane(block,requested):
    base.lane(block,requested)
    matrix=read(R/'input-matrix/summary.safe.json')['rows']
    for row in schedule():
        ep=R/f"episode-{row['index']}"
        if row['block']==block and (ep/'closed.json').exists() and not input_passed(ep,matrix[row['index']]):
            raise RuntimeError('runtime first-input gate failed; stop remaining pools')


def qualify_service(m):
    import weight_effort_trial_20261014 as prior
    prior.R=R
    try: prior.qualify_service(m)
    finally: configure()


def prepare(commit):
    assert re.fullmatch('[a-f0-9]{40}',commit)
    assert sha(DONOR/'plan.json')==DONOR_SHA and read(DONOR/'closed.json')['complete']==32
    p=read(DONOR/'plan.json')
    assert all(sha(DONOR/n)==h for n,h in p['files'].items())
    intake=read(ADAPTER.parent/'intake.safe.json')
    assert intake['file_id']==FILE_ID and intake['declared_lineage']=='metric' and intake['nonfinite_elements']==0
    assert read(ADAPTER.parent/'shape-compat.safe.json')['shape_compatible']
    assert sha(ADAPTER/'adapter_model.safetensors')==intake['weights_sha256']
    assert sha(ADAPTER/'adapter_config.json')==intake['config_sha256']
    assert sha(BUNDLE)==BUNDLE_SHA
    preview=read(BUNDLE)
    for task,v in preview['tasks'].items():
        assert digest(public_manifest(v['public_path']))==v['public_manifest_sha256']
        load_text(BUNDLE,BUNDLE_SHA,task)
    R.mkdir(mode=0o700)
    inherited=[n for n in p['files'] if not n.startswith(('configs/','input-matrix/')) and n!='preparation-plan.json']
    for n in inherited:
        assert not n.endswith('.env')
        dst=R/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/n,dst)
    (R/'dev-views').symlink_to((DONOR/'dev-views').resolve(),target_is_directory=True)
    (R/'configs').mkdir()
    for b in range(6):(R/f'block-{b}/service-cache/tmp').mkdir(parents=True)
    change=base.c.trial.change
    scorer=R/'image_scorer.py';scorer.write_text(scorer.read_text().replace(str(DONOR),str(R)))
    for row in schedule():
        i=row['index'];ep=R/f'episode-{i}';(ep/'work/input_cache').mkdir(parents=True)
        cfg=json.loads(json.dumps(read(DONOR/f"configs/{row['slot']}.json")).replace(str(DONOR),str(R)))
        def relocate(x):
            if isinstance(x,str):return x.replace(f'episode-{row["slot"]}/',f'episode-{i}/')
            if isinstance(x,list):return [relocate(v) for v in x]
            if isinstance(x,dict):return {k:relocate(v) for k,v in x.items()}
            return x
        cfg=relocate(cfg);cfg['id']='metric-deployment-'+str(i)
        cfg['metadata'].update(seed=row['seed'],script_id='metric-deployment-20261015')
        cfg['interpreter']['env']['PYTHONHASHSEED']=str(row['seed'])
        cfg['task']['search_only_dev_scorer_sha256']=sha(scorer)
        for role,op in cfg['solver']['operators'].items():
            e=policy.effort(row['arm'],role)
            op['llm']['client']['model_id']=policy.model(row['arm'])
            op['llm']['generation_kwargs'].update(seed=row['seed'],reasoning_effort=e)
            op['llm']['generation_kwargs']['extra_body']['chat_template_kwargs']['enable_thinking']=e!='none'
        write(R/f'configs/{i}.json',cfg)
    driver=R/'image_live_2plus4_20261011.py'
    s=change(driver.read_text(),str(p['adapter']['directory']),str(ADAPTER))
    driver.write_text(change(s,'dict(configs=32,paired_equal=24,no_kernel=True','dict(configs=48,paired_equal=32,no_kernel=True'))
    shared=R/'generation_joint_trial_20261012.py'
    s=change(shared.read_text(),'for block in range(4):','for block in range(6):')
    s=change(s,"'--time=02:30:00'","'--time=03:45:00'")
    s=change(s,'from weight_confirmation_trial_20261014 import qualify_service','from metric_deployment_trial_20261015 import qualify_service')
    s=change(s,'dict(planned=32,attempted_blocks=','dict(planned=48,attempted_blocks=')
    shared.write_text(change(s,'qwen3.8-27b-score-step30','qwen3.8-27b-metric-step30'))
    for name in ('service_entry.py','weight_effort_policy_20261014.py'):
        f=R/name;f.write_text(change(f.read_text(),'qwen3.8-27b-score-step30','qwen3.8-27b-metric-step30'))
    for n in NAMES:shutil.copyfile(Path(__file__).with_name(n),R/n)
    shim=R/'bin/singularity'
    shim.write_text(f'#!{base.c.trial.PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(__file__).stem} import host\nhost().task_runtime()\n');shim.chmod(0o700)
    with (R/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    (R/'.service.env').chmod(0o600)
    sb=R/'run.sbatch';s=sb.read_text().replace(str(DONOR),str(R))
    s=change(s,'r14-weight-confirm','r14-metric-deploy')
    s=change(s,'weight_confirmation_trial_20261014.py controller',NAME+' controller')
    s=change(s,'#SBATCH --time=02:30:00','#SBATCH --time=03:45:00')
    sb.write_text(change(s,'8940s','13440s'));subprocess.run(['bash','-n',str(sb)],check=True)
    for cache in ('vllm','triton'):
        src=DONOR/'block-0/service-cache'/cache
        if src.is_dir():shutil.copytree(src,R/'block-0/service-cache'/cache,symlinks=True)
    previous_adapter=p['adapter']['directory']
    p.update(source_commit=commit,source_parent_commit=p['source_commit'],source_donor_plan_sha256=DONOR_SHA,
        schedule=schedule(),planned=48,native_trial_module=Path(__file__).stem,independent_pool_pairs=2,
        allocation_seconds=CAP,gpu_hours_cap=22.5,combined_gpu_seconds_cap=81000,new_window_gpu_seconds_cap=81000,
        prior_failures=[],run_seconds=RUN,slot_seconds=SLOT,
        approval='Explicit user approval2026-10-15HK:48 runs,2service+4execution,<=13500seconds including startup/failure/cleanup,<=22.5GPUh. No automatic retry.',
        primary='Fixed metric-medium deployment versus old-medium; strong old-fast reference must also be beaten. Compare each reverse-order pool repeat separately.',
        single_change='Weight contrast within medium; old-fast is an additional strong reference, not a second changed knob in the primary contrast. Shared initial history/data/image/base and all-role weights follow arm; Analyze always medium.',
        advance='All48 complete and all structure/input/model/isolation/cleanup gates pass; metric-medium denoising best improves BOTH old references by>=.001 in BOTH repeats, aerial best nondecline against BOTH references in BOTH repeats. No pooled rescue.',
        limitation='Exploratory deployment only; two reverse-order pool repeats in one allocation/service, not48 independent trials. Reused development tasks/warm starts, aerial near ceiling. Not fixed-data reward ablation, daily-training causality, total-training-cost ROI or generalization.',
        stop='Fixed48; no interim quality inspection, substitution, retries or reuse of prior budgets. Infrastructure/input/model/cleanup failures stop remaining pools.',
        adapter=dict(directory=str(ADAPTER),selected_file_id=FILE_ID,declared_lineage='metric',
            selection='First newly visible metric step30 fixed before outcomes; do not replace with later daily checkpoint.',
            weights_sha256=intake['weights_sha256'],config_sha256=intake['config_sha256'],exact_training_revision_known=False),
        public_preview_sha256=BUNDLE_SHA,common_preview_preparation_wall_seconds=preview['preparation_wall_seconds'])
    p['model_files']={n:h for n,h in p['model_files'].items() if not n.startswith(previous_adapter+'/')}
    p['model_files'].update({str(ADAPTER/'adapter_model.safetensors'):intake['weights_sha256'],str(ADAPTER/'adapter_config.json'):intake['config_sha256']})
    write(R/'preparation-plan.json',dict(source_commit=commit,native_trial_module=p['native_trial_module'],schedule=schedule()))
    cp=subprocess.run([str(base.c.trial.PY),'-B',str(R/'fixed_preview_cpu_matrix_20261014.py'),str(R),str(R/'public-preview.private.json'),str(R/'input-matrix')],cwd=R,capture_output=True)
    (R/'input-preflight.private.log').write_bytes(cp.stdout+cp.stderr)
    if cp.returncode:raise RuntimeError('native CPU input matrix failed; no submission')
    matrix=read(R/'input-matrix/summary.safe.json')
    assert matrix['assigned']==matrix['passed']==48 and matrix['exact_input_gate'] and len(matrix['paired_groups'])==16
    p['files']={n:sha(R/n) for n in inherited}
    p['files'].update({f'configs/{i}.json':sha(R/f'configs/{i}.json') for i in range(48)})
    p['files'].update({n:sha(R/n) for n in NAMES+('preparation-plan.json','input-matrix/summary.safe.json')})
    write(R/'plan.json',p)
    cp=subprocess.run([str(base.c.trial.PY),'-B',str(R/NAME),'preflight'],cwd=R,capture_output=True)
    (R/'preflight.private.log').write_bytes(cp.stdout+cp.stderr)
    if cp.returncode:raise RuntimeError('final CPU preflight failed; no submission')
    print(json.dumps(read(R/'preflight.json')))


def preflight():
    p=base.c.trial.check();base.c.trial.cpu()
    assert len(schedule())==48
    for row in schedule():
        ref=next(r for r in schedule() if r['seed']==row['seed'] and r['arm']=='old_medium')
        a,b=(read(R/f"configs/{r['index']}.json") for r in (row,ref))
        assert base.c.trial.t.scientific(policy.normalize(a))==base.c.trial.t.scientific(policy.normalize(b))
        assert a['solver']['time_limit_secs']==RUN and a['interpreter']['timeout']==300
        for role,op in a['solver']['operators'].items():
            assert op['llm']['client']['model_id']==policy.model(row['arm'])
            kw=op['llm']['generation_kwargs'];effort=policy.effort(row['arm'],role)
            assert kw['reasoning_effort']==effort and kw['extra_body']['chat_template_kwargs']['enable_thinking']==(effort!='none')
            assert kw['max_tokens']==(8192 if role=='analyze' else 32768)
            assert kw['bounded_request_timeout_seconds']==(600 if role=='analyze' else 1500)
    matrix=read(R/'input-matrix/summary.safe.json')
    assert matrix['assigned']==matrix['passed']==48 and matrix['exact_input_gate']
    assert all(r['installed_native_hook'] and r['http_calls']==r['model_calls']==r['gpu_calls']==0 for r in matrix['rows'])
    subprocess.run([str(base.c.trial.PY),'-B','-m','unittest','test_fixed_public_preview_20261014','test_metric_deployment_20261015','test_deferred_alarm_transaction_20261012','-v'],cwd=R,check=True)
    write(R/'preflight.json',dict(source_commit=p['source_commit'],plan_sha256=sha(R/'plan.json'),configs=48,paired_groups=16,
        native_input_matrix_sha256=sha(R/'input-matrix/summary.safe.json'),public_preview_sha256=BUNDLE_SHA,no_gpu=True,no_model_calls=True,gpu_hours_cap=22.5))


configure()
if __name__=='__main__':
    os.umask(0o077);os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','preflight','submit','controller','service','lane','worker'])
    ap.add_argument('--commit');ap.add_argument('--block',type=int);ap.add_argument('--lane',type=int);ap.add_argument('--index',type=int)
    a=ap.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='preflight':preflight()
    elif a.mode=='submit':base.c.submit()
    elif a.mode=='controller':base.controller()
    elif a.mode=='service':base.c.trial.service(a.block)
    elif a.mode=='lane':lane(a.block,a.lane)
    else:base.c.worker(a.index)
