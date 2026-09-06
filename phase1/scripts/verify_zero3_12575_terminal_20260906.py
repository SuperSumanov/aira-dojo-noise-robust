"""Final independent evidence/trace/permission check; never trains or reads corpus."""
import datetime as dt,hashlib,json,os,re,subprocess
from pathlib import Path
BASE=Path('/research/d7/spc/yzyang4')
ROOT=BASE/'critic-zero3-engineering/job-12575'
SUB=BASE/'critic-zero3-engineering/submission-20260906-3090-native-cache'
POST=BASE/'critic-zero3-postcheck-12575-r2-20260906'
OLD=BASE/'critic-zero3-postcheck-12575-20260906'
FINAL=BASE/'critic-zero3-final-readout-12575-20260906'
SOURCE='1c211b87880a1110e3a67cc1dc7d277e5db18441'
CHECKER='c3eb1d546ac5314a8685bc692817b6cfde534c68'
SHAPE=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    b=p.read_bytes();assert not SHAPE.search(b);return json.loads(b)
def main():
    ready=read(SUB/'READY.json');control=Path(ready['control'])
    assert ready['commit']==SOURCE and len(ready['hashes'])==45
    assert all(sha(control/n)==h for n,h in ready['hashes'].items())
    assert read(SUB/'RELEASED.json')=={'job_id':'12575','commit':SOURCE}
    assert read(SUB/'INDEPENDENT_PRE_RELEASE.json')['source_commit']==SOURCE
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    accounting=subprocess.check_output(['sacct','-X','-n','-P','-j','12575','--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env,timeout=20)
    row=accounting.decode().strip().split('|');assert row[:3]==['12575','COMPLETED','271'] and row[4]=='0:0' and 'gres/gpu=2' in row[3].split(',')
    assert (ROOT/'exit_status.txt').read_text().strip()=='0'
    prior=read(ROOT/'independent_acceptance.json');final=read(FINAL/'receipt.json')
    assert prior['classification']=='INDEPENDENT_TINY_ZERO3_RESUME_ACCEPTANCE_NOT_EFFECT' and prior['code_commit']==SOURCE
    assert len(prior['actual_checkpoint_payload_comparisons'])==12 and len(prior['manifests'])==9
    assert all(r['all_payload_bits_equal'] is True for r in prior['actual_checkpoint_payload_comparisons'])
    assert final['classification']=='ACTUAL_TINY_ZERO3_FINAL_READOUT_NOT_1P7B_OR_EFFECT' and final['training_commit']==SOURCE
    assert final['prior_payload_acceptance_sha256']==sha(ROOT/'independent_acceptance.json')
    assert final['bitwise_final_weights_equal'] is True and final['bitwise_synthetic_outputs_equal'] is True
    assert final['final_models']==3 and final['production_admission'] is False and final['corpus_reads']==0
    assert prior['gpu_initialized'] is False and final['gpu_initialized'] is False
    source=read(POST/'source.json');assert source['commit']==CHECKER
    assert all(sha(POST/'code'/n)==h for n,h in source['files'].items()) and len(source['files'])==26
    for stage in ('cpu-tests','payload','readout'):
        x=read(POST/(stage+'-status.json'));assert x['returncode']==0 and x['timed_out'] is False
    assert read(OLD/'payload-status.json')['returncode']==1
    assert sha(OLD/'payload.log')=='eaa80d4b5d7d7e14180f4ff4f2d972b37f666ebdd9e21d12c34acd2c51045866'
    # Re-hash all checkpoints without importing or executing the pickled payloads.
    manifests={}
    for record in prior['manifests']:
        cp=ROOT/'trajectories'/record['path'];m=read(cp/'manifest.json')
        assert sha(cp/'manifest.json')==record['manifest_sha256']
        assert m['binding']==read(ROOT/'trajectories/full/trajectory.json')['binding']
        for n,h in m['files'].items():assert h=={'bytes':(cp/n).stat().st_size,'sha256':sha(cp/n)}
        manifests[record['path']]=record['manifest_sha256']
    inspected={};readonly=[]
    for label,root in (('gpu',ROOT),('post_r2',POST),('post_original',OLD),('final',FINAL)):
        for p in sorted(root.rglob('*')):
            if not p.is_file():continue
            rel=p.relative_to(root).as_posix()
            if rel.startswith(('code/','triton/')):continue
            assert not p.is_symlink() and p.stat().st_uid==os.getuid() and p.stat().st_nlink==1
            # Checkpoint tensors were authenticated above. Scan text and all traces.
            if p.suffix not in ('.pt','.pkl'):
                h=hashlib.sha256()
                with p.open('rb') as f:
                    for line in f:
                        assert not SHAPE.search(line)
                        if p.suffix=='.trace' or p.name=='file_trace.log':
                            assert not any(x in line for x in (b'/prospective_decision_v1/',b'decision_frozen_v11_',b'/target522-',b'/target300-'))
                        h.update(line)
                inspected[label+'/'+rel]={'bytes':p.stat().st_size,'sha256':h.hexdigest()}
            readonly.append(p)
    assert all(sha(control/n)==h for n,h in ready['hashes'].items())
    assert all(sha(POST/'code'/n)==h for n,h in source['files'].items())
    for p in readonly:p.chmod(0o444)
    assert all(p.stat().st_mode&0o222==0 for p in readonly)
    result={'classification':'REAL_TINY_ZERO3_RESTART_AND_FINAL_READOUT_ACCEPTED_NOT_PIVOT_OR_EFFECT',
        'job_id':'12575','source_commit':SOURCE,'checker_commit':CHECKER,'utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'gpu_elapsed_seconds':271,'allocated_gpu_seconds':542,'optional_group_actual_gpu_seconds':817+542,
        'actual_checkpoint_payload_comparisons':12,'checkpoint_bundles':9,'final_models':3,
        'source_files':45,'postcheck_source_files':26,'read_only_files':len(readonly),'checked_text':inspected,
        'manifest_sha256':manifests,'credential_shape_hits':0,'protected_path_marker_hits':0,
        'prior_payload_acceptance_sha256':sha(ROOT/'independent_acceptance.json'),'final_readout_sha256':sha(FINAL/'receipt.json'),
        'original_failed_postcheck_preserved':True,'new_gpu_jobs_started':0,'model_effect_measured':False,
        'is_1p7b_or_16k_qualification':False,'verifier_sha256':sha(Path(__file__))}
    out=ROOT/'TERMINAL_VERIFIED.json'
    with out.open('x') as f:json.dump(result,f,sort_keys=True,indent=2)
    out.chmod(0o444)
    with (ROOT/'verified_sacct.txt').open('xb') as f:f.write(accounting)
    (ROOT/'verified_sacct.txt').chmod(0o444)
    print(json.dumps({'status':result['classification'],'receipt_sha256':sha(out),'read_only_files':len(readonly),
        'payload_comparisons':12,'checkpoint_bundles':9,'final_models':3,'optional_group_gpu_seconds':1359}))


if __name__=='__main__':main()
