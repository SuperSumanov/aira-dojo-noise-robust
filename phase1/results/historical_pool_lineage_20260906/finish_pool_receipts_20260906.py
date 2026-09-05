"""Package aggregate evidence only; private scheduling identities stay remote."""
import csv,datetime as dt,hashlib,io,json,os,re,sys
from collections import Counter,defaultdict
from pathlib import Path

root=Path('/research/d7/spc/yzyang4')
code=sys.argv[1];control=Path(sys.argv[2]);git_commit=sys.argv[3]
a=root/('historical-pool-lineage-'+code+'-20260906-A');b=root/('historical-pool-lineage-'+code+'-20260906-B')
def h(raw):return hashlib.sha256(raw).hexdigest()
def c(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()+b'\n'
def put(path,raw):
 with path.open('xb') as f:f.write(raw)

os.umask(0o077)
summary=json.loads((a/'summary.json').read_bytes());assert (a/'independent_summary.json').is_file()
raw=(a/'pool_lineage.private.json').read_bytes();assert h(raw)==summary['lineage_sha256']
p=json.loads(raw)
ledger_raw=(root/'historical-source-ledger-faf04cc-20260905/source_ledger.private.json').read_bytes()
assert h(ledger_raw)==p['input_ledger_sha256'];ledger=json.loads(ledger_raw)
complete=[m for m in p['manifests'] if all(t['run_id'] is not None for t in m['tasks'])]
complete_runs={t['run_id'] for m in complete for t in m['tasks']}
components_with_partial={p['closure'][t['run_id']]['component_sha256'] for m in p['manifests'] if any(t['run_id'] is None for t in m['tasks']) for t in m['tasks'] if t['run_id']}
components_with_mismatch={p['closure'][t['run_id']]['component_sha256'] for m in p['manifests'] for t in m['tasks'] if t['step_matches_recorded_config'] is False}
covered={t['run_id'] for m in p['manifests'] for t in m['tasks'] if t['run_id']}
components_without_coverage={p['closure'][rid]['component_sha256'] for rid in ledger if rid not in covered}
structurally_clear={rid for rid,row in p['closure'].items() if not row['old_hold_closure_blocks_train'] and row['component_sha256'] not in components_with_partial|components_with_mismatch|components_without_coverage}
access={}
for path in sorted({m['identity']['snapshot_path'] for m in p['manifests']}):
 try:access[path]='accessible' if Path(path).is_dir() else 'absent'
 except PermissionError:access[path]='permission_denied'
details={'fully_fixed_scope_manifests':len(complete),'runs_in_fully_fixed_scope_manifests':len(complete_runs),
 'old_hold_clear_runs_in_fully_fixed_scope_manifests_not_admitted':sum(not p['closure'][r]['old_hold_closure_blocks_train'] for r in complete_runs),
 'components_with_unmatched_pool_members':len(components_with_partial),
 'components_with_step_mismatch':len(components_with_mismatch),
 'components_with_uncovered_runs':len(components_without_coverage),
 'old_hold_clear_and_complete_recorded_pool_component_runs_not_admitted':len(structurally_clear),
 'recorded_config_strata_in_that_range':len({ledger[r]['origins'][0]['recorded_config_stratum_sha256'] for r in structurally_clear}),
 'snapshot_path_access_counts':dict(Counter(access.values())),
 'runtime_pristine_or_training_qualification_attested':False}
put(a/'coverage_details.json',c(details))
context={'source_commit':git_commit,'source_sha256':summary['source_sha256'],
 'source_bundle_sha256':h(Path('/tmp/'+{'e7244fb':'historical-pool-retry.tar','53a6b21':'historical-pool-local.tar','14e38d2':'historical-pool-14e38d2.tar'}[code]).read_bytes()),
 'python_executable':sys.executable,'python_version':sys.version.split()[0],'threads':2,
 'per_leg_internal_deadline_seconds':1500,'per_leg_external_timeout_seconds':1550,
 'PYTHONHASHSEED':'0','random_sampling':False,'gpu_jobs_submitted':0,'paid_api_calls':0,
 'training_fits':0,'legs':[]}
csvout=io.StringIO();writer=csv.DictWriter(csvout,fieldnames=['leg','commit','seed','started_at_utc','ended_at_utc','elapsed_seconds','exit_code','runs','linked_runs','manifests','lineage_sha256'],lineterminator='\n');writer.writeheader()
for leg in ('A','B'):
 started=(control/('started_'+leg+'.txt')).read_text().strip();ended=(control/('ended_'+leg+'.txt')).read_text().strip()
 elapsed=(dt.datetime.fromisoformat(ended.replace('Z','+00:00'))-dt.datetime.fromisoformat(started.replace('Z','+00:00'))).total_seconds()
 rc=int((control/('exit_'+leg+'.txt')).read_text());assert rc==0
 argv=[sys.executable,'-B','recover_historical_pool_lineage.py','--output',str(a if leg=='A' else b)]
 context['legs'].append({'leg':leg,'argv':argv,'started_at_utc':started,'ended_at_utc':ended,'elapsed_seconds':elapsed,'exit_code':rc})
 writer.writerow(dict(leg=leg,commit=git_commit,seed='not_applicable_no_sampling',started_at_utc=started,ended_at_utc=ended,elapsed_seconds=elapsed,exit_code=rc,runs=summary['fixed_runs'],linked_runs=summary['historical_runs_linked'],manifests=summary['manifest_records'],lineage_sha256=summary['lineage_sha256']))
put(a/'execution_context.json',c(context));put(a/'runs.csv',csvout.getvalue().encode())
files=['summary.json','independent_summary.json','coverage_details.json','execution_context.json','runs.csv']
manifest={name:{'bytes':(a/name).stat().st_size,'sha256':h((a/name).read_bytes())} for name in files}
put(a/'public_manifest.json',c(manifest))
for d in (a,b):
 for file in d.iterdir():
  assert file.is_file() and not file.is_symlink();file.chmod(0o400)
 d.chmod(0o500)
print(json.dumps({'coverage_details':details,'elapsed_seconds':[x['elapsed_seconds'] for x in context['legs']],
                  'public_manifest':manifest,'read_only_locked':True},sort_keys=True))
