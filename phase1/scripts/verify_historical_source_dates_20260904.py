"""Independent read-only recomputation; does not import the date diagnostic."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

PATH = Path('/research/d7/spc/yzyang4/senior-true-batch-identity-support/a466888-v3/producer_1/run_batch_manifest.jsonl')
SHA = '60846a3a68f4cc9644ad676aa89e0d250b5fb8c0a3b8f6c1a708f2b5d0fb3e4d'


def verify(receipt_path, receipt_sha):
    p = Path(receipt_path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size > 64*1024:
        raise ValueError('unsafe_receipt')
    raw_receipt = p.read_bytes()
    if hashlib.sha256(raw_receipt).hexdigest() != receipt_sha:
        raise ValueError('receipt_changed')
    if PATH.is_symlink() or not PATH.is_file() or PATH.stat().st_size > 1024*1024:
        raise ValueError('unsafe_source_metadata')
    raw = PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SHA:
        raise ValueError('source_changed')
    for body in (raw,raw_receipt):
        if re.search(rb'(?i)(?:sk-[A-Za-z0-9_.-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})',body):
            raise ValueError('credential_shape')
    rows = [json.loads(line) for line in raw.splitlines()]
    state_sets = {state:{r['run_id'] for r in rows if r['source_match_status']==state}
                  for state in ('unique','ambiguous','missing')}
    if sum(map(len,state_sets.values())) != len(rows) or len(rows) != 676:
        raise ValueError('invalid_inventory')
    deltas=[]
    for r in rows:
        if r['source_match_status'] != 'unique':
            if r['source_day'] is not None or r['batch_sha256'] is not None:
                raise ValueError('unresolved_mapping_not_empty')
            continue
        launch=datetime.strptime(r['run_id'].rsplit('__',1)[1],'%Y-%m-%d')
        day=r['source_day'].split('-',1)[0]
        collection=datetime.strptime('2026'+day,'%Y%m%d')
        deltas.append((collection-launch).days)
    expected={'rows':len(rows),'run_source_status':{k:len(v) for k,v in state_sets.items()},
              'unique_same_date':deltas.count(0),'unique_cross_date':len(deltas)-deltas.count(0),
              'collection_minus_launch_days':{str(k):deltas.count(k) for k in sorted(set(deltas))},
              'ambiguous_sources_resolved':0,'missing_sources_resolved':0,'old_S0_overridden':False}
    result=json.loads(raw_receipt)
    if result['metrics'] != expected or result['input_sha256'] != SHA:
        raise ValueError('independent_metrics_mismatch')
    for key in ('archive_payload_reads','archive_header_rescans','cards_or_pairs_opened','protected_cohort_reads','new_gpu_jobs','model_fits'):
        if result[key] != 0:
            raise ValueError('scope_mismatch')
    if hashlib.sha256(PATH.read_bytes()).hexdigest() != SHA:
        raise ValueError('source_post_drift')
    return {'status':'INDEPENDENT_HISTORICAL_DATE_DIAGNOSTIC_MATCH','receipt_sha256':receipt_sha,
            'input_sha256':SHA,'metrics':expected,'model_fits':0,'new_gpu_jobs':0,'archive_payload_reads':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--receipt',required=True); parser.add_argument('--sha256',required=True)
    a=parser.parse_args()
    try:
        print(json.dumps(verify(a.receipt,a.sha256),sort_keys=True))
    except Exception as exc:
        print(json.dumps({'status':'INDEPENDENT_FAILED_CLOSED','exception_type':type(exc).__name__}))
        raise SystemExit(1)
