"""Read-only, terminal-only G0 schema/hash acceptance. Emits no dev values."""
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys

ROOT = Path('/research/d7/spc/yzyang4/critic-component-g0/runs/job-12499')
SOURCE = Path('/research/d7/spc/yzyang4/worktrees/critic-g0-final-only-20260903-b')
SOURCE_COMMIT = '5f3bc362db922c8edee2ef134656dfdb9a2b74fb'
SOURCE_SHA = 'd3cfd12602dc399a456810d4f706124df7117834ebba124813233f77ba043977'
CONTROL = Path('/research/d7/spc/yzyang4/worktrees/g0_r5_90cd910_sparse')
CONTROL_COMMIT = '90cd91058fd03e86185d42c14704845827259655'
PREFLIGHT_SHA = '0f5c83cb3dcd8ec73e5d6aefc0c42fa34619d73bcc0e6f1464861e1a4b6347ad'
SECRET = re.compile(r'(?i)(?<![A-Za-z0-9])(?:sk-[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})(?![A-Za-z0-9])|Bearer\s+\S+')

def sha(path):
    before = path.stat()
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), 'file_changed'
    return h.hexdigest()

def small_json(path):
    assert path.stat().st_size <= 8*1024*1024
    raw = path.read_text()
    assert not SECRET.search(raw), 'credential_shape_no_disclosure'
    return json.loads(raw)

env = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
raw = subprocess.check_output(['sacct', '-n', '-P', '-j', '12181,12288,12377,12486,12497,12499',
    '--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocTRES'], env=env, text=True)
jobs = {}
for line in raw.splitlines():
    fields = line.split('|')
    if fields[0].isdigit():
        job, state, code, seconds, resources = fields[:5]
        gpu = re.search(r'(?:^|,)gres/gpu=(\d+)(?:,|$)', resources)
        assert gpu and job not in jobs
        jobs[job] = {'state': state, 'exit_code': code, 'elapsed_seconds': int(seconds),
                     'gpus': int(gpu[1])}
assert set(jobs) == {'12181','12288','12377','12486','12497','12499'}
assert jobs['12499']['state'] == 'COMPLETED' and jobs['12499']['exit_code'] == '0:0', 'not_successful_terminal'
assert jobs['12499']['gpus'] == 2
scontrol = subprocess.check_output(['scontrol','show','job','12499','-o'],env=env,text=True)
for field, expected_value in (('Restarts','0'),('Requeue','0'),('JobState','COMPLETED')):
    match = re.search(r'(?:^|\s)'+field+r'=(\S+)',scontrol)
    assert match and match[1] == expected_value, 'scheduler_terminal_field_mismatch'
jobs['12499'].update(restarts=0,requeue=0)
assert (ROOT/'COMPLETE').read_text().strip() == 'status=G0_ENGINEERING_CALIBRATION_VALID'
assert not (ROOT/'FAILED').exists()
assert (ROOT/'training_exit_status.txt').read_text().strip() == 'training_exit_status=0'
assert sha(ROOT/'preflight.json') == PREFLIGHT_SHA
for repo, commit in ((SOURCE,SOURCE_COMMIT),(CONTROL,CONTROL_COMMIT)):
    assert subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip() == commit
    assert not subprocess.check_output(['git','-C',str(repo),'status','--porcelain','--untracked-files=no'],text=True).strip()
assert sha(SOURCE/'src/mle_critic/src/train/bradley_terry.py') == SOURCE_SHA
p = small_json(ROOT/'preflight.json')
v = small_json(ROOT/'verification.json')
assert v['status'] == 'G0_ENGINEERING_CALIBRATION_VALID' and v['preflight_sha256'] == PREFLIGHT_SHA
result = v['result']
checkpoint = Path(result['checkpoint'])
assert checkpoint.is_relative_to(ROOT) and checkpoint.name == 'checkpoint-10'
assert result['global_step'] == 10 and result['dev_evaluations'] == 1
artifact_hashes = {}
for relative, expected in result['checkpoint_artifacts'].items():
    path = checkpoint.parent/relative
    assert path.is_relative_to(checkpoint) and not path.is_symlink() and path.is_file()
    assert path.stat().st_size == expected['bytes'] and sha(path) == expected['sha256']
    artifact_hashes[path.relative_to(checkpoint).as_posix()] = expected
assert set(artifact_hashes) == {x.relative_to(checkpoint).as_posix() for x in checkpoint.rglob('*') if x.is_file()}
for line in (ROOT/'SHA256SUMS').read_text().splitlines():
    expected, name = line.split(maxsplit=1)
    path = Path(name.lstrip('*'))
    assert path.parent == ROOT and re.fullmatch(r'[0-9a-f]{64}',expected)
    assert sha(path) == expected

# Derive exact expected tensor schema without allocating/loading model weights.
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
import torch
from transformers import AutoConfig, AutoModel
torch.set_num_threads(1)
config = AutoConfig.from_pretrained(p['model']['snapshot'],local_files_only=True)
with torch.device('meta'):
    backbone = AutoModel.from_config(config,torch_dtype=torch.bfloat16,attn_implementation='eager')
    head = torch.nn.Linear(config.hidden_size,1,dtype=torch.bfloat16)
expected = {'backbone.'+k: {'shape':list(t.shape),'dtype':'BF16'} for k,t in backbone.state_dict().items()}
expected.update({'head.'+k:{'shape':list(t.shape),'dtype':'BF16'} for k,t in head.state_dict().items()})
assert all(t.dtype == torch.bfloat16 for t in list(backbone.state_dict().values())+list(head.state_dict().values()))
observed = {}
weight_files = sorted(checkpoint.glob('*.safetensors'))
assert weight_files, 'no_safetensors_weights'
for path in weight_files:
    with path.open('rb') as stream:
        length_raw = stream.read(8)
        assert len(length_raw) == 8
        length = struct.unpack('<Q', length_raw)[0]
        assert 0 < length < 8*1024*1024
        header = json.loads(stream.read(length))
    offsets = []
    for key, value in header.items():
        if key == '__metadata__':
            continue
        assert key not in observed and key in expected, 'unexpected_tensor_key'
        assert value['shape'] == expected[key]['shape'] and value['dtype'] == expected[key]['dtype'], 'tensor_schema_mismatch'
        start, end = value['data_offsets']
        assert isinstance(start,int) and isinstance(end,int) and 0 <= start <= end
        assert end-start == math.prod(value['shape'])*2, 'tensor_byte_size_mismatch'
        offsets.append((start,end))
        observed[key] = expected[key]
    offsets.sort()
    assert offsets and offsets[0][0] == 0
    assert all(a[1] == b[0] for a,b in zip(offsets,offsets[1:])), 'tensor_hole_or_overlap'
    assert offsets[-1][1]+8+length == path.stat().st_size, 'weight_file_length_mismatch'
assert observed == expected, 'missing_tensor_keys'
total = sum(x['elapsed_seconds']*x['gpus'] for x in jobs.values())
assert total <= 14400
receipt = {'status':'G0_TERMINAL_CHECKPOINT_SCHEMA_HASH_PASS', 'job_id':12499,
    'checked_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'source_commit':SOURCE_COMMIT,'control_commit':CONTROL_COMMIT,
    'verification_sha256':sha(ROOT/'verification.json'),'preflight_sha256':PREFLIGHT_SHA,
    'checkpoint_artifacts':artifact_hashes,'tensor_count':len(expected),
    'parameter_count':sum(math.prod(x['shape']) for x in expected.values()),'weight_dtypes':['BF16'],
    'weight_file_count':len(weight_files),'global_steps':10,'dev_evaluations':1,
    'dev_values_disclosed':False,'jobs':jobs,'cumulative_gpu_seconds':total,'cumulative_gpu_hours':total/3600,
    'remaining_gpu_seconds_in_existing_cap':14400-total,'timing':result['timing'],
    'gnu_elapsed_seconds':result['gnu_elapsed_seconds'],'peak_gpu_memory_mib':result['peak_gpu_memory_mib'],
    'trace_scope_certified':False,'scientific_claim':'none; G0 engineering calibration only',
    'checkpoint_resume_claim':False,'tensor_values_inspected':False}
out = Path(sys.argv[1])
with out.open('x') as stream:
    json.dump(receipt,stream,sort_keys=True,indent=2)
print(json.dumps(receipt,sort_keys=True,indent=2))
