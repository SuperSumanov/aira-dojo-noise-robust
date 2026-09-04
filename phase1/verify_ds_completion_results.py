"""Independent result arithmetic. Does not import producer or adapter."""
import hashlib
import json
import math
from pathlib import Path
import subprocess

repo=Path(__file__).resolve().parents[1]
root=Path(__file__).resolve().parent/'results/ds_completion_20260905'
verified_files=0;verified_sources=0
for run,commit in [('r1','94976ec0aba086cca22bf7dc13eae420ae624b35'),('r2','d6b569e9ee5b77e40565f5c86db47650e6011ab4')]:
    directory=root/run
    manifest=json.loads((directory/'manifest.json').read_bytes())
    for name,digest in manifest.items():
        assert Path(name).name==name
        assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==digest
        verified_files+=1
    context=json.loads((directory/'execution_context.json').read_bytes())
    assert context['source_commit']==commit
    for name,digest in context['source_sha256'].items():
        raw=subprocess.check_output(['git','-C',str(repo),'show',commit+':'+name])
        assert hashlib.sha256(raw).hexdigest()==digest
        verified_sources+=1
r1=json.loads((root/'r1/producer_a.json').read_bytes())
assert r1==dict(status='FAILED_CLOSED',exception_type='PermissionError',safe_reason='linked_source')
a=(root/'r2/producer_a.json').read_bytes();b=(root/'r2/producer_b.json').read_bytes()
assert a==b
r=json.loads(a)
seen=set()
for c in r['cases']:
    w,n,rank,skip=c['world'],c['planned_update_pairs'],c['rank'],c['simulated_overflow']
    key=w,n,rank,skip
    assert key not in seen;seen.add(key)
    micro=math.ceil(n/(w*8));q,rem=divmod(n,micro*w)
    assert c['local_pair_counts']==[q+int(m*w+rank<rem) for m in range(micro)]
    assert c['attempted_updates']==c['attempted_update_delta']==1
    assert c['stub_applied_updates']==c['applied_update_delta']==int(not skip)
    assert c['skipped_update_delta']==int(skip)
    assert c['optimizer_step_skipped'] is skip and c['can_commit_plan_cursor'] is (not skip)
    assert c['legacy_reported_skip'] is False and c['engine_reported_samples']==128
expected={(w,n,rank,s) for w in (2,4) for n in (128,48,114,81) for rank in range(w) for s in (False,True)}
assert seen==expected
assert r['case_count']==len(seen)==48 and r['legacy_false_success_detected_cases']==24
assert set(r['injected_faults_detected'])=={'missing_step','double_step','skipped_counter_drift'}
assert r['real_backend_executed'] is False and r['real_data_opened'] is False
assert len(r['data_open_counts'])==4 and set(r['data_open_counts'].values())=={2}
assert r['new_gpu_jobs']==r['model_fits']==r['api_calls']==0
for path,digest in [('phase1/global_local_calibration_candidate_protocol_v2.json','3e0785a13f9d9fc3638a222e78fd74010757b1201249ebd0ad7a5597c224a2e9'),('phase1/global_local_historical_development_protocol_v1.json','1964e8e48e998660584c045a7e8fe2a03d61a946ba266d29d74555f934482902')]:
    assert hashlib.sha256((repo/path).read_bytes()).hexdigest()==digest
print(json.dumps(dict(status='INDEPENDENT_RESULT_ARITHMETIC_AND_GIT_BINDINGS_PASS',
    verified_manifest_files=verified_files,verified_source_blobs=verified_sources,
    cases=48,normal_cases=24,overflow_cases=24,injected_failures=3,
    preserved_failed_attempts=1,receipt_sha256=hashlib.sha256(a).hexdigest(),frozen_files_unchanged=2,
    numerical_or_real_gpu_validation=False)))
