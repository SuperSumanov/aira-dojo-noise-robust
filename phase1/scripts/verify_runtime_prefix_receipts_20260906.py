"""Independent stored-receipt scope/count checks, without rereading raw logs."""
import argparse,csv,datetime as dt,hashlib,io,json,os
from collections import Counter,defaultdict
from pathlib import Path

def h(raw):return hashlib.sha256(raw).hexdigest()
def c(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()+b'\n'
def locked(path,sha):
 raw=path.read_bytes();assert h(raw)==sha;return json.loads(raw)

def verify(control):
 os.umask(0o077);root=Path('/research/d7/spc/yzyang4')
 a=root/'historical-runtime-prefix-79164e0-20260906-A';b=root/'historical-runtime-prefix-79164e0-20260906-B'
 ledger=locked(root/'historical-source-ledger-faf04cc-20260905/source_ledger.private.json','8e48b4c6598cf8efe205fc6cba5cdd27d14621eb13fad42a7fd4180953da00d1')
 lineage=locked(root/'historical-pool-lineage-e7244fb-20260906-A/pool_lineage.private.json','fe05dddcd4fe8a3f2208652ce51c9b06df9b9b8f57a5fa655d2029caddcf9981')
 raw=(a/'runtime_prefix.private.json').read_bytes();assert raw==(b/'runtime_prefix.private.json').read_bytes()
 p=json.loads(raw);sa=(a/'summary.json').read_bytes();assert sa==(b/'summary.json').read_bytes();summary=json.loads(sa)
 assert h(raw)==summary['private_sha256']
 group_members=defaultdict(set)
 for rid,r in lineage['closure'].items():group_members[r['component_sha256']].add(rid)
 covered={t['run_id'] for m in lineage['manifests'] for t in m['tasks'] if t['run_id']}
 rejected=set()
 for gid,members in group_members.items():
  if not members<=covered or any(lineage['closure'][rid]['old_hold_closure_blocks_train'] for rid in members):rejected.add(gid)
 for m in lineage['manifests']:
  if any(t['run_id'] is None or t['step_matches_recorded_config'] is False for t in m['tasks']):
   rejected.update(lineage['closure'][t['run_id']]['component_sha256'] for t in m['tasks'] if t['run_id'])
 chosen={rid for gid,members in group_members.items() if gid not in rejected for rid in members}
 assert set(p['selected_runs'])==chosen and len(chosen)==84
 counts=Counter();complete_runs=set();comparison=Counter();observed_runs=set();max_read=0
 for archive in p['archives']:
  name='archive-'+archive['archive_sha256']+'.private.json'
  assert (a/name).read_bytes()==(b/name).read_bytes()==c(archive)
  for record in archive['log_prefixes']:
   counts[record['status']]+=1;assert 0<=record['bytes_read']<=65537 and 0<=record['lines_read']<=64
   max_read=max(max_read,record['bytes_read'])
   for binding in record['bindings']:
    rid=binding['run_id'];assert rid in chosen;observed_runs.add(rid)
    matches=[(m,t) for m in lineage['manifests'] if m['archive_sha256']==archive['archive_sha256'] for t in m['tasks'] if t['run_id']==rid]
    assert len(matches)==1;m,t=matches[0]
    assert binding['snapshot_path']==m['identity']['snapshot_path']
    assert binding['attempt']==t['attempts'][-1]['attempt']
    assert binding['channel'] in ('stdout','stderr')
    if record['status']=='COMPLETE_PRETASK_SOURCE_RECORD':
     assert set(record['paths'])=={'cwd','dojo','aira_core','mlebench'};complete_runs.add(rid)
     snap=binding['snapshot_path']
     comparison['dojo_from_recorded_snapshot']+=record['paths']['dojo'].startswith(snap+'/src/dojo/')
     comparison['mlebench_from_recorded_snapshot']+=record['paths']['mlebench'].startswith(snap+'/src/dojo/tasks/mlebench/mle-bench/')
     comparison['complete_bindings']+=1
    else:assert record['paths']=={}
 assert dict(counts)==summary['prefix_status'] and len(complete_runs)==summary['runs_with_complete_prefix']
 assert dict(comparison)==summary['snapshot_path_comparison']
 # The first rejected line can already be from a non-startup phase. Hence the
 # producer's task_phase_log_reads=0 is NOT a defensible byte-level guarantee.
 receipt={'status':'INDEPENDENT_SCOPE_AND_PREFIX_RECEIPT_VERIFIED','private_sha256':h(raw),
  'AB_byte_identical':True,'selected_runs':len(chosen),'runs_with_log_receipts':len(observed_runs),
  'log_prefixes':sum(counts.values()),'prefix_status':dict(counts),'runs_with_complete_prefix':len(complete_runs),
  'maximum_bytes_read_per_file':max_read,'raw_log_reparse_performed_by_verifier':False,
  'task_phase_byte_read_count':'unknown_for_first_unrecognized_line',
  'producer_task_phase_log_reads_zero_not_accepted_as_byte_level_guarantee':True,
  'guard_scope':'stop after first unrecognized line or recognized task boundary; no score parsing or raw line emission',
  'source_paths_exported':len(complete_runs)>0,'installed_revision_attested':False,'training_qualified':False}
 snapshots={m['identity']['snapshot_path'] for m in lineage['manifests'] if any(t['run_id'] in chosen for t in m['tasks'])}
 access=Counter()
 for path in snapshots:
  try:status='accessible' if Path(path).is_dir() else 'absent_on_this_host'
  except PermissionError:status='permission_denied'
  access[status]+=1
 receipt['snapshots_needed_for_fixed_84']=len(snapshots);receipt['snapshot_access_counts_for_fixed_84']=dict(access)
 context={'source_commit':'79164e047b46f7d76db38a89407d1b008c19221a','source_sha256':summary['source_sha256'],
  'bundle_sha256':'1e301af024cc3e56eab29d116162ebe69a3a710c82a47598edd8540fe6676d01',
  'export_git_bytes_identical':True,'two_cpu_threads':True,'gpu_jobs_submitted':0,'model_fits':0,'api_calls':0,'legs':[]}
 rows=io.StringIO();writer=csv.DictWriter(rows,fieldnames=['leg','commit','started_utc','ended_utc','elapsed_seconds','exit_code','selected_runs','complete_prefix_runs','seed'],lineterminator='\n');writer.writeheader()
 for leg in ('A','B'):
  started=(control/('started_'+leg+'.txt')).read_text().strip();ended=(control/('ended_'+leg+'.txt')).read_text().strip()
  seconds=(dt.datetime.fromisoformat(ended.replace('Z','+00:00'))-dt.datetime.fromisoformat(started.replace('Z','+00:00'))).total_seconds()
  rc=int((control/('exit_'+leg+'.txt')).read_text());assert rc==0
  command=['/research/d7/spc/yzyang4/venvs/exp/bin/python','-B','audit_historical_runtime_prefix.py','--output',str(a if leg=='A' else b)]
  context['legs'].append(dict(leg=leg,argv=command,started_utc=started,ended_utc=ended,elapsed_seconds=seconds,exit_code=rc))
  writer.writerow(dict(leg=leg,commit=context['source_commit'],started_utc=started,ended_utc=ended,elapsed_seconds=seconds,exit_code=rc,selected_runs=84,complete_prefix_runs=len(complete_runs),seed='not_applicable_no_sampling'))
 def put(name,data):
  with (a/name).open('xb') as f:f.write(data)
 put('independent_summary.json',c(receipt));put('execution_context.json',c(context));put('runs.csv',rows.getvalue().encode())
 manifest={name:{'bytes':(a/name).stat().st_size,'sha256':h((a/name).read_bytes())} for name in ('summary.json','independent_summary.json','execution_context.json','runs.csv')}
 put('public_manifest.json',c(manifest))
 for directory in (a,b):
  for file in directory.iterdir():assert file.is_file() and not file.is_symlink();file.chmod(0o400)
  directory.chmod(0o500)
 print(json.dumps({'receipt':receipt,'elapsed_seconds':[x['elapsed_seconds'] for x in context['legs']],'read_only_locked':True},sort_keys=True))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);verify(p.parse_args().control)
