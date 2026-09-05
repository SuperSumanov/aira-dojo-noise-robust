"""One outcome-blind, no-fit foreground WL coverage update; exact old runner."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

B=Path('/research/d7/spc/yzyang4')
CONTROL=B/'worktrees/alias_monitor_bc362df_v2_nosmudge'
COMMIT='bc362dfe95287f199f6bc4a1dc8f781f3b1b6ee0'
SCORER=B/'worktrees/codex_wl_escrow_031edb3'
SCORER_COMMIT='031edb34400781ca026bc9833ac7f850312ffb1c'
SCRIPT=CONTROL/'phase1/scripts/monitor_wl_snapshot_chain_20260826.sh'
SCRIPT_SHA='4cec4fd7cb2382f6e7f4e071b31212cfa45901de9dcfcc7730f18cad4e619daa'
PUBLIC_PATH='phase1/scripts/run_wl_catchup_673_20260906.py'
WL=B/'wl-graph-escrow-snapshot-chain/monitor_3932b38_v1'
OUTPUT=B/'wl-graph-escrow-snapshot-chain'
STATE=B/'prospective_decision_v1'
ACTION=B/'wl-catchup-session-673-20260906'
LATEST='cdae57a622cfa8e83b40e93f60dbd90045b4670c4e9050bf552ef689745a25f2'
PRIOR='e9e12c639fdeb54f3c18ef9d55841db60332baedfe8149774006e458ab8e8a6d'
FROZEN={
 'wl-graph-escrow-snapshot-chain/monitor_3932b38_v1/state.tsv':'98155113b3921d7126d5fe5bd0b26715167b3a96c42cd9de41d74cb485a5d3c8',
 'wl-graph-escrow-snapshot-chain/monitor_3932b38_v1/monitor.log':'3d5a84a7cecef55f513789d02e2fb0d1744a30303a6a36cf7d04bfab5ff69f0e',
 'transition-future-escrow/monitor_7458f09_snapshot_chain_v1/state.tsv':'ac66b2deb9054b05e9fab803587d1ee38478f88cbadc86aebfa9f4a9f7ebad4e',
 'transition-future-escrow/monitor_7458f09_snapshot_chain_v1/monitor.log':'a23e382f0a8ccb2684dbd29bed68ae0ea1d61c7a6a1727f03195033697f9ec43',
 'prediction-receipt-common-support/monitor_9f2cbe9_v1/state.tsv':'6a1ac64a49221f3879a165e608b3cb8298aab221f3ff1bcd20764c1fe47d38bc',
 'prediction-receipt-common-support/monitor_9f2cbe9_v1/monitor.log':'72f4fb13605a2aa6cc092f625799e671f140b39a79313a03f1f1847f70d84a22'}
SECRET=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')


def require(ok,why):
    if not ok:raise RuntimeError(why)


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()


def command(cmd):
    p=subprocess.run(cmd,capture_output=True,timeout=90)
    require(p.returncode==0 and not SECRET.search(p.stdout+p.stderr),'metadata_command_failed_or_withheld')
    return p.stdout


def record(name,obj):
    with (ACTION/name).open('x') as f:json.dump(obj,f,sort_keys=True,indent=2)


def inventory_ok(inventory):
    expected={'all_physical_runs':699,'eligible_runs':673,'eligible_endpoints':18696,
              'eligible_structural_pairs':4275,'eligible_tasks':57}
    require(all(type(inventory.get(k)) is int and inventory[k]==v for k,v in expected.items()),'inventory_drift')


def preflight(public_commit):
    require(re.fullmatch('[0-9a-f]{40}',public_commit),'public_commit')
    require(hashlib.sha256(command(['git','-C',str(B/'aira-dojo'),'show',public_commit+':'+PUBLIC_PATH])).hexdigest()==sha(Path(__file__)),'public_code_drift')
    for repo,commit in ((CONTROL,COMMIT),(SCORER,SCORER_COMMIT)):
        require(repo.resolve()==repo,'unsafe_source_root')
        require(command(['git','-C',str(repo),'rev-parse','HEAD']).decode().strip()==commit,'head_drift')
        require(not command(['git','-C',str(repo),'status','--porcelain','--untracked-files=all']).strip(),'dirty_source')
    require(sha(SCRIPT)==SCRIPT_SHA,'runner_drift')
    require((STATE/'LATEST').read_text().strip()==LATEST,'latest_drift')
    s=STATE/'snapshots'/LATEST/'accumulator/summary.json'
    require(sha(s)=='b70da317b36949cba2db91edcfc5ce1af85f19fa0378a63d0b5587a4989b7d56','snapshot_summary_drift')
    inventory_ok(json.loads(s.read_bytes())['inventory'])
    for relative,h in FROZEN.items():require(sha(B/relative)==h,'state_or_log_drift')
    for p in WL.glob('*.pid'):
        v=p.read_text().strip();require(re.fullmatch('[0-9]+',v),'pid_schema')
        require(not (Path('/proc')/v).exists(),'prior_wl_pid_present')
    with (WL/'monitor.lock').open('r') as f:
        fcntl.flock(f,fcntl.LOCK_SH|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN)
    src=B/'external/senior_data/mle'
    require(sum(p.is_file() for p in src.glob('*/*.tar.gz'))==331,'archive_inventory_drift')
    require(not any(src.rglob('*.config_v2.jsonl')),'new_sidecar_stop_before_content')
    require(not list(OUTPUT.glob('*_'+LATEST[:12])),'prior_attempt_for_current_snapshot')
    require(ACTION.parent.resolve()==ACTION.parent and not ACTION.exists(),'action_exists_or_alias')


def run(public_commit):
    preflight(public_commit);ACTION.mkdir(mode=0o700)
    record('intent.json',{'public_commit':public_commit,'wrapper_sha256':sha(Path(__file__)),
        'prior':PRIOR,'latest':LATEST,'wall_cap_seconds':7200,'gpu_api_model_fit':0,'fixed_inputs':FROZEN})
    p=ACTION/'own-storage-check.bin';size=64*1024*1024
    with p.open('xb') as f:
        os.posix_fallocate(f.fileno(),0,size);os.fsync(f.fileno());st=os.fstat(f.fileno())
        require(st.st_size==size and st.st_blocks*512>=size,'storage_reservation')
    require(p.stat().st_ino==st.st_ino and p.stat().st_nlink==1,'storage_inode');p.unlink()
    record('storage.json',{'actual_allocated_bytes':st.st_blocks*512,'own_file_removed':True})
    env=dict(os.environ,WL_CHAIN_STATE_ROOT=str(STATE),WL_CHAIN_OUTPUT_ROOT=str(OUTPUT),
        WL_CHAIN_MONITOR_ROOT=str(WL),WL_CHAIN_MAX_POLLS='1',WL_CHAIN_POLL_SECONDS='300',WL_CHAIN_MINIMUM_NEW_RUNS='12',
        CUDA_VISIBLE_DEVICES='',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1')
    args=['bash',str(SCRIPT),str(CONTROL),COMMIT];record('command.json',args)
    started=time.monotonic()
    with (ACTION/'stdout.private').open('xb') as out,(ACTION/'stderr.private').open('xb') as err:
        proc=subprocess.Popen(args,env=env,stdout=out,stderr=err,start_new_session=True)
        record('process.json',{'pid':proc.pid,'process_group':proc.pid,'started_epoch':time.time()})
        print(json.dumps({'status':'WL_FROZEN_CATCHUP_RUNNING','pid':proc.pid,'prior_runs':517,'target_runs':673,'model_fits':0}),flush=True)
        try:rc=proc.wait(timeout=7200)
        except BaseException:
            os.killpg(proc.pid,signal.SIGTERM)
            try:proc.wait(timeout=20)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=10)
            record('failure.json',{'reason':'timeout_or_parent_interrupt','returncode':proc.returncode})
            raise
    elapsed=time.monotonic()-started
    record('terminal.json',{'returncode':rc,'elapsed_seconds':elapsed})
    require(rc==0,'wl_runner_failed_no_retry')
    for n in ('stdout.private','stderr.private'):
        require((ACTION/n).stat().st_size<1_000_000 and not SECRET.search((ACTION/n).read_bytes()),'private_stream_withheld')
    for relative,h in FROZEN.items():
        if not relative.startswith('wl-graph-'):require(sha(B/relative)==h,'unrelated_monitor_changed')
    parts=(WL/'state.tsv').read_text().strip().split('\t')
    require(len(parts)==4 and parts[0]==LATEST and parts[3]=='673','wl_not_promoted')
    artifact=Path(parts[1]);require(artifact.parent.parent==OUTPUT and artifact.name=='artifact','artifact_root')
    root=artifact.parent
    require((root/'COMPLETE').is_file() and not (root/'FAILURE').exists(),'formal_not_complete')
    require(sha(artifact/'summary.json')==parts[2],'promoted_hash')
    receipt=json.loads((root/'monitor_receipt.json').read_bytes())
    require(receipt['snapshot_sha256']==LATEST and receipt['selected_runs']==673
        and receipt['added_runs']==156 and receipt['removed_runs']==0 and receipt['outcomes_read'] is False
        and receipt['effect_metrics_computed']==[],'safe_receipt_mismatch')
    record('safe_receipt.json',{'status':'WL_COVERAGE_PROMOTED_PENDING_INDEPENDENT_POSTCHECK',
        'prior_runs':517,'current_runs':673,'added_runs':156,'elapsed_seconds':elapsed,
        'artifact':str(root),'manifest_sha256':sha(root/'SHA256SUMS'),'outcomes_read':False,
        'prediction_values_emitted':False,'model_fits':0,'wrapper_sha256':sha(Path(__file__))})
    print(json.dumps({'status':'WL_COVERAGE_PROMOTED_PENDING_INDEPENDENT_POSTCHECK','eligible_runs':673,'added_runs':156,'elapsed_seconds':elapsed}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--commit',required=True);a=p.parse_args();os.umask(0o077)
    try:run(a.commit)
    except Exception as exc:
        print(json.dumps({'status':'WL_CATCHUP_FAILED_CLOSED','reason':str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__}),flush=True)
        raise SystemExit(1)
