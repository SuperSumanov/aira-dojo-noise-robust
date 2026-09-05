"""Explicit recovery of a verified prefix; NO download, reinstall, GPU, system edit."""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from phase1.scripts.verify_private_cuda128_20260906 import ROOT,SOURCE,ARCHIVES,check,digest_file,archive_expected,verify_prefix


def main():
    commit=os.environ.get('CUDA_RECOVERY_COMMIT','')
    check(re.fullmatch('[0-9a-f]{40}',commit),'exact_recovery_commit')
    failure=json.loads((ROOT/'FAILURE.json').read_bytes())
    check(failure=={'automatic_retry':False,'reason':'compiler_validation_failed','status':'CUDA128_INSTALL_FAILED_CLOSED'},'original_failure')
    check((ROOT/'compile_only.txt').read_text()=="gcc: fatal error: cannot execute 'cc1plus': execvp: No such file or directory\ncompilation terminated.\nnvcc fatal   : Failed to preprocess host compiler properties.\n",'diagnosed_failure')
    check(not (ROOT/'INSTALL_COMPLETE.json').exists() and not (ROOT/'RECOVERY_COMPLETE.json').exists(),'no_completed_install')
    check(json.loads((ROOT/'intent.json').read_bytes())['source_commit']==SOURCE,'original_source')
    recovery=ROOT/'host-compiler-recovery';recovery.mkdir(mode=0o700)
    archives={}
    for name,(version,h,size) in ARCHIVES.items():
        p=ROOT/'archives'/f'{name}-linux-x86_64-{version}-archive.tar.xz'
        check(p.is_file() and not p.is_symlink() and p.stat().st_size==size and digest_file(p)==h,'archive_binding')
        archives[name]=p
    expected=archive_expected(archives)
    verify_prefix(ROOT/'prefix',expected,sealed=False)
    compiler=Path('/usr/bin/g++');frontend=Path('/usr/libexec/gcc/x86_64-linux-gnu/13/cc1plus')
    check(compiler.resolve()==Path('/usr/bin/x86_64-linux-gnu-g++-13') and frontend.is_file(),'host_compiler_inventory')
    env={'PATH':'/usr/bin:/bin','CUDA_VISIBLE_DEVICES':'','TMPDIR':str(ROOT/'validation')}
    host_version=subprocess.check_output([str(compiler),'--version'],env=env,timeout=10)
    check(b'13.' in host_version.splitlines()[0],'host_compiler_version')
    (recovery/'host_compiler_version.txt').write_bytes(host_version)
    intent={'source_commit':SOURCE,'recovery_commit':commit,'recovery_script_sha256':digest_file(Path(__file__)),
        'original_failure_sha256':digest_file(ROOT/'FAILURE.json'),'host_compiler':str(compiler),
        'host_compiler_sha256':digest_file(compiler),'host_frontend_sha256':digest_file(frontend),
        'archives_reused':True,'new_downloads':0,'compile_seconds_cap':60,'gpu_jobs':0,'model_runs':0}
    (recovery/'intent.json').write_text(json.dumps(intent,sort_keys=True,indent=2))
    test=ROOT/'validation/headers_and_kernel.cu';obj=ROOT/'validation/headers_and_kernel_r2.o'
    check(not obj.exists(),'new_object_required')
    argv=[str(ROOT/'prefix/bin/nvcc'),'-ccbin',str(compiler),'-arch=sm_86','-std=c++17','-c',str(test),'-o',str(obj)]
    (recovery/'command.json').write_text(json.dumps(argv))
    started=time.monotonic()
    with (ROOT/'compile_only_r2.txt').open('xb') as output:
        p=subprocess.Popen(argv,env=env,cwd=ROOT/'validation',stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
        try:rc=p.wait(timeout=60)
        except BaseException:
            try:os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            p.wait(timeout=10);raise
    with (ROOT/'compile_only_r2.rc.json').open('x') as out:json.dump({'returncode':rc,'seconds':time.monotonic()-started},out)
    check(rc==0 and obj.is_file(),'explicit_host_compile_failed')
    prefix=ROOT/'prefix'
    for p in sorted(prefix.rglob('*'),reverse=True):
        if p.is_symlink():continue
        p.chmod(0o555 if p.is_dir() or p.stat().st_mode&0o111 else 0o444)
    prefix.chmod(0o555)
    observed=verify_prefix(prefix,expected)
    with (ROOT/'installed_manifest.json').open('x') as out:json.dump(observed,out,sort_keys=True,indent=2)
    receipt={'status':'PRIVATE_CUDA128_EXPLICIT_HOST_COMPILER_RECOVERY_NOT_GPU_QUALIFICATION',
        **intent,'nvcc_host_compiler':str(compiler),'manifest_sha256':'daa0d766b36feaa933592162c27be5fb63b68fc547ca6886c160a35d96ee8891',
        'installed_manifest_sha256':digest_file(ROOT/'installed_manifest.json'),'nvcc_sha256':digest_file(prefix/'bin/nvcc'),
        'compiled_object_executed':False,'system_or_venv_modified':False,'production_training_admitted':False}
    with (ROOT/'RECOVERY_COMPLETE.json').open('x') as out:json.dump(receipt,out,sort_keys=True,indent=2)
    print(json.dumps(receipt,sort_keys=True))


if __name__=='__main__':
    os.umask(0o077)
    def expire(*_):raise TimeoutError('recovery_wall_cap_240_seconds')
    signal.signal(signal.SIGALRM,expire);signal.alarm(240)
    main()
