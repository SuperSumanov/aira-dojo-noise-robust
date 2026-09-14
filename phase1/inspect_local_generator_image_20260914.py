"""Bounded CPU-only inspection of the delivered service image; never launch vLLM."""
import hashlib,json,os,re,subprocess
from pathlib import Path

ROOT=Path('/research/d7/spc/yzyang4/local-qwen27b-20260914-zcx1k1dy')
CODE=r'''
import importlib.metadata as m,json,pathlib,re
names=('vllm','torch','transformers')
versions={name:m.version(name) for name in names}
dist=m.distribution('vllm')
paths=[pathlib.Path(dist.locate_file(x)) for x in dist.files if str(x).startswith('vllm/') and str(x).endswith('.py')]
matches=[]
for path in paths:
    text=path.read_text(errors='replace')
    for i,line in enumerate(text.splitlines(),1):
        if 'VLLM_API_KEY' in line:
            matches.append(dict(file=str(path),line=i,text=line.strip()))
print('IMAGE_FACTS '+json.dumps(dict(versions=versions,api_key_environment_references=matches,
    package_code_imported=False,model_loaded=False,gpu_used=False)))
'''

def main():
    os.umask(0o077)
    if ROOT.resolve(strict=True)!=ROOT:raise ValueError('fixed root changed')
    raw=(ROOT/'image-complete.json').read_bytes();receipt=json.loads(raw)
    if not receipt.get('image_only') or len(receipt['files'])!=1:raise ValueError('image receipt')
    entry=receipt['files'][0];image=ROOT/'vllm.sif'
    if entry['path']!='vllm.sif' or entry['bytes']!=7939788800 or image.is_symlink() or image.stat().st_size!=entry['bytes']:
        raise ValueError('image size/path changed')
    prefix=['/usr/local/bin/singularity','exec','--containall','--cleanenv','--no-home',
        '--no-mount','bind-paths,cwd','--pwd','/tmp',str(image)]
    env={key:os.environ[key] for key in ('PATH','HOME','USER','LOGNAME') if key in os.environ}
    discover=subprocess.run(prefix+['/bin/sh','-c','command -v python3 vllm'],capture_output=True,text=True,timeout=20,env=env)
    print(json.dumps({'event':'image_executable_paths','exit_code':discover.returncode,
                      'paths':discover.stdout.splitlines()}))
    paths=discover.stdout.splitlines()
    if not paths or not re.fullmatch(r'/[A-Za-z0-9_./-]+python3',paths[0]):
        raise ValueError('image python3 executable not established')
    command=prefix+[paths[0],'-c',CODE]
    process=subprocess.run(command,capture_output=True,text=True,timeout=60,env=env)
    if re.search(r'(?i)(?:sk-[a-z0-9_.-]{12,}|Bearer\s+[a-z0-9_.-]{20,})',process.stdout+process.stderr):
        raise ValueError('unexpected credential shape; do not emit')
    lines=[x.removeprefix('IMAGE_FACTS ') for x in process.stdout.splitlines() if x.startswith('IMAGE_FACTS ')]
    if process.returncode or len(lines)!=1:
        print(json.dumps({'status':'IMAGE_INSPECTION_FAILED','exit_code':process.returncode,
                          'stderr_tail':process.stderr[-1500:],'gpu_jobs':0}))
        raise SystemExit(1)
    result=dict(status='IMAGE_METADATA_ONLY_NOT_SERVING_ACCEPTANCE',facts=json.loads(lines[0]),
        image_sha256=entry['digest'],image_bytes=entry['bytes'],
        completion_receipt_sha256=hashlib.sha256(raw).hexdigest(),actual_model_inference=False,gpu_jobs=0)
    with (ROOT/'image-inspection.json').open('x') as f:json.dump(result,f,sort_keys=True,indent=2)
    print(json.dumps(result))

if __name__=='__main__':main()
