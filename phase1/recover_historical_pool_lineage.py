"""Recover actual archived srun-pool scheduling records; never admit training.

Config hashes alone do not identify launcher instances. Preserve actual manifest
creation/snapshot/pool/task-set identity, and add links to (never split) the old
conservative hold closure. Only exact fixed historical archive bytes are scanned.
Journal/env/log payloads, evaluator values and protected cohorts are not read.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
from pathlib import Path, PurePosixPath
import re
import time
import tarfile

from recover_historical_production_configs import (
    ARCHIVES_SHA, OLD, SOURCE, SECRET, canonical, digest, hash_file, load_locked,
    pairs_object, regular, require, safe_parts,
)
from recover_historical_repair_config import CANDIDATE, CANDIDATE_SHA

LEDGER = Path('/research/d7/spc/yzyang4/historical-source-ledger-faf04cc-20260905/source_ledger.private.json')
LEDGER_SHA = '8e48b4c6598cf8efe205fc6cba5cdd27d14621eb13fad42a7fd4180953da00d1'
ROOT_KEYS = {'version','launcher_type','allocation_id','node_list','allocations',
             'snapshot_path','python_executable','pool_dir','created_at','updated_at','tasks'}
TASK_KEYS = {'attempt','attempts','config_path','exit_code','experiment_dir','reason',
             'slurm_state','status','stderr','stdout','step_id','task_name','updated_at'}
ATTEMPT_KEYS = {'attempt','ended_at','exit_code','identity_path','job_name','slurm_state',
                'started_at','status','stderr','stdout','step_id'}
LOCAL_ROOT_KEYS = {'version','launcher_type','host','host_boot_id','snapshot_path',
                  'python_executable','pool_dir','inventory','current_inventory','inventory_history',
                  'selected_gpu_uuids','gpus_per_task','max_parallel','created_at','updated_at','tasks'}
LOCAL_TASK_KEYS = {'attempt','attempts','config_path','execution_id','exit_code','experiment_dir',
                  'gpu_uuids','gpu_indices','reason','status','stderr','stdout','task_name','updated_at'}
LOCAL_ATTEMPT_KEYS = {'attempt','ended_at','exit_code','identity_path','result_path','started_at',
                      'status','stderr','stdout','execution_id','pid','pgid','process_start_ticks',
                      'container_pid','container_pgid','container_process_start_ticks',
                      'gpu_uuids','gpu_indices','devices','hardware_description','reason','result'}


def parse_manifest(raw, member, sha, origins):
    require(not SECRET.search(raw), 'manifest_credential_shape')
    obj = json.loads(raw, object_pairs_hook=pairs_object)
    require(isinstance(obj,dict), 'manifest_not_object')
    launcher=obj.get('launcher_type')
    require(launcher in ('srun_pool','local_gpu_pool'),'launcher_type')
    local=launcher=='local_gpu_pool'
    require(set(obj) <= (LOCAL_ROOT_KEYS if local else ROOT_KEYS), 'unknown_manifest_schema')
    require(isinstance(obj.get('tasks'),dict) and 0 < len(obj['tasks']) <= 10000, 'task_count')
    parts = safe_parts(member)
    require(len(parts)==4 and parts[1]==launcher and parts[3]=='manifest.json', 'manifest_path')
    require(all(isinstance(cid,str) and cid for cid in obj['tasks']), 'task_id_type')
    key = digest('\n'.join(sorted(obj['tasks'])).encode())[:12]
    require(parts[2] == key, 'pool_task_set_hash')
    created = datetime.fromisoformat(obj['created_at'])
    require(created.date().isoformat() <= '2026-08-15', 'outside_historical_date')
    if not local:require(isinstance(obj.get('allocations'),list) and obj['allocations'], 'allocations_missing')
    for field in ('snapshot_path','python_executable','pool_dir'):
        require(isinstance(obj.get(field),str) and PurePosixPath(obj[field]).is_absolute(), 'lineage_path')
    require(obj['pool_dir'].endswith('/'+'/'.join(parts[:3])), 'pool_dir_binding')
    allocations=[]
    for a in obj.get('allocations',[]):
        require(isinstance(a,dict) and set(a) <= {'allocation_id','node_list','started_at'}, 'allocation_schema')
        allocations.append({k:a[k] for k in ('allocation_id','started_at')})
    task_records=[]
    for cid,t in sorted(obj['tasks'].items()):
        require(isinstance(t,dict) and set(t) <= (LOCAL_TASK_KEYS if local else TASK_KEYS), 'task_schema')
        require(isinstance(t.get('attempts'),list), 'attempts_missing')
        attempts=[]
        for a in t['attempts']:
            require(isinstance(a,dict) and set(a)<=(LOCAL_ATTEMPT_KEYS if local else ATTEMPT_KEYS), 'attempt_schema')
            # _finish_task embeds worker process-exit metadata under result.
            # Never inspect/project that object or its exception_summary text.
            fields=('attempt','started_at','ended_at','execution_id','identity_path','gpu_uuids') if local else ('attempt','started_at','ended_at','step_id','identity_path')
            attempts.append({k:a.get(k) for k in fields})
        candidates=[(rid,o) for rid,o in origins if rid.rsplit('__',1)[0]==cid
                    and o['config_member'].split('/')[0]==parts[0]]
        require(len(candidates)<=1, 'ambiguous_manifest_run_binding')
        record={k:t.get(k) for k in ('config_path','experiment_dir','task_name','step_id')}
        if local:record['recorded_launcher_execution_id']=t.get('execution_id')
        record.update(config_id=cid,attempts=attempts,run_id=None,step_matches_recorded_config=None)
        if candidates:
            rid,o=candidates[0]
            require(isinstance(t.get('experiment_dir'),str) and
                    t['experiment_dir'].endswith('/'+str(PurePosixPath(o['config_member']).parent)), 'experiment_dir_binding')
            record.update(run_id=rid,step_matches_recorded_config=None if local else (str(t.get('step_id'))==o['recorded_slurm_id']))
        task_records.append(record)
    # Excludes last-update/status/reason/outcome fields, which cannot select data.
    identity={k:obj[k] for k in ('created_at','snapshot_path','python_executable','pool_dir')}
    identity['launcher_type']=launcher
    identity['task_ids']=sorted(obj['tasks'])
    return dict(archive_sha256=sha,manifest_member=member,manifest_sha256=digest(raw),
                instance_sha256=digest(canonical(identity)),identity=identity,
                allocations=allocations,tasks=task_records)


def scan(path, sha, origins, deadline):
    before=regular(path)
    require(hash_file(path,deadline)==sha,'archive_pre_hash')
    seen=set(); records=[]; other=Counter(); declared=0
    with tarfile.open(path,'r|*') as arc:
        for m in arc:
            require(time.monotonic()<deadline,'deadline')
            parts=safe_parts(m.name); name='/'.join(parts)
            require(name not in seen and (m.isfile() or m.isdir()),'duplicate_or_unsafe_member')
            seen.add(name);declared+=max(0,m.size)
            require(len(seen)<=1_000_000 and declared<=256*1024**3,'archive_cap')
            if parts[-1]!='manifest.json':continue
            if len(parts)!=4 or parts[1] not in ('srun_pool','local_gpu_pool'):
                other['unopened_other_manifest_headers']+=1
                continue
            require(m.isfile() and 0<m.size<=4*1024**2,'manifest_size')
            raw=arc.extractfile(m).read(4*1024**2+1)
            require(len(raw)==m.size,'manifest_truncated')
            records.append(parse_manifest(raw,name,sha,origins))
    after=path.stat()
    require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
            (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'archive_changed')
    require(hash_file(path,deadline)==sha,'archive_post_hash')
    return dict(archive_sha256=sha,manifest_records=records,member_headers=len(seen),**other)


def closure(ledger, manifests):
    parent={rid:rid for rid in ledger}
    def find(rid):
        while parent[rid]!=rid:
            parent[rid]=parent[parent[rid]];rid=parent[rid]
        return rid
    grouped=defaultdict(set)
    for rid,r in ledger.items():grouped[('old',r['conservative_component_sha256'])].add(rid)
    for m in manifests:
        grouped[('pool',m['instance_sha256'])].update(t['run_id'] for t in m['tasks'] if t['run_id'])
    for group in grouped.values():
        if not group:continue
        anchor=min(group)
        for rid in group:parent[find(rid)]=find(anchor)
    result=defaultdict(list)
    for rid in sorted(ledger):result[find(rid)].append(rid)
    output={}
    for members in result.values():
        blocked=any(ledger[rid]['old_hold_closure_blocks_train'] for rid in members)
        sha=digest(canonical(members))
        for rid in members:output[rid]={'component_sha256':sha,'old_hold_closure_blocks_train':blocked}
    return output


def build(output):
    os.umask(0o077)
    require(not output.exists() and output.parent.resolve(strict=True)==output.parent,'output_exists_or_parent')
    ledger=load_locked(LEDGER,LEDGER_SHA);require(len(ledger)==676,'fixed_scope')
    archive_rows=load_locked(OLD/'archive_manifest.jsonl',ARCHIVES_SHA,True)
    paths=defaultdict(list)
    for row in archive_rows:
        if row['status']=='ok':paths[row['sha256']].append(SOURCE.joinpath(*safe_parts(row['relative_path'])))
    paths[CANDIDATE_SHA].append(CANDIDATE)
    by_archive=defaultdict(dict)
    for rid,r in ledger.items():
        for o in r['origins']:
            old=by_archive[o['archive_sha256']].get(o['config_member'])
            require(old is None or old==(rid,o),'origin_conflict')
            by_archive[o['archive_sha256']][o['config_member']]=(rid,o)
    require(len(by_archive)==143,'fixed_archive_scope')
    output.mkdir(mode=0o700);deadline=time.monotonic()+1500
    def work(item):
        sha,wanted=item
        try:
            r=scan(sorted(paths[sha])[0],sha,list(wanted.values()),deadline)
        except Exception as e:
            from recover_historical_production_configs import RecoveryError
            r={'archive_sha256':sha,'status':'FAILED_CLOSED',
               'reason':str(e) if isinstance(e,RecoveryError) else type(e).__name__}
        (output/('archive-'+sha+'.private.json')).write_bytes(canonical(r))
        return r
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(work,sorted(by_archive.items())))
    failures=[r for r in results if r.get('status')=='FAILED_CLOSED']
    if failures:
        fail={'status':'FAILED_CLOSED','failed_archives':len(failures),
              'reasons':dict(Counter(r['reason'] for r in failures)),'training_source_qualified':False}
        (output/'failure_summary.json').write_bytes(canonical(fail));print(json.dumps(fail));return 1
    manifests=[m for r in results for m in r['manifest_records']]
    linked=closure(ledger,manifests)
    covered={t['run_id'] for m in manifests for t in m['tasks'] if t['run_id']}
    raw=canonical({'input_ledger_sha256':LEDGER_SHA,'manifests':manifests,'closure':linked})
    (output/'pool_lineage.private.json').write_bytes(raw)
    summary=dict(status='ACTUAL_ARCHIVED_LAUNCHER_LINEAGE_NOT_TRAINING_ADMISSION',
        input_ledger_sha256=LEDGER_SHA,lineage_sha256=digest(raw),fixed_runs=len(ledger),
        archives_scanned=len(results),manifest_records=len(manifests),
        unique_manifest_hashes=len({m['manifest_sha256'] for m in manifests}),
        recorded_launcher_instances=len({m['instance_sha256'] for m in manifests}),
        manifest_launcher_types=dict(Counter(m['identity']['launcher_type'] for m in manifests)),
        local_launcher_execution_id_records=sum(bool(t.get('recorded_launcher_execution_id')) for m in manifests for t in m['tasks'] if t['run_id']),
        historical_runs_linked=len(covered),historical_runs_without_launcher_manifest=len(ledger)-len(covered),
        unmatched_task_records=sum(t['run_id'] is None for m in manifests for t in m['tasks']),
        config_slurm_step_matches=sum(t['step_matches_recorded_config'] is True for m in manifests for t in m['tasks']),
        config_slurm_step_nonmatches=sum(t['step_matches_recorded_config'] is False for m in manifests for t in m['tasks']),
        snapshots_recorded=len({m['identity']['snapshot_path'] for m in manifests}),
        conservative_components=len({v['component_sha256'] for v in linked.values()}),
        blocked_runs=sum(v['old_hold_closure_blocks_train'] for v in linked.values()),
        newly_blocked_runs=sum(v['old_hold_closure_blocks_train'] and not ledger[rid]['old_hold_closure_blocks_train'] for rid,v in linked.items()),
        other_manifest_headers_not_parsed=sum(r.get('unopened_other_manifest_headers',0) for r in results),
        recorded_instance_is_complete_experiment_attestation=False,
        runtime_evaluator_or_clean_snapshot_attested=False,training_source_qualified=False,
        journal_env_log_payload_reads=0,protected_cohort_reads=0,cards_pairs_built=False,
        source_sha256=digest(Path(__file__).read_bytes()))
    (output/'summary.json').write_bytes(canonical(summary));print(json.dumps(summary,sort_keys=True));return 0


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    raise SystemExit(build(p.parse_args().output))
