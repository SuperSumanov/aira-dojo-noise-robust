"""Independent receipt join / graph verification, not runtime attestation."""
import argparse
from collections import defaultdict,Counter
import hashlib
import json
from pathlib import Path,PurePosixPath

def h(raw):return hashlib.sha256(raw).hexdigest()
def c(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()+b'\n'

def verify(a,b,control):
    source=Path('/research/d7/spc/yzyang4/historical-source-ledger-faf04cc-20260905/source_ledger.private.json').read_bytes()
    assert h(source)=='8e48b4c6598cf8efe205fc6cba5cdd27d14621eb13fad42a7fd4180953da00d1'
    ledger=json.loads(source)
    raw=(a/'pool_lineage.private.json').read_bytes()
    assert raw==(b/'pool_lineage.private.json').read_bytes()
    assert (a/'summary.json').read_bytes()==(b/'summary.json').read_bytes()
    result=json.loads(raw);summary=json.loads((a/'summary.json').read_bytes())
    assert h(raw)==summary['lineage_sha256'] and set(result['closure'])==set(ledger)
    assert result['input_ledger_sha256']==h(source)
    archives={o['archive_sha256'] for r in ledger.values() for o in r['origins']}
    gathered=[]
    for sha in sorted(archives):
        x=(a/('archive-'+sha+'.private.json')).read_bytes()
        assert x==(b/('archive-'+sha+'.private.json')).read_bytes()
        record=json.loads(x);assert record['archive_sha256']==sha
        gathered.extend(record['manifest_records'])
    assert gathered==result['manifests'] and len(archives)==143
    # This implementation uses graph traversal, not the producer's union-find.
    adjacency={rid:set() for rid in ledger};groups=defaultdict(set)
    for rid,row in ledger.items():groups[('old',row['conservative_component_sha256'])].add(rid)
    covered=set();step_counts=Counter();identity_per_instance=defaultdict(set)
    for m in gathered:
        ident=m['identity'];assert h(c(ident))==m['instance_sha256']
        ids=sorted(t['config_id'] for t in m['tasks']);assert ids==ident['task_ids']
        assert len(ids)==len(set(ids))
        parts=PurePosixPath(m['manifest_member']).parts
        assert parts[2]==h('\n'.join(ids).encode())[:12]
        assert ident['pool_dir'].endswith('/'+'/'.join(parts[:3]))
        identity_per_instance[(ident['pool_dir'],ident['created_at'])].add(m['instance_sha256'])
        for task in m['tasks']:
            origins=[(rid,o) for rid,r in ledger.items() for o in r['origins']
                     if o['archive_sha256']==m['archive_sha256']
                     and o['config_member'].split('/')[0]==parts[0]
                     and rid.rsplit('__',1)[0]==task['config_id']]
            matches={rid for rid,o in origins}
            assert len(matches)<=1
            if not matches:assert task['run_id'] is None;continue
            rid=matches.pop();assert task['run_id']==rid
            assert all(task['experiment_dir'].endswith('/'+str(PurePosixPath(o['config_member']).parent)) for _,o in origins)
            same=all(str(task['step_id'])==o['recorded_slurm_id'] for _,o in origins)
            assert same==task['step_matches_recorded_config']
            step_counts[str(same)]+=1;covered.add(rid)
            groups[('pool',m['instance_sha256'])].add(rid)
    assert all(len(v)==1 for v in identity_per_instance.values()), 'same_instance_identity_drift'
    for group in groups.values():
        for rid in group:adjacency[rid].update(group)
    remaining=set(ledger);components=[];blocked_count=0;newly_blocked=0
    while remaining:
        stack=[min(remaining)];members=set()
        while stack:
            rid=stack.pop()
            if rid in members:continue
            members.add(rid);stack.extend(adjacency[rid]-members)
        remaining-=members;components.append(members)
        blocked=any(ledger[r]['old_hold_closure_blocks_train'] for r in members)
        group_sha=h(c(sorted(members)))
        for rid in members:
            assert result['closure'][rid]==dict(component_sha256=group_sha,old_hold_closure_blocks_train=blocked)
            blocked_count+=int(blocked)
            newly_blocked+=int(blocked and not ledger[rid]['old_hold_closure_blocks_train'])
    assert summary['blocked_runs']==blocked_count and summary['newly_blocked_runs']==newly_blocked
    assert summary['historical_runs_linked']==len(covered) and summary['conservative_components']==len(components)
    traces={}
    for leg in ('A','B'):
        assert (control/('exit_'+leg+'.txt')).read_text().strip()=='0'
        trace=(control/('opens_'+leg+'.private.log')).read_bytes()
        assert b'journal.jsonl"' not in trace and b'env_variables.json"' not in trace
        traces[leg]=h(trace)
    receipt={'status':'INDEPENDENT_POOL_RECEIPT_JOIN_AND_CLOSURE_VERIFIED',
             'lineage_sha256':h(raw),'runs':len(ledger),'archives':len(archives),
             'manifest_records':len(gathered),'linked_runs':len(covered),
             'actual_recorded_launcher_instances':len(identity_per_instance),
             'components':len(components),'blocked_runs':blocked_count,'newly_blocked_runs':newly_blocked,
             'config_slurm_step_checks':dict(step_counts),'AB_lineage_and_archive_receipts_byte_identical':True,
             'same_instance_identity_drift':False,'trace_sha256':traces,
             'verification_scope':'stored receipt join, immutable origin binding, separate graph algorithm, A/B bytes; not independent raw tar reparse or OS isolation',
             'training_source_qualified':False,'runtime_environment_attested':False}
    with (a/'independent_summary.json').open('xb') as f:f.write(c(receipt))
    print(json.dumps(receipt,sort_keys=True))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--a',type=Path,required=True);p.add_argument('--b',type=Path,required=True);p.add_argument('--control',type=Path,required=True)
    args=p.parse_args();verify(args.a,args.b,args.control)
