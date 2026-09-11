"""Submit once, observe metadata, then close all four development runs together."""
import argparse
from collections import Counter
import csv
import datetime as dt
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path('/research/d7/spc/yzyang4/forets-env-20260912-edcpizid')
PREPARED = '1e0f29be3f48fb376a2ce4a2740da583d5c39fcdefa9c5f6d2bceac7b100eda9'
PRIOR_NANO = 318775548
os.environ['SLURM_CONF'] = '/opt1/slurm/gpu-slurm.conf'
sys.path.insert(0, str(ROOT/'code'))


def read(path): return json.loads(path.read_text())
def write(path, obj):
    with path.open('x') as f: json.dump(obj, f, indent=2, allow_nan=False); f.write('\n')
def command(args):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=25).stdout


def submit():
    from forets_native_run_20260911 import static_ready
    from forets_stage_gate import validate_route_receipt
    static_ready(ROOT/'code', 1); validate_route_receipt(ROOT/'block-1.route.json', ROOT/'source')
    if 'forets-env-s10' in command(['squeue','-u','yzyang4','-h','-o','%j']):
        raise ValueError('matching job already present')
    if (ROOT/'submission.json').exists() or (ROOT/'submit-intent.json').exists():
        raise ValueError('submission already attempted, no automatic duplicate')
    script = ROOT/'launchers/forets_environment_20260912.sbatch'
    args = ['sbatch','--parsable','--output='+str(ROOT/'allocation-%j.log'),str(script)]
    write(ROOT/'submit-intent.json', dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        argv=args, script_sha256=hashlib.sha256(script.read_bytes()).hexdigest(), maximum_new_gpu_hours=10))
    raw = command(args).strip()
    if not re.fullmatch(r'\d+(?:;[A-Za-z0-9_.-]+)?', raw): raise ValueError('ambiguous submission, inspect before retry')
    receipt = dict(job_id=raw.split(';')[0], submitted_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                   run_count=4, seed=10, node_requested='gpu28')
    write(ROOT/'submission.json', receipt); print(json.dumps(receipt))


def billing():
    from forets_paid_budget_20260911 import snapshot
    state = snapshot(ROOT/'paid.sqlite')
    old = [r for r in state['scopes'] if r['scope']=='closed_predecessor']
    if len(old)!=1 or old[0]['calls']!=1 or old[0]['settled_usd']!=PRIOR_NANO/1e9:
        raise ValueError('predecessor carryover differs')
    return dict(new_api_calls=state['calls']-1, cumulative_api_calls=state['calls']-1+124,
        new_settled_usd=str(Decimal(str(state['settled_usd']))-Decimal(PRIOR_NANO)/10**9),
        cumulative_settled_usd=state['settled_usd'], unresolved_api_calls=state['unresolved'],
        stopped=state['stopped'])


def status(emit=True):
    job = read(ROOT/'submission.json')['job_id']
    scheduling = command(['sacct','-X','-j',job,'-nP','--format=JobIDRaw,State,NodeList,ElapsedRaw,ExitCode']).strip()
    start_path = ROOT/'block-1.runtime/started.json'
    states = []
    if start_path.exists():
        start = read(start_path); pool = read(ROOT/start['pool_manifest'])
        states = [dict(run_id=name, status=row['status'], attempt=row['attempt']) for name,row in pool['tasks'].items()]
    result = dict(observed_utc=dt.datetime.now(dt.timezone.utc).isoformat(), job=scheduling, runs=states, billing=billing())
    if emit: print(json.dumps(result),flush=True)
    return result


def watch():
    """In-session observer, not a scheduled task; no resubmit or paid requests."""
    previous=None
    while True:
        result=status(emit=False)
        key=([(r['run_id'],r['status'],r['attempt']) for r in result['runs']],
             result['job'].split('|')[1],result['billing']['stopped'])
        if key!=previous:
            print(json.dumps(result),flush=True);previous=key
        state=result['job'].split('|')[1].split(' ',1)[0].rstrip('+')
        if state in ('COMPLETED','FAILED','CANCELLED','TIMEOUT','NODE_FAIL','OUT_OF_MEMORY','PREEMPTED','BOOT_FAIL'):
            if (ROOT/'diagnostics.json').exists():
                print('CLOSEOUT_ALREADY_EXISTS',flush=True)
            else: closeout()
            return
        time.sleep(45)


def closeout():
    from forets_block_collect_20260911 import collect_metadata
    from forets_block_readout_20260911 import summarize, write_report
    from forets_paid_measurements_20260912 import read_batch
    from forets_paid_failure_verify_20260912 import SECRET, classify
    from forets_paid_budget_20260911 import snapshot
    raw = (ROOT/'prepared.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PREPARED: raise ValueError('preparation drift')
    prepared=json.loads(raw)
    manifest=collect_metadata(ROOT,prepared)  # independent allocation closure first
    result=summarize(manifest,prepared,ROOT)
    ledger_before=snapshot(ROOT/'paid.sqlite')
    scopes={row['scope']:row for row in ledger_before['scopes']}
    costs=billing(); totals=Counter(); diagnostics=[]
    for run, final in zip(manifest['runs'],result['runs']):
        base=ROOT/run['run_dir']; journal=base/'checkpoint/journal.jsonl'
        nodes=[]
        if journal.exists():
            safe=SECRET.sub('[REDACTED]',journal.read_text())
            nodes=[json.loads(line) for line in safe.splitlines() if line.strip()][1:]
        failures=Counter(classify('\n'.join(node['_term_out'])) for node in nodes if node['exit_code']!=0)
        zero=sum(node['exit_code']==0 for node in nodes)
        ledgers=base/'checkpoint/forets-candidates-private'; batches=[]
        if ledgers.exists():
            for path in sorted(ledgers.iterdir()):
                if path.name.endswith('.lock'): raise ValueError('unfinished batch lock remains')
                match=re.fullmatch(r'batch-([0-5])\.sqlite',path.name)
                if not match: raise ValueError('unexpected candidate artifact')
                batches.append(read_batch(path,task=run['task'],arm=run['arm'],step=int(match[1])))
        calls=sum(b['total_task_calls'] for b in batches)
        if len(nodes)!=calls or zero!=sum(b['interpreter_exit_zero_calls'] for b in batches):
            raise ValueError('independent journal/task-call disagreement')
        if final['comparable_final']:
            event=json.loads((base/'json/eval.jsonl').read_text())['data']
            selected=[n for n in nodes if n['id']==event['selected_node_id']]
            if len(selected)!=1 or selected[0]['exit_code']!=0 or selected[0]['is_buggy'] is not False:
                raise ValueError('final selection is not a successful executed node')
        charge=scopes.get(run['run_id'], {'calls':0,'settled_usd':0,'held_usd':0,'unresolved':0})
        diagnostics.append(dict(run_id=run['run_id'],task=run['task'],arm=run['arm'],seed=10,
            source_tree=manifest['source_tree'],controller_commit=manifest['controller_commit'],
            execution_timeout_seconds=300,step_limit=6,worker_wall_cap_seconds=3540,
            api_calls=charge['calls'],settled_api_cost_usd=charge['settled_usd'],
            unresolved_api_calls=charge['unresolved'],accounted_api_liability_usd=charge['held_usd'],
            total_api_cost_usd=charge['settled_usd'] if charge['unresolved']==0 else None,
            task_calls=calls, exit_zero_calls=zero, buggy_nodes=sum(n['is_buggy'] is True for n in nodes),
            generated_candidates=sum(b['generated_candidates'] for b in batches), failure_categories=dict(failures),
            comparable_final=final['comparable_final']))
        totals.update(failures)
    if snapshot(ROOT/'paid.sqlite')!=ledger_before:
        raise ValueError('API ledger changed during closed readout')
    write(ROOT/'runtime-manifest.json',manifest)
    write_report(result,ROOT/'final-readout')
    report=dict(observed_utc=dt.datetime.now(dt.timezone.utc).isoformat(), billing=costs,
        valid_final_solutions=sum(r['comparable_final'] for r in result['runs']),
        comparable_pairs=result['comparable_pairs'], total_task_calls=sum(r['task_calls'] for r in diagnostics),
        exit_zero_calls=sum(r['exit_zero_calls'] for r in diagnostics), failure_categories=dict(totals),
        allocation_gpu_hours=result['total_allocation_gpu_hours'],runs=diagnostics,
        limitations=['Single-seed development viability, not replicated critic benefit.',
                    'Old eight failed runs are not repaired or retrospectively rescored.'])
    write(ROOT/'diagnostics.json',report)
    with (ROOT/'runs_cost_work.csv').open('x', newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(diagnostics[0]))
        writer.writeheader();writer.writerows(diagnostics)
    print(json.dumps({k:v for k,v in report.items() if k!='runs'}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('submit','status','closeout','watch'));a=p.parse_args()
    {'submit':submit,'status':status,'closeout':closeout,'watch':watch}[a.mode]()
