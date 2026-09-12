"""Build an isolated exact-source patch, NOT an activated paid e2e release."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

BASE='54e353963a6899965896b2e8ea492207829b3cbd'
PREFIX='src/dojo/core/interpreters/jupyter/'
EXPECTED={'jupyter_client.py':'a6c6abdca37745ce8d5137f48595a3c0e6332c113e8133b0782425b7bbb291bf',
          'jupyter_code_executor.py':'99681e6a519a14bcdcc0c56caacfb108760b73e98af71c5b054efe5dead9efc0'}


def patch_client(text):
    old='''    def wait_for_ready(self, timeout_seconds: float | None = None) -> bool:
        message_id = self._send_message(content={}, channel="shell", message_type="kernel_info_request")
        while True:
            message = self._receive_message(timeout_seconds)
            # This means we timed out with no new messages.
            if message is None:
                return False
            if (
                message.get("parent_header", {}).get("msg_id") == message_id
                and message["msg_type"] == "kernel_info_reply"
            ):
                return True
'''
    new='''    def wait_for_ready(self, timeout_seconds: float | None = None) -> bool:
        from .kernel_readiness import wait_for_ready
        return wait_for_ready(self, timeout_seconds)
'''
    if text.count(old)!=1:raise ValueError('client anchor mismatch')
    result=text.replace(old,new);ast.parse(result);return result


def patch_executor(text):
    old='''            return ExecutionResult(
                term_out=["ERROR:", "Kernel did not become ready in time."],
                exit_code=1,
                exec_time=time.monotonic() - start_time,
                timed_out=True,
            )'''
    new='''            from .kernel_readiness import KernelReadinessError
            raise KernelReadinessError("Kernel readiness failed before candidate dispatch")'''
    if text.count(old)!=1:raise ValueError('executor anchor mismatch')
    result=text.replace(old,new);ast.parse(result);return result


def build(output):
    repo=Path(__file__).resolve().parents[1]
    def git(*args,data=None,env=None):
        return subprocess.check_output(['git',*args],cwd=repo,input=data,env=env)
    changed={}
    for name,sha in EXPECTED.items():
        raw=git('show',BASE+':'+PREFIX+name)
        if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('source hash differs')
        changed[PREFIX+name]=(patch_client if name=='jupyter_client.py' else patch_executor)(raw.decode()).encode()
    helper=Path(__file__).with_name('forets_kernel_readiness_20260912.py').read_bytes().replace(b'\r\n',b'\n')
    ast.parse(helper);changed[PREFIX+'kernel_readiness.py']=helper
    with tempfile.TemporaryDirectory(prefix='forets-readiness-index-') as temp:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(temp)/'index'))
        git('read-tree',BASE,env=env)
        for name,raw in changed.items():
            blob=git('hash-object','-w','--stdin',data=raw).decode().strip()
            git('update-index','--add','--cacheinfo','100644,'+blob+','+name,env=env)
        tree=git('write-tree',env=env).decode().strip()
    files={}
    for line in git('ls-tree','-r',tree,'--','LICENSE','src/aira_core','src/dojo').decode().splitlines():
        head,name=line.split('\t');_,kind,blob=head.split()
        if kind!='blob':raise ValueError('unexpected source member')
        raw=git('cat-file','blob',blob);files[name]=hashlib.sha256(raw).hexdigest()
    archive=git('-c','core.autocrlf=false','archive','--format=tar',tree,'LICENSE','src/aira_core','src/dojo',
                env=dict(os.environ,GIT_LFS_SKIP_SMUDGE='1'))
    output.mkdir(exist_ok=False,parents=True)
    (output/'source.tar').write_bytes(archive)
    info=dict(base_source=BASE,source_tree=tree,controller_commit=git('rev-parse','HEAD').decode().strip(),
        changed_files=sorted(changed),source_files=files,archive_sha256=hashlib.sha256(archive).hexdigest(),
        paid_authorization_changed=False,activated=False,gpu_jobs=0,api_calls=0,
        purpose='readiness_stage_correction_only_not_runnable_paid_experiment')
    (output/'artifact.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in info.items() if k!='source_files'}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();build(a.output)
