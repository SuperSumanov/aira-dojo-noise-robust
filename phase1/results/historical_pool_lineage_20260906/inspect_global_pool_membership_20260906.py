import collections,hashlib,json
from pathlib import Path,PurePosixPath
r=Path('/research/d7/spc/yzyang4')
lraw=(r/'historical-source-ledger-faf04cc-20260905/source_ledger.private.json').read_bytes();assert hashlib.sha256(lraw).hexdigest()=='8e48b4c6598cf8efe205fc6cba5cdd27d14621eb13fad42a7fd4180953da00d1'
l=json.loads(lraw)
for code in ('14e38d2','e7244fb'):
 root=r/('historical-pool-lineage-'+code+'-20260906-A');raw=(root/'pool_lineage.private.json').read_bytes()
 assert hashlib.sha256(raw).hexdigest()==json.loads((root/'summary.json').read_bytes())['lineage_sha256']
 p=json.loads(raw);counts=collections.Counter();unknownids=set();instances=collections.defaultdict(dict)
 known_in_instance=collections.defaultdict(set)
 for m in p['manifests']:
  known_in_instance[m['instance_sha256']].update(t['run_id'] for t in m['tasks'] if t['run_id'])
 for m in p['manifests']:
  for t in m['tasks']:
   if t['run_id'] is not None:
    instances[m['instance_sha256']][t['config_id']]=t['run_id'];continue
   candidates={rid for rid,row in l.items() for o in row['origins'] if rid.rsplit('__',1)[0]==t['config_id'] and t['experiment_dir'].endswith('/'+str(PurePosixPath(o['config_member']).parent))}
   counts['globally_unique_binding' if len(candidates)==1 else 'globally_missing' if not candidates else 'globally_ambiguous']+=1
   if len(candidates)==1:
    counts['already_bound_in_same_instance_other_archive' if candidates <= known_in_instance[m['instance_sha256']] else 'directory_match_only_not_instance_confirmed']+=1
   if not candidates:unknownids.add(t['config_id'])
   instances[m['instance_sha256']].setdefault(t['config_id'],next(iter(candidates)) if len(candidates)==1 else None)
 complete={key for key,values in instances.items() if all(v is not None for v in values.values())}
 covered={rid for key in complete for rid in instances[key].values()}
 result={'code':code,'unbound_record_classification':dict(counts),'distinct_globally_missing_config_ids':len(unknownids),
         'instances_with_complete_directory_candidates_not_qualification':len(complete),'runs_in_those_instances':len(covered),
         'lineage_sha256':hashlib.sha256(raw).hexdigest(),'no_roles_changed':True}
 output=r/('historical-global-pool-binding-'+code+'-20260906.json')
 with output.open('x') as f:json.dump(result,f,sort_keys=True);f.write('\n')
 output.chmod(0o400);print(json.dumps(result))
