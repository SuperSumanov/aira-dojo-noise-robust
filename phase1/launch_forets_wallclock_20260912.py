"""Single fresh dispatch after bounded cutoff integration and route checks."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def write(path, value):
    with path.open('x') as stream:
        json.dump(value,stream,sort_keys=True,indent=2,allow_nan=False)
        stream.flush();os.fsync(stream.fileno())


def checked(root):
    root=root.resolve(strict=True)
    if root.parent!=Path('/research/d7/spc/yzyang4') or not root.name.startswith('forets-wallclock-20260912-'):
        raise ValueError('explicit new package only')
    build=json.loads((root/'build.json').read_bytes())
    if hashlib.sha256((root/'prepared.json').read_bytes()).hexdigest()!=build['prepared_sha256']:
        raise ValueError('preparation hash')
    check=json.loads((root/'integration-check.json').read_bytes())
    if check['status']!='PASSED_CPU_INTEGRATION_NOT_GPU_ACCEPTANCE' or check['source_tree']!=build['source_tree']:
        raise ValueError('production hook integration missing')
    sys.path[:0]=[str(root/'code'),str(root/'source/src')]
    from forets_native_run_20260911 import static_ready
    static_ready(root/'code',1)
    os.environ['SLURM_CONF']='/opt1/slurm/gpu-slurm.conf'
    return root,build


def route(root):
    root,build=checked(root)
    if not (os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY')):
        raise RuntimeError('source remote env_setup before public catalog/route access')
    from forets_context_judge_20260912 import checked_catalog
    import requests
    response=requests.get('https://openrouter.ai/api/v1/models/qwen/qwen3-coder-plus/endpoints',timeout=(10,30),allow_redirects=False)
    response.raise_for_status();write(root/'block-1.plus-catalog.json',checked_catalog(response.json()))
    result=subprocess.run([sys.executable,'-B',str(root/'code/forets_native_run_20260911.py'),'route','--block','1'],
        capture_output=True,text=True,timeout=350)
    with (root/'route-command.private.log').open('x') as stream:stream.write(result.stdout+'\n'+result.stderr)
    print(json.dumps(dict(route_exit_code=result.returncode,route_receipt=(root/'block-1.route.json').is_file())))
    return result.returncode


def submit(root):
    root,build=checked(root)
    from forets_stage_gate import validate_route_receipt
    from forets_paid_budget_20260911 import snapshot
    validate_route_receipt(root/'block-1.route.json',root/'source')
    state=snapshot(root/'paid.sqlite')
    if state['stopped'] or state['unresolved']!=2 or state['authorization_sha256']!=build['authorization_sha256']:
        raise ValueError('budget state changed')
    prepared=json.loads((root/'prepared.json').read_bytes())
    if len(prepared['run_configs'])!=8 or prepared['nominal_gpu_hours']!=3:
        raise ValueError('matrix or allocation changed')
    check=dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),configuration_and_seeds=8,
        matched_arm_configs=4,typed_configuration_verified=True,production_hook_integration=True,
        selection_only_treatment=True,original_image_and_gpu28=True,training_or_new_checkpoint=False,
        protected_cohort_read=False,automatic_retry=False,complete_matrix_readout=True,
        no_missing_to_zero=True,nominal_gpu_hours=3,search_cutoff_seconds=600,per_program_seconds=300,
        api_request_admission_margin_seconds=135,physical_cleanup_cost_must_be_reported=True,
        prior_unresolved_preserved=2,billing={k:v for k,v in state.items() if k!='scopes'},
        launcher_sha256=hashlib.sha256((root/'launchers/forets_wallclock.sbatch').read_bytes()).hexdigest(),
        submission_tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        prepared_sha256=build['prepared_sha256'],source_tree=build['source_tree'],controller_commit=build['commit'])
    write(root/'preflight.json',check)
    write(root/'submit-intent.json',dict(utc=check['utc'],launcher_sha256=check['launcher_sha256'],
        note='Exclusive intent; an uncertain scheduler response must not be retried.'))
    result=subprocess.run(['sbatch','--parsable','--output='+str(root/'slurm-%j.out'),
        '--error='+str(root/'slurm-%j.err'),str(root/'launchers/forets_wallclock.sbatch')],
        capture_output=True,text=True,timeout=25)
    with (root/'submit-response.private.log').open('x') as stream:stream.write(result.stdout+'\n'+result.stderr)
    job=result.stdout.strip().split(';')[0]
    if result.returncode or not re.fullmatch('[0-9]+',job): raise RuntimeError('scheduler response not confirmed; inspect intent before any further action')
    record=dict(job=job,utc=dt.datetime.now(dt.timezone.utc).isoformat(),package=str(root),source_tree=build['source_tree'],
        controller_commit=build['commit'],runs=8,nominal_gpu_hours=3,readiness='submitted_not_running')
    write(root/'launch.json',record);print(json.dumps(record));return 0


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('route','submit'));parser.add_argument('root',type=Path)
    args=parser.parse_args();os.umask(0o077);raise SystemExit(globals()[args.mode](args.root))
