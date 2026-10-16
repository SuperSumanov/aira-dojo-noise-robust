"""Independent chronological-source confirmation, conditional on sealed18819.

Reuses the exact rank execution/worker functions. Only source cohort and root
change, as declared in333c5662 before18819 outcomes. No new outcome selection.
v1/18844 failed before candidate execution: inherited namespace import named
the old donor module. v2 uses the new donor's AST-identical namespace function.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import clock_rank_20261016 as rank

base=rank.base
D=Path('/research/d7/spc/yzyang4/scheduling-colocation-20261016-v1')
R=D.parent/'clock-rank-confirmation-20261016-v2'
PIN='36ce5852b26de2299755c19a8b9711a1f4161d68abd25a3de6cc7687cdde8560'
PRIOR=D.parent/'clock-rank-20261016-v1/readout-20261016-v1/summary.json'
PRIOR_SHA='0f5ba4f180d2b82d0a0e343e140791e35447d138d615f417e99a83bf366ed0ba'
NAME=Path(__file__).name
WINDOW_END=1792142280  # 2026-10-16 09:18:00 UTC
read,write,sha=base.read,base.write,base.sha

def configure():
    base.D=D;base.PIN=PIN;rank.D=D;rank.R=R;rank.NAME=NAME;rank.CAP=5400
    rank.configure()

def eligible(s):
    return bool(s['structure'] and s['complete']==s['valid']==s['recomputed']==16
        and len(s['overlaps'])==4
        and all(x['host_training_envelope_overlap_seconds'] is not None
                and x['host_training_envelope_overlap_seconds']>0 for x in s['overlaps'])
        and any(x.get('strict_repeated_flip',False) for x in s['ranking']))

def prior_gate():
    assert sha(PRIOR)==PRIOR_SHA and eligible(read(PRIOR))
    return PRIOR_SHA

def repair_gate(chosen):
    failed=D.parent/'clock-rank-confirmation-20261016-v1'
    assert sha(failed/'plan.json')=='7ba784e11e2f9a821286308294cfd7acfe011ea11fa1acadc91153b13ed8c30b'
    p,c=read(failed/'plan.json'),read(failed/'closed.json')
    assert read(failed/'launch.json')['job']=='18844' and c['cleanup_verified']
    assert len(c['records'])==1 and c['records'][0]['index']==0 and c['records'][0]['returncode']==1
    assert not list(failed.glob('episode-*/score.json'))
    keys=('source_episode','source_candidate','seed','code_sha256','executed_sha256','original_config_sha256')
    assert [[x[k] for k in keys] for x in chosen]==[[x[k] for k in keys] for x in p['programs']]

def prepare(commit):
    configure();assert re.fullmatch('[a-f0-9]{40}',commit)
    prior_gate();assert sha(D/'plan.json')==PIN
    old=read(D/'plan.json')
    for n,h in old['files'].items():assert sha(D/n)==h
    runtime=base.setup();chosen=rank.select();repair_gate(chosen)
    previous=PRIOR.parent.parent/'plan.json'
    assert sha(previous)==read(PRIOR)['plan_sha256']
    old_codes={p['code_sha256'] for p in read(previous)['programs']}
    assert not old_codes.intersection(p['code_sha256'] for p in chosen),'selected source reused: stop, no replacement'
    R.mkdir(mode=0o700);(R/'configs').mkdir();(R/'bin').mkdir();(R/'programs').mkdir()
    for n in (NAME,'clock_rank_20261016.py','clock_contention_20261016.py','closed_clock_screen_20261016.py'):
        shutil.copyfile(Path(__file__).with_name(n),R/n)
    for k,p in enumerate(chosen):(R/f'programs/{k}.private.py').write_text(p.pop('action'))
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    from unittest.mock import patch
    for row in rank.schedule():
        ep=R/f"episode-{row['index']}";(ep/'work/input_cache').mkdir(parents=True)
        p=chosen[row['program']];cfg=read(D/f"configs/{p['source_episode']}.json")
        cfg=json.loads(json.dumps(cfg).replace(str(D/f"episode-{p['source_episode']}"),str(ep)))
        cfg['id']=f"clock-rank-confirm-{row['index']}";cfg['logger']['output_dir']=str(ep/'native-log')
        assert cfg['interpreter']['timeout']==300 and cfg['interpreter']['env']['PYTHONHASHSEED']==str(p['seed'])
        write(R/f"configs/{row['index']}.json",cfg)
        c=RunConfig.load_from_json(R/f"configs/{row['index']}.json");c.validate()
        assert not Path(c.task.private_dir).exists() and not c.logger.write_env_vars and not c.logger.use_wandb
        base.port_hook('100',row['program'])
        factory=build(c.interpreter,INTERPRETER_MAP,data_dir=c.task.data_dir);assert factory.factory
        with patch('dojo.core.interpreters.jupyter.jupyter_interpreter.SingularityJupyterServer') as server:
            assert factory.instance.port==base.gateway_port('100',row['program']) and factory.instance.timeout==300
            assert server.call_args.kwargs['port']==base.gateway_port('100',row['program'])
            factory.close()
    shim=f'#!{base.PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(NAME).stem} import task_runtime\ntask_runtime()\n'
    (R/'bin/singularity').write_text(shim);os.chmod(R/'bin/singularity',0o700)
    (R/'run.sbatch').write_text(f'''#!/bin/bash
#SBATCH --job-name=r14-rank-confirm
#SBATCH --partition=gpu_24h
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --hint=nomultithread
#SBATCH --time=01:30:00
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
exec srun --exclusive --ntasks=1 --cpus-per-task=4 --gres=gpu:1 {base.PY} -B {R/NAME} run
''')
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and not p.relative_to(R).parts[0].startswith('episode-')}
    write(R/'plan.json',dict(source_commit=commit,prior_summary_sha256=PRIOR_SHA,donor_plan_sha256=PIN,
        donor_files=old['files'],files=files,schedule=rank.schedule(),programs=chosen,
        task_image=str(runtime.TASK_IMAGE),task_image_sha256=old['task_image_sha256'],
        allocation_seconds=5400,gpus=1,node='gpu27',worker_seconds=380,execution_seconds=300,
        selection='First2 distinct-source chronological valid CUDA/clock programs per task from closed18807; no score/rank sorting.',
        primary='Full16; repeat the same task strict interval-separated rank reversal from18819. Mechanism only, not E2E or significance.',
        stop='Any infrastructure/isolation/cleanup or first4 solo valid-CUDA failure stops remaining. No replacements or retries.',
        preregistration_commit='333c56623a5c87cdf49cbad004e9b97812430f50',window_end_utc=WINDOW_END,
        repair_of_job=18844,repair_scope='Only resolve namespace helper from current donor; identical sources/seeds/configs/caps/gates. Old failed batch remains sealed. No further automatic repair batch.'))
    print(json.dumps(dict(status='PREPARED',root=str(R),plan_sha256=sha(R/'plan.json'),programs=chosen)))

def task_runtime():
    configure();base.setup()
    from colocation_trial_20261016 import namespace_command
    from forets_gpu_binding_20260911 import REAL_SINGULARITY
    args=sys.argv[1:]
    if args==['--version']:os.execv(REAL_SINGULARITY,[REAL_SINGULARITY,'--version'])
    ep=Path(os.environ['POLICY9B_EPISODE']);assert ep.parent==R and re.fullmatch(r'episode-(?:[0-9]|1[0-5])',ep.name)
    n=read(R/'native.json');assert n['job']==os.environ['SLURM_JOB_ID'] and n['step']==os.environ['SLURM_STEP_ID']
    from resource_gpu_identity import gpu_uuids
    assert gpu_uuids(1)==n['gpu_uuids']
    cmd,env,receipt=namespace_command(args,n['gpu_uuids'][0])
    write(ep/f'binding-{os.getpid()}.json',dict(receipt,wall=time.time()))
    os.execve(REAL_SINGULARITY,cmd,env)

def entrycheck():
    """Actual prepared shim + real imports; mock only external binary exec."""
    import ast
    import runpy
    from unittest.mock import patch
    configure();base.check()
    old=D.parent/'scheduling-pooling-20261016-v3/pooling_trial_20261015.py'
    new=D/'colocation_trial_20261016.py'
    get=lambda path:next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='namespace_command')
    assert ast.dump(get(old),include_attributes=False)==ast.dump(get(new),include_attributes=False)
    class ReachedExec(Exception):pass
    with patch.object(sys,'argv',[str(R/'bin/singularity'),'--version']),patch.object(os,'execv',side_effect=ReachedExec) as call:
        try:runpy.run_path(str(R/'bin/singularity'),run_name='__main__')
        except ReachedExec:pass
        else:raise AssertionError('prepared shim did not reach binary exec')
        assert call.call_count==1 and call.call_args.args[1][1:]==['--version']
    print(json.dumps(dict(actual_prepared_shim_imports=True,namespace_ast_identical=True,external_binary_not_executed=True)))

def main():
    a=argparse.ArgumentParser();a.add_argument('action',choices=('inspect','prepare','entrycheck','submit','run','worker'))
    a.add_argument('--commit');a.add_argument('--index',type=int);v=a.parse_args();configure()
    if v.action=='inspect':
        prior_gate();base.setup();print(json.dumps([{k:v for k,v in p.items() if k!='action'} for p in rank.select()]))
    elif v.action=='prepare':prepare(v.commit)
    elif v.action=='entrycheck':entrycheck()
    elif v.action=='submit':
        prior_gate();assert WINDOW_END-time.time()>=110*60,'insufficient remaining window'
        base.submit()
    elif v.action=='worker':return base.worker(v.index)
    else:return rank.run()

if __name__=='__main__':sys.exit(main())
