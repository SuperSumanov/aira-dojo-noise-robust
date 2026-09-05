"""Bounded pre-task startup provenance only; never inspect task execution logs."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import re
import tarfile
import time

from recover_historical_production_configs import (ARCHIVES_SHA,OLD,SOURCE,SECRET,
    canonical,digest,hash_file,load_locked,pairs_object,regular,require,safe_parts)
from recover_historical_repair_config import CANDIDATE,CANDIDATE_SHA
from recover_historical_pool_lineage import LEDGER,LEDGER_SHA

ROOT=Path('/research/d7/spc/yzyang4')
LINEAGE=ROOT/'historical-pool-lineage-e7244fb-20260906-A/pool_lineage.private.json'
LINEAGE_SHA='fe05dddcd4fe8a3f2208652ce51c9b06df9b9b8f57a5fa655d2029caddcf9981'
ANSI=re.compile(rb'\x1b\[[0-?]*[ -/]*[@-~]')
MESSAGES={'Current working directory: ':'cwd','`dojo` package source path: ':'dojo',
          '`aira_core` package source path: ':'aira_core','`mlebench` package source path: ':'mlebench',
          'Saving experiment artifacts to: ':'ignored_output','Output dir: ':'ignored_output'}

def prefix(stream):
    """No scan-ahead: the first unknown message or task-start is terminal."""
    paths={};n=0;lines=0;fingerprint=hashlib.sha256()
    for _ in range(64):
        raw=stream.readline(min(8193,65537-n))
        if not raw:return dict(status='EOF_BEFORE_BOUNDARY',bytes_read=n,lines_read=lines,paths={},prefix_sha256=fingerprint.hexdigest())
        n+=len(raw);lines+=1;fingerprint.update(raw)
        if n>65536 or len(raw)>8192 or not raw.endswith(b'\n'):status='PREFIX_CAP';break
        clean=ANSI.sub(b'',raw)
        if SECRET.search(raw) or SECRET.search(clean):status='CREDENTIAL_SHAPE_STOP';break
        try:text=clean.decode('utf-8').strip()
        except UnicodeDecodeError:status='ENCODING_STOP';break
        if not text:continue
        # Match only anchored known messages after a conventional logger prefix.
        matches=[]
        for message,key in MESSAGES.items():
            idx=text.find(message)
            if idx<0:continue
            before=text[:idx]
            if before and not (re.match(r'^\d{4}-\d\d-\d\d',before) and len(before)<=240 and before.endswith(' - ')):continue
            matches.append((key,text[idx+len(message):]))
        boundary='Instantiating the task...'
        idx=text.find(boundary)
        if idx>=0 and text[idx:]==boundary:
            before=text[:idx]
            if not before or (re.match(r'^\d{4}-\d\d-\d\d',before) and len(before)<=240 and before.endswith(' - ')):
                status='COMPLETE_PRETASK_SOURCE_RECORD' if set(paths)=={'cwd','dojo','aira_core','mlebench'} else 'BOUNDARY_WITH_INCOMPLETE_RECORD'
                break
        if len(matches)!=1:status='UNRECOGNIZED_PREFIX_STOP';break
        key,value=matches[0]
        if key=='ignored_output':continue
        value=value.strip();path=PurePosixPath(value)
        if not value or not path.is_absolute() or '..' in path.parts or any(c in value for c in ('\x00','\t','\n','\r')):
            status='INVALID_SOURCE_PATH';break
        if key in paths:status='DUPLICATE_SOURCE_FIELD';break
        paths[key]=value
    else:status='PREFIX_LINE_CAP'
    return dict(status=status,bytes_read=n,lines_read=lines,paths=paths if status=='COMPLETE_PRETASK_SOURCE_RECORD' else {},prefix_sha256=fingerprint.hexdigest())

def selected_scope(ledger,p):
    covered={t['run_id'] for m in p['manifests'] for t in m['tasks'] if t['run_id']}
    blocked_components={p['closure'][rid]['component_sha256'] for rid in ledger if rid not in covered}
    for m in p['manifests']:
        if any(t['run_id'] is None or t['step_matches_recorded_config'] is False for t in m['tasks']):
            blocked_components.update(p['closure'][t['run_id']]['component_sha256'] for t in m['tasks'] if t['run_id'])
    return {rid for rid,row in p['closure'].items() if not row['old_hold_closure_blocks_train'] and row['component_sha256'] not in blocked_components}

def log_member(path,pool_dir):
    require(isinstance(path,str) and PurePosixPath(path).is_absolute(),'log_path')
    pool=PurePosixPath(pool_dir);relative=PurePosixPath(path).relative_to(pool)
    require(len(relative.parts)==2 and relative.parts[0]=='logs','log_not_in_pool_logs')
    return '/'.join((*pool.parts[-3:],*relative.parts))

def scan(path,sha,manifests,chosen,deadline):
    st=regular(path);require(hash_file(path,deadline)==sha,'archive_pre_hash')
    names={m['manifest_member']:m for m in manifests};payloads={};seen=set()
    with tarfile.open(path,'r|*') as arc:
        for member in arc:
            require(time.monotonic()<deadline,'deadline');name='/'.join(safe_parts(member.name))
            require(name not in seen and (member.isfile() or member.isdir()),'unsafe_or_duplicate_member');seen.add(name)
            if name not in names:continue
            require(member.isfile() and 0<member.size<=4*1024**2,'manifest_cap')
            raw=arc.extractfile(member).read();require(digest(raw)==names[name]['manifest_sha256'] and not SECRET.search(raw),'manifest_drift_or_credential')
            payloads[name]=json.loads(raw,object_pairs_hook=pairs_object)
    require(set(payloads)==set(names),'missing_manifest')
    wanted=defaultdict(list)
    for name,record in names.items():
        obj=payloads[name]
        for t in record['tasks']:
            if t['run_id'] not in chosen:continue
            actual=obj['tasks'][t['config_id']]
            for a in actual['attempts']:
                if a['attempt']!=actual['attempt']:continue
                for channel in ('stdout','stderr'):
                    if not a.get(channel):continue
                    member=log_member(a[channel],record['identity']['pool_dir'])
                    wanted[member].append({'run_id':t['run_id'],'attempt':a['attempt'],'channel':channel,'snapshot_path':record['identity']['snapshot_path']})
    outputs=[];found=set()
    with tarfile.open(path,'r|*') as arc:
        for member in arc:
            require(time.monotonic()<deadline,'deadline')
            if member.name not in wanted:continue
            require(member.isfile(),'nonfile_log');found.add(member.name)
            value=prefix(arc.extractfile(member))
            outputs.append({'member':member.name,'bindings':wanted[member.name],**value})
    after=path.stat()
    require((st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'archive_changed')
    require(hash_file(path,deadline)==sha,'archive_post_hash')
    return {'archive_sha256':sha,'log_prefixes':outputs,'missing_log_members':len(set(wanted)-found)}

def build(out):
    os.umask(0o077);require(not out.exists() and out.parent.resolve(strict=True)==out.parent,'output')
    ledger=load_locked(LEDGER,LEDGER_SHA);p=load_locked(LINEAGE,LINEAGE_SHA)
    chosen=selected_scope(ledger,p);require(len(chosen)==84,'scope_changed')
    paths={row['sha256']:SOURCE.joinpath(*safe_parts(row['relative_path'])) for row in load_locked(OLD/'archive_manifest.jsonl',ARCHIVES_SHA,True) if row['status']=='ok'}
    paths[CANDIDATE_SHA]=CANDIDATE
    grouped=defaultdict(list)
    for m in p['manifests']:
        if any(t['run_id'] in chosen for t in m['tasks']):grouped[m['archive_sha256']].append(m)
    out.mkdir(mode=0o700);deadline=time.monotonic()+600
    def work(item):
        sha,manifests=item
        result=scan(paths[sha],sha,manifests,chosen,deadline)
        (out/('archive-'+sha+'.private.json')).write_bytes(canonical(result));return result
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(work,sorted(grouped.items())))
    private=canonical({'input_lineage_sha256':LINEAGE_SHA,'selected_runs':sorted(chosen),'archives':results})
    (out/'runtime_prefix.private.json').write_bytes(private)
    records=[x for a in results for x in a['log_prefixes']]
    complete=[x for x in records if x['status']=='COMPLETE_PRETASK_SOURCE_RECORD']
    complete_runs={b['run_id'] for x in complete for b in x['bindings']}
    comparison=Counter()
    for x in complete:
        for b in x['bindings']:
            snap=b['snapshot_path']
            comparison['dojo_from_recorded_snapshot']+=x['paths']['dojo'].startswith(snap+'/src/dojo/')
            comparison['mlebench_from_recorded_snapshot']+=x['paths']['mlebench'].startswith(snap+'/src/dojo/tasks/mlebench/mle-bench/')
            comparison['complete_bindings']+=1
    summary={'status':'HISTORICAL_PRETASK_SOURCE_PATH_AUDIT_NOT_VERSION_ATTESTATION','selected_runs':len(chosen),
        'archives':len(results),'log_prefixes':len(records),'prefix_status':dict(Counter(x['status'] for x in records)),
        'runs_with_complete_prefix':len(complete_runs),'snapshot_path_comparison':dict(comparison),
        'missing_log_members':sum(x['missing_log_members'] for x in results),
        'private_sha256':digest(private),'source_sha256':digest(Path(__file__).read_bytes()),
        'input_lineage_sha256':LINEAGE_SHA,'model_fits':0,'protected_cohort_reads':0,
        'last_manifest_attempt_only':True,
        'task_phase_log_reads':0,'journal_env_payload_reads':0,'installed_revision_attested':False,'training_qualified':False}
    (out/'summary.json').write_bytes(canonical(summary));print(json.dumps(summary,sort_keys=True))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);build(parser.parse_args().output)
