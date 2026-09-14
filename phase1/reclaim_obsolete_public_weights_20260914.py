"""Two-phase reclamation of ten exact, verified public generator shards only.

No recursive deletion. Configs/tokenizers/download metadata and every trained
critic, corpus, experiment result, runtime and current image remain untouched.
"""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import urllib.request

BASE=Path('/research/d7/spc/yzyang4')
TARGETS=(('Qwen2.5-Coder-14B-Instruct','aedcc2d42b622764e023cf882b6652e646b95671',6),
         ('Qwen2.5-Coder-7B-Instruct','c03e6d358207e414f1eca0bb1891e29f1db0e242',4))
PROTECTED=(BASE/'forets-critic-incoming-20260908-3lcjjcwq/unpacked/Qwen3-8B_reward_seed1/checkpoint-100/model.safetensors',
           BASE/'local-qwen27b-20260914-zcx1k1dy/vllm.sif',
           BASE/'aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif')

def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def emit(**value):print(json.dumps(value),flush=True)
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def info(path):
    s=path.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or s.st_nlink!=1:
        raise ValueError('not an exclusively owned regular file: '+str(path))
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,allocated_bytes=s.st_blocks*512,mtime_ns=s.st_mtime_ns)
def save(path,value):
    raw=(json.dumps(value,indent=2,sort_keys=True)+'\n').encode()
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return hashlib.sha256(raw).hexdigest()
def read_json_url(url):
    with urllib.request.urlopen(url,timeout=30) as r:raw=r.read(1_000_001)
    if len(raw)>1_000_000:raise ValueError('metadata size')
    return json.loads(raw)
def roots():
    values=[BASE/'models'/name for name,_,_ in TARGETS]
    for path in values:
        if path.is_symlink() or path.resolve(strict=True)!=path or path.parent!=BASE/'models':
            raise ValueError('target outside exact model directory')
    return values
def activity_gate():
    targets=roots();needles=[str(p).encode() for p in targets]+[p.name.encode() for p in targets]
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    queue=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i|%T|%R'],env=env,timeout=20).decode().strip().splitlines()
    if queue and queue!=['12535|PENDING|(JobHeldUser)']:raise ValueError('new scheduler activity: recheck dependencies')
    configs=[BASE/'local-qwen27b-20260914-zcx1k1dy/plan.json',
             BASE/'local-qwen27b-20260914-zcx1k1dy/calibration-inputs.json',
             BASE/'worktrees/zero3-engineering-09911b15ca06/phase1/scripts/zero3_session_engineering_20260905.sbatch']
    for path in configs:
        if any(n in path.read_bytes() for n in needles):raise ValueError('current configuration references cleanup target')
    inspected=0
    for proc in Path('/proc').iterdir():
        if not proc.name.isdecimal() or proc.name==str(os.getpid()):continue
        try:
            if proc.stat().st_uid!=os.getuid():continue
            comm=(proc/'comm').read_text().strip()
            if any(n in (proc/'cmdline').read_bytes() for n in needles):raise ValueError('live command references target')
            if comm in ('sshd','systemd','(sd-pam)'):continue
            if any(n in (proc/'maps').read_bytes() for n in needles):raise ValueError('live mapping references target')
            for path in [proc/'cwd']+list((proc/'fd').iterdir()):
                try:
                    linked=os.readlink(path)
                    if any(linked==str(t) or linked.startswith(str(t)+'/') for t in targets):
                        raise ValueError('live open file or cwd references target')
                except FileNotFoundError:pass
            inspected+=1
        except (FileNotFoundError,ProcessLookupError):pass
    return dict(scheduler=queue,linux5_processes_inspected=inspected,protected_files={str(p):info(p) for p in PROTECTED})

def prepare():
    gate=activity_gate()
    root=Path(tempfile.mkdtemp(prefix='research-storage-cleanup-20260914-',dir=BASE))
    emit(event='PREPARING_READ_ONLY_WEIGHT_VERIFICATION',root=str(root))
    items=[];retained={};recovery=[]
    for name,revision,count in TARGETS:
        target=BASE/'models'/name;repo='Qwen/'+name
        model=read_json_url(f'https://huggingface.co/api/models/{repo}/revision/{revision}')
        if model.get('sha')!=revision or model.get('private') or model.get('gated'):
            raise ValueError('fixed public recovery revision unavailable')
        entries=read_json_url(f'https://huggingface.co/api/models/{repo}/tree/{revision}?recursive=false&expand=false')
        expected={f'model-{i:05}-of-{count:05}.safetensors' for i in range(1,count+1)}
        if {p.name for p in target.glob('*.safetensors')}!=expected:raise ValueError('unexpected shard set')
        by_name={e['path']:e for e in entries if e.get('type')=='file' and e['path'] in expected}
        if set(by_name)!=expected:raise ValueError('public shard manifest differs')
        for file in sorted(expected):
            entry=by_name[file];local=target/file;before=info(local)
            metadata=target/'.cache/huggingface/download'/(file+'.metadata')
            lines=metadata.read_text().splitlines()
            if before['bytes']!=entry['size'] or lines[:2]!=[revision,entry['lfs']['oid']]:
                raise ValueError('local/public download metadata differ')
            if not re.fullmatch('[0-9a-f]{64}',entry['lfs']['oid']):raise ValueError('missing publisher digest')
            items.append(dict(path=str(local),repo=repo,revision=revision,expected_sha256=entry['lfs']['oid'],before=before))
        for path in target.rglob('*'):
            if path.is_symlink():raise ValueError('unexpected symlink in public download')
            if path.is_file() and path.name not in expected:
                if path.stat().st_size>10_000_000:raise ValueError('unexpected non-weight payload')
                retained[str(path)]=dict(sha256=sha(path),before=info(path))
        first=sorted(expected)[0]
        with urllib.request.urlopen(urllib.request.Request(f'https://huggingface.co/{repo}/resolve/{revision}/{first}',method='HEAD'),timeout=30) as r:
            if r.status!=200:raise ValueError('recovery download not reachable')
        recovery.append(dict(repo=repo,revision=revision,local_directory=str(target),
            command=['hf','download',repo,'--revision',revision,'--local-dir',str(target)],first_shard_head_200=True))
    save(root/'verification-inputs.json',dict(utc=now(),items=items,retained=retained,recovery=recovery,activity=gate))
    def verify(row):
        path=Path(row['path']);actual=sha(path)
        if actual!=row['expected_sha256'] or info(path)!=row['before']:
            raise ValueError('weight is modified or changed during verification: '+path.name)
        emit(event='PUBLIC_WEIGHT_VERIFIED',model=path.parent.name,file=path.name,bytes=row['before']['bytes'])
        return dict(row,actual_sha256=actual)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:verified=list(pool.map(verify,items))
    if len(verified)!=10:raise ValueError('exact ten shards required')
    activity_gate()
    for path,data in retained.items():
        if info(Path(path))!=data['before'] or sha(Path(path))!=data['sha256']:raise ValueError('retained metadata changed')
    value=dict(utc=now(),items=verified,retained=retained,recovery=recovery,activity_before=gate,
        allocated_bytes_to_reclaim=sum(x['before']['allocated_bytes'] for x in verified),
        payload_bytes_to_reclaim=sum(x['before']['bytes'] for x in verified),no_recursive_deletion=True)
    digest=save(root/'plan.json',value)
    emit(event='PREPARED_NO_DELETION_YET',root=str(root),plan_sha256=digest,
         shards=len(verified),allocated_bytes_to_reclaim=value['allocated_bytes_to_reclaim'])

def execute(root,expected_sha):
    root=root.resolve(strict=True)
    if root.parent!=BASE or not re.fullmatch(r'research-storage-cleanup-20260914-[a-z0-9_]+',root.name):raise ValueError('receipt scope')
    if sha(root/'plan.json')!=expected_sha:raise ValueError('plan changed')
    value=json.loads((root/'plan.json').read_text())
    expected_paths={str(BASE/'models'/name/f'model-{i:05}-of-{count:05}.safetensors') for name,_,count in TARGETS for i in range(1,count+1)}
    if len(value['items'])!=10 or {r['path'] for r in value['items']}!=expected_paths:raise ValueError('unexpected deletion target')
    gate=activity_gate()
    for row in value['items']:
        if info(Path(row['path']))!=row['before'] or row['actual_sha256']!=row['expected_sha256']:raise ValueError('target identity drift')
    save(root/'delete-intent.json',dict(utc=now(),plan_sha256=expected_sha,activity=gate))
    removed=[]
    for index,row in enumerate(value['items']):
        path=Path(row['path'])
        if path.resolve(strict=True)!=path or info(path)!=row['before']:raise ValueError('target changed before unlink')
        path.unlink()  # Only this exact verified single-link shard. No directory removal.
        removed.append(row['path'])
        save(root/f'deleted-{index:02}.json',dict(path=row['path'],utc=now(),former_allocated_bytes=row['before']['allocated_bytes']))
    for path,data in value['retained'].items():
        if info(Path(path))!=data['before'] or sha(Path(path))!=data['sha256']:raise ValueError('retained file changed')
    for path,data in gate['protected_files'].items():
        if info(Path(path))!=data:raise ValueError('protected model/image identity changed')
    result=dict(utc=now(),removed=removed,allocated_bytes_reclaimed=value['allocated_bytes_to_reclaim'],
        payload_bytes_removed=value['payload_bytes_to_reclaim'],retained_files_verified=len(value['retained']),
        current_critic_and_images_untouched=True,recovery=value['recovery'],plan_sha256=expected_sha)
    save(root/'reclaimed.json',result)
    emit(event='TEN_PUBLIC_SHARDS_REMOVED',**result)
    reserve=root/'capacity-40gib.tmp';fd=os.open(reserve,os.O_CREAT|os.O_EXCL|os.O_RDWR,0o600)
    try:
        os.posix_fallocate(fd,0,40*1024**3);os.fsync(fd)
        allocation=os.fstat(fd).st_blocks*512
        if allocation<40*1024**3:raise ValueError('sparse capacity test')
        capacity=dict(status='PASS_REAL_40_GIB_ALLOCATION',utc=now(),requested_bytes=40*1024**3,allocated_bytes=allocation)
    except OSError as e:
        capacity=dict(status='CAPACITY_FAILED',utc=now(),errno=e.errno,requested_bytes=40*1024**3)
    finally:
        own=os.fstat(fd);present=reserve.lstat()
        if (own.st_dev,own.st_ino)!=(present.st_dev,present.st_ino):raise ValueError('reservation identity changed')
        os.close(fd);reserve.unlink()
    capacity['temporary_reservation_released']=not reserve.exists()
    save(root/'capacity-after.json',capacity);emit(**capacity)

if __name__=='__main__':
    os.umask(0o077)
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','execute']);p.add_argument('--root',type=Path);p.add_argument('--plan-sha256')
    a=p.parse_args()
    if a.mode=='prepare':prepare()
    elif a.root is None or not a.plan_sha256:p.error('execute requires exact root and plan hash')
    else:execute(a.root,a.plan_sha256)
