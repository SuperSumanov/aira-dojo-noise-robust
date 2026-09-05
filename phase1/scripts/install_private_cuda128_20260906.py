"""Hash-fixed NVIDIA components in a NEW private prefix; never modifies a venv.

Not a general CUDA installer, driver installer, task submitter or GPU validator.
Only official component archives are executed (nvcc); test objects are compiled,
never loaded or executed. Successful downloads are retained for explicit recovery.
"""
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import signal
import stat
import subprocess
import tarfile
import time

ROOT = Path('/research/d7/spc/yzyang4/private-cuda128-toolchain-20260906')
MANIFEST = Path('/tmp/nvidia-cuda128-manifest-20260906.json')
MANIFEST_SHA = 'daa0d766b36feaa933592162c27be5fb63b68fc547ca6886c160a35d96ee8891'
BASE = 'https://developer.download.nvidia.com/compute/cuda/redist/'
COMPONENTS = {
    'cuda_cccl': ('12.8.55', 'dce4f2e7720d4432ab0861ede2243f9cbd46bc675008932bc9dcdb871fc7d60b', 925460),
    'cuda_cudart': ('12.8.57', '5bd3ac35ea8e8ab880e595d5054ee373abf6d9e53dcb8cef0a5c75358dbc0ae2', 1343152),
    'cuda_nvcc': ('12.8.61', '145f8779bd56bdfa214447e5cb1b3a206ec1b7398da460e257f2898fd8604c54', 79032992),
    'libcurand': ('10.3.9.55', '91923b0e38dc3d0e14c667800ebf95ee7cd290387effc7a0a559144004b5504f', 88575908),
}
DISK_CAP = 1610612736


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def write_record(name, value):
    with (ROOT/name).open('x') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)


def validated_members(members, top):
    require(0 < len(members) <= 30000, 'archive_member_count')
    seen, estimated = set(), 0
    for member in members:
        name = member.name.rstrip('/')
        p = PurePosixPath(name)
        require(str(p) == name and p.parts and p.parts[0] == top and
                not p.is_absolute() and '..' not in p.parts and '\\' not in name and
                all(ord(c) >= 32 for c in name) and name not in seen, 'archive_member_path')
        seen.add(name)
        require(member.isdir() or member.isfile() or member.issym(), 'archive_member_type')
        require(not member.islnk() and member.size >= 0, 'archive_hardlink_or_size')
        estimated += max(4096, math.ceil(member.size/4096)*4096)
        if member.issym():
            link = member.linkname
            require(link and not PurePosixPath(link).is_absolute() and '\\' not in link
                    and all(ord(c) >= 32 for c in link), 'archive_link_path')
            target = PurePosixPath(posixpath.normpath(str(p.parent/link)))
            require(target.parts and target.parts[0] == top and '..' not in target.parts,
                    'archive_link_escape')
    return estimated


def merge_component(source, prefix, component):
    """Copy files before creating links. Preserve component-root documentation."""
    def mapped(relative, is_dir=False):
        p = PurePosixPath(relative)
        return PurePosixPath('share/components', component)/p if len(p.parts)==1 and not is_dir else p
    paths = sorted(source.rglob('*'))
    links = []
    for p in paths:
        relative = p.relative_to(source).as_posix()
        if p.is_symlink():
            original_target = PurePosixPath(posixpath.normpath(str(PurePosixPath(relative).parent/os.readlink(p))))
            require(not original_target.is_absolute() and '..' not in original_target.parts, 'merge_link_escape')
            # Root-level links may name directories. Keep their semantic role.
            destination = mapped(relative, p.is_dir())
            target = mapped(str(original_target), (source/str(original_target)).is_dir())
            links.append((destination, posixpath.relpath(str(target), str(destination.parent))))
            continue
        target = prefix/str(mapped(relative, p.is_dir()))
        require(not any(x.is_symlink() for x in (target, *target.parents)), 'merge_symlink_ancestor')
        if p.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            require(p.is_file() and p.stat().st_nlink==1, 'merge_regular_file')
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                require(target.is_file() and target.stat().st_size==p.stat().st_size and sha(target)==sha(p),
                        'merge_nonidentical_collision')
            else:
                shutil.copyfile(p, target)
                target.chmod(0o755 if p.stat().st_mode & 0o111 else 0o644)
    return links


def run_bounded(argv, label):
    log = ROOT/(label+'.txt')
    with log.open('xb') as stream:
        child = subprocess.Popen(argv, stdout=stream, stderr=subprocess.STDOUT,
            env={'PATH':'/usr/local/bin:/usr/bin:/bin','CUDA_VISIBLE_DEVICES':'','TMPDIR':str(ROOT/'validation')},
            cwd=ROOT/'validation', start_new_session=True)
        try:
            rc = child.wait(timeout=60)
        except BaseException:
            try: os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            child.wait(timeout=10)
            raise
    write_record(label+'.rc.json', {'returncode':rc})
    require(rc==0, 'compiler_validation_failed')


def main():
    require(os.name=='posix' and ROOT.parent.resolve()==ROOT.parent and not ROOT.exists(), 'new_private_root_required')
    commit = os.environ.get('CUDA_INSTALL_CODE_COMMIT','')
    require(re.fullmatch('[0-9a-f]{40}',commit), 'source_commit_required')
    require(sha(MANIFEST)==MANIFEST_SHA, 'official_manifest_changed')
    space = Path('/research/d7/spc/yzyang4/cuda128-storage-check-20260906/receipt.json')
    require(sha(space)=='6989ff298b58f1d2f43e67e2b4f87ac1147413f6cad168b84dddb8a68877d67d', 'allocation_check_binding')
    receipt = json.loads(space.read_bytes())
    require(receipt['status']=='CUDA_TOOLCHAIN_SPACE_CHECK_PASSED' and receipt['allocated_bytes']>=DISK_CAP,
            'allocation_check_failed')
    official = json.loads(MANIFEST.read_bytes())
    require(official['release_label']=='12.8.0' and official['release_product']=='cuda', 'official_release')
    ROOT.mkdir(mode=0o700)
    for name in ('archives','staging','prefix','validation'):
        (ROOT/name).mkdir(mode=0o700)
    write_record('intent.json', {'source_commit':commit,'installer_sha256':sha(Path(__file__)),
        'manifest_sha256':MANIFEST_SHA,'disk_cap_bytes':DISK_CAP,'gpu_jobs':0,'model_runs':0,
        'modify_system_or_venv':False,'wall_cap_seconds':900})
    import requests
    session = requests.Session()
    archives = {}
    for component, (version,digest,size) in COMPONENTS.items():
        selected=official[component]['linux-x86_64']
        relative=f'{component}/linux-x86_64/{component}-linux-x86_64-{version}-archive.tar.xz'
        require(official[component]['version']==version and selected['relative_path']==relative
                and selected['sha256']==digest and int(selected['size'])==size, 'component_binding')
        target=ROOT/'archives'/Path(relative).name
        partial=target.with_suffix(target.suffix+'.partial')
        with session.get(BASE+relative, stream=True, timeout=(10,30), allow_redirects=False, verify=True) as response:
            require(response.status_code==200, 'component_download_status')
            received=0
            with partial.open('xb') as stream:
                for block in response.iter_content(1<<20):
                    received+=len(block)
                    require(received<=size, 'component_oversize')
                    stream.write(block)
        require(received==size and sha(partial)==digest, 'component_size_or_hash')
        partial.rename(target)
        archives[component]=target
        print(json.dumps({'downloaded_component':component,'bytes':size,'sha256_verified':True}),flush=True)
    blocks=0
    for component, target in archives.items():
        with tarfile.open(target,'r:xz') as tar:
            blocks+=validated_members(tar.getmembers(), target.name[:-7])
    compressed=sum(p.stat().st_size for p in archives.values())
    require(compressed+2*blocks+64*1024**2<=DISK_CAP, 'unpacked_disk_budget')
    write_record('archive_inventory.json', {'compressed_bytes':compressed,'estimated_component_blocks':blocks,
        'estimated_peak_bytes':compressed+2*blocks+64*1024**2,'disk_cap_bytes':DISK_CAP})
    links={}
    prefix=ROOT/'prefix'
    for component, target in archives.items():
        folder=ROOT/'staging'/component
        folder.mkdir(mode=0o700)
        with tarfile.open(target,'r:xz') as tar:
            members=tar.getmembers()
            validated_members(members,target.name[:-7])
            tar.extractall(folder,members=members,filter='data')
        source=folder/target.name[:-7]
        require(source.is_dir() and source.resolve()==source, 'extracted_component_root')
        for name, link in merge_component(source,prefix,component):
            key=str(name)
            require(key not in links or links[key]==link, 'merge_link_collision')
            links[key]=link
    for name, link in sorted(links.items()):
        destination=prefix/name
        require(not destination.exists() and not destination.is_symlink(), 'merge_link_file_collision')
        require(not any(p.is_symlink() for p in destination.parents), 'merge_link_parent')
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.symlink_to(link)
    if not (prefix/'lib64').exists() and (prefix/'lib').is_dir():
        (prefix/'lib64').symlink_to('lib',target_is_directory=True)
    for p in prefix.rglob('*'):
        if p.is_symlink():
            require(p.exists() and p.resolve().is_relative_to(prefix), 'installed_link_escape_or_dangling')
    for name in ('bin/nvcc','include/cuda.h','include/cuda_runtime.h','lib64/libcudart.so','lib64/libcurand.so'):
        require((prefix/name).is_file(), 'required_toolchain_file_missing')
    run_bounded([str(prefix/'bin/nvcc'),'--version'],'nvcc_version')
    version=(ROOT/'nvcc_version.txt').read_bytes()
    require(re.search(rb'release 12\.8[,\s]',version) and b'V12.8.61' in version, 'wrong_compiler_version')
    test=ROOT/'validation'/'headers_and_kernel.cu'
    test.write_text('#include <cuda.h>\n#include <cuda_runtime.h>\n#include <cuda_fp16.h>\n#include <cuda_bf16.h>\n#include <curand.h>\nstatic_assert(CUDART_VERSION == 12080);\n__global__ void check(float *x) { if(threadIdx.x == 0) *x = 1.0f; }\n')
    run_bounded([str(prefix/'bin/nvcc'),'-arch=sm_86','-std=c++17','-c',str(test),'-o',str(test.with_suffix('.o'))], 'compile_only')
    require(test.with_suffix('.o').is_file(), 'compiled_object_missing')
    installed={}
    for p in sorted(prefix.rglob('*')):
        relative=p.relative_to(prefix).as_posix()
        if p.is_symlink():
            installed[relative]={'kind':'symlink','target':os.readlink(p)}
        elif p.is_file():
            p.chmod(0o555 if p.stat().st_mode&0o111 else 0o444)
            installed[relative]={'kind':'file','bytes':p.stat().st_size,'sha256':sha(p),'mode':stat.S_IMODE(p.stat().st_mode)}
    for p in sorted((p for p in prefix.rglob('*') if p.is_dir() and not p.is_symlink()),reverse=True):
        p.chmod(0o555)
    prefix.chmod(0o555)
    write_record('installed_manifest.json',installed)
    actual_blocks=ROOT.lstat().st_blocks*512+sum(p.lstat().st_blocks*512 for p in ROOT.rglob('*'))
    require(actual_blocks+65536<=DISK_CAP, 'actual_disk_budget')
    write_record('INSTALL_COMPLETE.json',{'status':'PRIVATE_CUDA128_COMPILED_OBJECT_NOT_GPU_QUALIFICATION',
        'source_commit':commit,'manifest_sha256':MANIFEST_SHA,'installed_manifest_sha256':sha(ROOT/'installed_manifest.json'),
        'prefix':str(prefix),'files_and_links':len(installed),'nvcc_sha256':sha(prefix/'bin/nvcc'),
        'allocated_blocks_before_completion_receipt_bytes':actual_blocks,'gpu_jobs':0,'model_runs':0,'compiled_object_executed':False,
        'system_or_venv_modified':False,'production_training_admitted':False})
    print(json.dumps(json.loads((ROOT/'INSTALL_COMPLETE.json').read_bytes()),sort_keys=True),flush=True)


if __name__=='__main__':
    os.umask(0o077)
    def expire(signum, frame): raise TimeoutError('overall_install_deadline')
    signal.signal(signal.SIGALRM,expire);signal.alarm(900)
    try:
        main()
    except Exception as exc:
        reason=str(exc) if type(exc) is RuntimeError and re.fullmatch('[a-z_]+',str(exc)) else type(exc).__name__
        value={'status':'CUDA128_INSTALL_FAILED_CLOSED','reason':reason,'automatic_retry':False}
        if ROOT.is_dir() and not (ROOT/'FAILURE.json').exists(): write_record('FAILURE.json',value)
        print(json.dumps(value),flush=True)
        raise SystemExit(1)
