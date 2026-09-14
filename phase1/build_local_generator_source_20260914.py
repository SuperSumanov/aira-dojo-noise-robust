"""Build a new source archive; never edit a closed experiment or senior branch."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from local_generator_adapter_20260914 import patch

BASE='b7f8ab0f65dba9877ac3af35e3e770fc32546565'
PREFIX='src/dojo/core/solvers/llm_helpers/backends/'

def git(*args, data=None, env=None):
    return subprocess.run(['git',*args],input=data,env=env,capture_output=True,check=True).stdout

def build(output):
    output.mkdir(exist_ok=False)
    original=git('show',BASE+':'+PREFIX+'lite_llm.py').decode()
    changes={PREFIX+'lite_llm.py':patch(original).encode(),
             PREFIX+'selfhosted_guard.py':Path(__file__).with_name('forets_selfhosted_guard_20260912.py').read_bytes()}
    with tempfile.TemporaryDirectory(prefix='local-generator-index-') as temporary:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(temporary)/'index'),GIT_LFS_SKIP_SMUDGE='1')
        git('read-tree',BASE,env=env)
        for name,raw in changes.items():
            blob=git('hash-object','-w','--stdin',data=raw).decode().strip()
            git('update-index','--add','--cacheinfo','100644,'+blob+','+name,env=env)
        tree=git('write-tree',env=env).decode().strip()
    payload=git('-c','core.autocrlf=false','archive','--format=tar',tree,'src/dojo','src/aira_core')
    with (output/'source.tar').open('xb') as f:f.write(payload)
    record=dict(base_tree=BASE,source_tree=tree,archive_sha256=hashlib.sha256(payload).hexdigest(),archive_bytes=len(payload),
        changed_files={name:hashlib.sha256(raw).hexdigest() for name,raw in changes.items()},
        model='cyankiwi/Qwen3.8-27B-AWQ-BF16-INT4',revision='dc430725f831dd90d9271738b877879a46a82239',
        constructor_and_bounded_transport_only=True,closed_source_changed=False,gpu_or_inference_started=False)
    with (output/'source.json').open('x') as f:json.dump(record,f,indent=2,sort_keys=True)
    print(json.dumps(record))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();build(a.output)
