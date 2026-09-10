"""Collect both terminal development blocks without opening any score file.

Reads only explicit started/finished/pool/config records and fresh sacct metadata.
Missing start records are NOT silently turned into unstarted blocks. This is not
the score reader, and it cannot submit, retry, cancel, or choose another seed.
"""
import argparse
import datetime as dt
import hashlib
from pathlib import Path
import re
import subprocess

from forets_block_controller_20260911 import PREPARED_SHA, TREE, block_spec
from forets_block_readout_20260911 import ROOT, ROLE, TERMINAL, _inside, _load, validate_manifest
from forets_block_runtime_20260911 import write_once


def terminal_record(text, start):
    """Parse exactly one independent allocation record, never sum child steps."""
    rows=[line.split('|') for line in text.splitlines() if line.strip()]
    matches=[r for r in rows if r[0]==start['allocation_id']]
    if len(matches)!=1 or len(matches[0])!=6: raise ValueError('ambiguous allocation accounting')
    job,state,node,elapsed,tres,owner=matches[0]
    state=state.split(' ',1)[0].rstrip('+')
    entries=dict(item.split('=',1) for item in tres.split(',') if '=' in item)
    if (state not in TERMINAL or node!=start['node'] or owner!='yzyang4'
            or entries.get('gres/gpu')!='2' or not elapsed.isdigit()):
        raise ValueError('allocation not terminal or wrong owner/hardware')
    return dict(block=start['block'],allocation_id=job,node=node,state=state,
        elapsed_seconds=int(elapsed),allocated_gpus=2,service_startup_seconds=None,
        observed_utc=dt.datetime.now(dt.timezone.utc).isoformat())


def query_terminal(start):
    job=start['allocation_id']
    if not re.fullmatch(r'[0-9]+',job): raise ValueError('invalid allocation identity')
    result=subprocess.run(['sacct','-X','-j',job,'--noheader','--parsable2',
        '--format=JobIDRaw,State%32,NodeList%64,ElapsedRaw,AllocTRES%256,User%64'],
        capture_output=True,text=True,check=False,timeout=15)
    if result.returncode: raise RuntimeError('allocation accounting unavailable')
    return terminal_record(result.stdout,start)


def collect_metadata(root,prepared,*,query=query_terminal):
    """Produce a bound manifest; complete all metadata checks before any readout."""
    root=Path(root).resolve(strict=True)
    starts,blocks,pools,hashes=[],[],[],{}
    for block in (1,2):
        spec=block_spec(prepared,block)
        start_path=_inside(root,f'block-{block}.runtime/started.json')
        start=_load(start_path)
        if (start.get('block')!=block or start.get('node') not in ('gpu27','gpu28')
                or not re.fullmatch(r'[0-9a-f]{40}',str(start.get('controller_commit','')))):
            raise ValueError('wrong block start binding')
        key=hashlib.sha256('\n'.join(sorted(spec.run_ids)).encode()).hexdigest()[:12]
        if start.get('pool_manifest')!=f'runs/srun_pool/{key}/manifest.json':
            raise ValueError('wrong fixed pool path')
        # Observe allocation closure BEFORE reading its last mutable ledger.
        # Reading first could preserve stale RUNNING rows across the query.
        terminal=query(start)
        pool_path=_inside(root,start['pool_manifest'])
        pool=_load(pool_path)
        if (pool.get('allocation_id')!=start['allocation_id'] or pool.get('node_list')!=start['node']
                or set(pool['tasks'])!=set(spec.run_ids)
                or pool.get('snapshot_path')!=str(root/'source')
                or [r['allocation_id'] for r in pool.get('allocations',[])]!=[start['allocation_id']]):
            raise ValueError('pool/allocation drift or replay')
        finish_path=_inside(root,f'block-{block}.runtime/finished.json')
        finish=_load(finish_path) if finish_path.exists() else {}
        terminal['service_startup_seconds']=finish.get('service_startup_seconds')
        for path in (start_path,pool_path,finish_path):
            if path.is_file(): hashes[str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
        starts.append(start);blocks.append(terminal);pools.append(pool)
    if starts[0]['controller_commit']!=starts[1]['controller_commit']:
        raise ValueError('blocks used different controller code')
    manifest=dict(schema=1,role=ROLE,source_tree=TREE,prepared_sha256=PREPARED_SHA,
        controller_commit=starts[0]['controller_commit'],blocks=blocks,runs=[],
        evidence_sha256=hashes,scope='metadata_only_no_score_reads')
    for original in prepared['run_configs']:
        run_id=original['run_id'];block=original['block']
        task=pools[block-1]['tasks'][run_id]
        attempt=task.get('attempt')
        if type(attempt) is not int or attempt not in (0,1): raise ValueError('unexpected repeat/attempt')
        if task.get('experiment_dir')!=str(root/'runs'/run_id): raise ValueError('run directory drift')
        row={k:original[k] for k in ('run_id','block','task','seed','arm')}
        row.update(run_dir='runs/'+run_id,prepared_config_sha256=original['config_sha256'],
            runtime_config_path=None,runtime_config_sha256=None,process_summary=None)
        if attempt==0:
            if task['status']!='pending' or task['attempts']: raise ValueError('ambiguous unstarted slot')
            row['runtime_status']='not_started'
        else:
            attempts=task['attempts']
            if len(attempts)!=1 or attempts[0]['attempt']!=1: raise ValueError('attempt ledger changed')
            if task['status'] not in ('launching','running','completed','failed','cancelled'):
                raise ValueError('unknown attempted run status')
            # Allocation closure proves the step cannot still run. A stale
            # launching/running ledger is interrupted failure, never success.
            row['runtime_status']=task['status'] if task['status'] in ('completed','cancelled') else 'failed'
            cfg=Path(task['config_path']);identity=Path(attempts[0]['identity_path'])
            pool_dir=_inside(root,starts[block-1]['pool_manifest']).parent
            stem=re.sub(r'[^A-Za-z0-9_.-]+','-',run_id).strip('-.')[:64]+'-'+hashlib.sha256(run_id.encode()).hexdigest()[:10]
            if cfg!=pool_dir/'configs'/f'{stem}.json' or identity!=pool_dir/'identities'/f'{stem}.attempt-1.json':
                raise ValueError('runtime paths not from fixed pool')
            rel=str(cfg.relative_to(root)).replace('\\','/')
            cfg=_inside(root,rel)
            row.update(runtime_config_path=rel,runtime_config_sha256=hashlib.sha256(cfg.read_bytes()).hexdigest(),
                process_summary=str((identity.with_suffix('.bounded')/'execution/summary.json').relative_to(root)).replace('\\','/'))
        manifest['runs'].append(row)
    validate_manifest(manifest,prepared,root)  # metadata/path/config only
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True,help='New relative manifest file in the fixed package')
    a=p.parse_args()
    root=ROOT.resolve(strict=True)
    prepared=_load(root/'prepared.json',digest=PREPARED_SHA)
    result=collect_metadata(root,prepared)
    write_once(_inside(root,a.output),result)


if __name__=='__main__': main()
