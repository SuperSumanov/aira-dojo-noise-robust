"""Approved32-run independent medium-only AB/BA confirmation, <=15 GPUh.

Both pools in each repeat start from the same frozen public preview, native
program and archive. Only deployed weights differ. No training or paid API.
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

DONOR=Path('/research/d7/spc/yzyang4/scheduling-weight-effort-20261014-v4')
sys.path.insert(1,str(DONOR))
import generation_joint_trial_20261012 as base
import joint_generation_policy_20261012 as old_parent
import feedback_parent_policy_20261012 as parent
import weight_effort_policy_20261014 as policy
from lifecycle_pilot import read,write,sha
from fixed_public_preview_20261014 import load_text,install,digest,public_manifest

R=DONOR.parent/'scheduling-weight-confirmation-20261014-v1'
NAME=Path(__file__).name
ORDER=('old_medium','new_medium','new_medium','old_medium')
BUNDLE=Path('/tmp/weight-history-input-20261014-gNF3Jd/public-preview-v2.private.json')
BUNDLE_SHA='d12d04af8684983be97f5ae6277731a65b505b5034244be34343daee02947006'
DONOR_SHA='cba9bad500a106b8c44f18116c491a1744edb50c3744c7f7ef1f498e45cdbd4f'
NAMES=(NAME,'weight_confirmation_readout_20261014.py','test_weight_confirmation_20261014.py',
       'fixed_public_preview_20261014.py','test_fixed_public_preview_20261014.py',
       'fixed_preview_native_cpu_20261014.py','fixed_preview_cpu_matrix_20261014.py')


def schedule():
    return [dict(index=8*b+2*lane+k,block=b,lane=lane,slot=2*lane+k,
        repeat=b//2,arm=arm,task=task,seed=214501+100*(b//2)+2*lane+k)
        for b,arm in enumerate(ORDER) for lane in range(4)
        for k,task in enumerate(base.c.trial.TASKS)]


def install_hooks(row,ep,deadline):
    base.BASE_HOOK(row,ep,deadline)
    policy.install(row,ep,deadline,read(R/'warm.private.json')[row['task']])
    from dojo.solvers.mcts.mcts import MCTS
    from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
    from live_admission import append_event
    matrix=read(R/'input-matrix/summary.safe.json')
    expected=matrix['rows'][row['index']]
    assert all(expected[k]==row[k] for k in ('index','task','arm','seed'))
    text=load_text(R/'public-preview.private.json',BUNDLE_SHA,row['task'])
    install(MCTS,GenericLLM,text,expected['first_prompt_sha256'],
            lambda e:append_event(ep/'input-gate.jsonl',dict(e,index=row['index'])))


def configure():
    base.R,base.CAP,base.RUN,base.SLOT=R,9000,1800,1960
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
        and len(preview)>=1 and all(e['sha256']==expected['preview_sha256'] for e in preview))


def lane(block,requested):
    base.lane(block,requested)
    # Physical lane mapping is recorded by the frozen lane implementation.
    # Check every finished member of this pool; incomplete peers are checked by
    # their own lane before the controller may advance to another pool.
    matrix=read(R/'input-matrix/summary.safe.json')['rows']
    for row in schedule():
        ep=R/f"episode-{row['index']}"
        if row['block']==block and (ep/'closed.json').exists():
            if not input_passed(ep,matrix[row['index']]):
                raise RuntimeError('runtime first-input gate failed; stop remaining pools')


def qualify_service(m):
    # Reuse the exact accepted two-alias check, writing ONLY into the new root.
    import weight_effort_trial_20261014 as prior
    prior.R=R
    try: prior.qualify_service(m)
    finally: configure()


def prepare(commit):
    assert re.fullmatch('[a-f0-9]{40}',commit)
    assert sha(DONOR/'plan.json')==DONOR_SHA and read(DONOR/'closed.json')['complete']==32
    p=read(DONOR/'plan.json')
    assert all(sha(DONOR/n)==h for n,h in p['files'].items())
    assert sha(BUNDLE)==BUNDLE_SHA
    preview=read(BUNDLE)
    for task,v in preview['tasks'].items():
        assert digest(public_manifest(v['public_path']))==v['public_manifest_sha256']
        load_text(BUNDLE,BUNDLE_SHA,task)
    R.mkdir(mode=0o700)
    for n in p['files']:
        if n.startswith('configs/'):continue
        dst=R/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/n,dst)
    (R/'dev-views').symlink_to((DONOR/'dev-views').resolve(),target_is_directory=True)
    (R/'configs').mkdir()
    for b in range(4):(R/f'block-{b}/service-cache/tmp').mkdir(parents=True)
    shutil.copyfile(BUNDLE,R/'public-preview.private.json')
    scorer=R/'image_scorer.py';scorer.write_text(scorer.read_text().replace(str(DONOR),str(R)))
    for row in schedule():
        i=row['index'];ep=R/f'episode-{i}';(ep/'work/input_cache').mkdir(parents=True)
        cfg=json.loads(json.dumps(read(DONOR/f"configs/{row['slot']}.json")).replace(str(DONOR),str(R)))
        def relocate(x):
            if isinstance(x,str):return x.replace(f'episode-{row["slot"]}/',f'episode-{i}/')
            if isinstance(x,list):return [relocate(v) for v in x]
            if isinstance(x,dict):return {k:relocate(v) for k,v in x.items()}
            return x
        cfg=relocate(cfg)
        cfg['id']='weight-confirmation-'+str(i)
        cfg['metadata'].update(seed=row['seed'],script_id='weight-confirmation-20261014')
        cfg['interpreter']['env']['PYTHONHASHSEED']=str(row['seed'])
        cfg['task']['search_only_dev_scorer_sha256']=sha(scorer)
        for op in cfg['solver']['operators'].values():
            op['llm']['client']['model_id']=policy.model(row['arm'])
            kw=op['llm']['generation_kwargs'];kw.update(seed=row['seed'],reasoning_effort='medium')
            kw['extra_body']['chat_template_kwargs']['enable_thinking']=True
        write(R/f'configs/{i}.json',cfg)
    shared=R/'generation_joint_trial_20261012.py'
    shared.write_text(base.c.trial.change(shared.read_text(),
        'from weight_effort_trial_20261014 import qualify_service',
        'from weight_confirmation_trial_20261014 import qualify_service'))
    for n in NAMES:shutil.copyfile(Path(__file__).with_name(n),R/n)
    shim=R/'bin/singularity'
    shim.write_text(f'#!{base.c.trial.PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(__file__).stem} import host\nhost().task_runtime()\n')
    shim.chmod(0o700)
    with (R/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    (R/'.service.env').chmod(0o600)
    sb=R/'run.sbatch'
    sb.write_text(sb.read_text().replace(str(DONOR),str(R)).replace('r14-weight-effort','r14-weight-confirm').replace('weight_effort_trial_20261014.py controller',NAME+' controller'))
    subprocess.run(['bash','-n',str(sb)],check=True)
    for cache in ('vllm','triton'):
        src=DONOR/'block-0/service-cache'/cache
        if src.is_dir():shutil.copytree(src,R/'block-0/service-cache'/cache,symlinks=True)
    p.update(source_commit=commit,source_parent_commit=p['source_commit'],source_donor_plan_sha256=DONOR_SHA,
        schedule=schedule(),native_trial_module=Path(__file__).stem,independent_pool_pairs=2,
        approval='User explicitly approved independent32-run old/new medium AB/BA on2026-10-14HK; <=9000s including startup/failure/cleanup,6GPUs,<=15GPUh. No retry.',
        primary='Within each reversed-order repeat: new-medium minus old-medium best timely externally valid development endpoint/task/pool including identical supplied warm program.',
        single_change='Deployed weights only: exact unadapted base versus same base plus preselected score-step30. All roles medium; same actual first input and initialized history.',
        common_repairs='Frozen native preview built from identical real public data only; runtime first complete prompt checked BEFORE client transport. Kernel cleanup guards retained. Prefix caching disabled in all pools.',
        advance='All32 complete and structural/model/input/cleanup gates; denoising best gain >=.001 in BOTH repeats, aerial best nondecline in BOTH. One positive repeat cannot rescue another. No automatic expansion.',
        limitation='Two reversed-order pool repeats within one allocation/service, not32 independent replicates; residual shared service/time effects remain. Reused developer tasks and supplied warm start. Adapter training revision/cost/overlap unknown. Deployment contrast, not daily-training causality, training-cost ROI, generalization or new algorithm. No fast baseline in this batch.',
        stop='Fixed32. Any isolation/input/cleanup/service failure stops remaining pools. No outcome-dependent reruns/replacements or old-budget reuse.',
        public_preview_sha256=BUNDLE_SHA,common_preview_preparation_wall_seconds=preview['preparation_wall_seconds'])
    # Preflight staging is exclusive, separately hashed, and never a submitted plan.
    write(R/'preparation-plan.json',dict(source_commit=commit,native_trial_module=p['native_trial_module'],schedule=schedule()))
    cp=subprocess.run([str(base.c.trial.PY),'-B',str(R/'fixed_preview_cpu_matrix_20261014.py'),str(R),str(R/'public-preview.private.json'),str(R/'input-matrix')],cwd=R,capture_output=True)
    (R/'input-preflight.private.log').write_bytes(cp.stdout+cp.stderr)
    if cp.returncode:raise RuntimeError('real-input native CPU matrix failed; no frozen plan/submission')
    matrix=read(R/'input-matrix/summary.safe.json')
    assert matrix['assigned']==matrix['passed']==32 and matrix['exact_input_gate'] and len(matrix['paired_groups'])==16
    p['files']={n:sha(R/n) for n in p['files'] if not n.startswith('configs/')}
    p['files'].update({f'configs/{i}.json':sha(R/f'configs/{i}.json') for i in range(32)})
    p['files'].update({n:sha(R/n) for n in NAMES+('public-preview.private.json','preparation-plan.json','input-matrix/summary.safe.json')})
    write(R/'plan.json',p)
    cp=subprocess.run([str(base.c.trial.PY),'-B',str(R/NAME),'preflight'],cwd=R,capture_output=True)
    (R/'preflight.private.log').write_bytes(cp.stdout+cp.stderr)
    if cp.returncode:raise RuntimeError('final CPU preflight failed; no submission')
    print(json.dumps(read(R/'preflight.json')))


def preflight():
    p=base.c.trial.check();base.c.trial.cpu()
    assert len(schedule())==32
    for row in schedule():
        ref=next(r for r in schedule() if r['seed']==row['seed'] and r['arm']=='old_medium')
        a,b=(read(R/f"configs/{r['index']}.json") for r in (row,ref))
        assert base.c.trial.t.scientific(policy.normalize(a))==base.c.trial.t.scientific(policy.normalize(b))
        assert a['solver']['time_limit_secs']==1800 and a['interpreter']['timeout']==300
        for role,op in a['solver']['operators'].items():
            assert op['llm']['client']['model_id']==policy.model(row['arm'])
            kw=op['llm']['generation_kwargs']
            assert kw['reasoning_effort']=='medium' and kw['extra_body']['chat_template_kwargs']['enable_thinking'] is True
            assert kw['max_tokens']==(8192 if role=='analyze' else 32768)
            assert kw['bounded_request_timeout_seconds']==(600 if role=='analyze' else 1500)
    matrix=read(R/'input-matrix/summary.safe.json')
    assert matrix['assigned']==matrix['passed']==32 and matrix['exact_input_gate']
    assert all(r['installed_native_hook'] and r['http_calls']==r['model_calls']==r['gpu_calls']==0 for r in matrix['rows'])
    subprocess.run([str(base.c.trial.PY),'-B','-m','unittest','test_fixed_public_preview_20261014','test_weight_confirmation_20261014','test_deferred_alarm_transaction_20261012','-v'],cwd=R,check=True)
    write(R/'preflight.json',dict(source_commit=p['source_commit'],plan_sha256=sha(R/'plan.json'),
        configs=32,paired_groups=16,native_input_matrix_sha256=sha(R/'input-matrix/summary.safe.json'),
        public_preview_sha256=BUNDLE_SHA,no_gpu=True,no_model_calls=True,gpu_hours_cap=15))


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
