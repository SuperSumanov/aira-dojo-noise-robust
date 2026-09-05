"""Independent archive-to-installed-file verification; CPU only, no installer calls."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import stat
import tarfile

ROOT=Path('/research/d7/spc/yzyang4/private-cuda128-toolchain-20260906')
SOURCE='7c0c06e1a1bdb355d35ab052da16e3454fde9198'
ARCHIVES={
    'cuda_cccl':('12.8.55','dce4f2e7720d4432ab0861ede2243f9cbd46bc675008932bc9dcdb871fc7d60b',925460),
    'cuda_cudart':('12.8.57','5bd3ac35ea8e8ab880e595d5054ee373abf6d9e53dcb8cef0a5c75358dbc0ae2',1343152),
    'cuda_nvcc':('12.8.61','145f8779bd56bdfa214447e5cb1b3a206ec1b7398da460e257f2898fd8604c54',79032992),
    'libcurand':('10.3.9.55','91923b0e38dc3d0e14c667800ebf95ee7cd290387effc7a0a559144004b5504f',88575908),
}


def check(condition,reason):
    if not condition:raise ValueError(reason)


def digest_file(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
    return h.hexdigest()


def archive_expected(archives):
    expected={}
    for component,path in sorted(archives.items()):
        with tarfile.open(path,'r:xz') as t:
            entries=t.getmembers(); top=path.name.removesuffix('.tar.xz')
            directories={m.name.rstrip('/') for m in entries if m.isdir()}
            def mapped(relative,is_directory):
                return str(PurePosixPath('share/components')/component/relative) if '/' not in relative and not is_directory else relative
            for m in entries:
                name=m.name.rstrip('/')
                check(name==top or name.startswith(top+'/'),'archive_top')
                check(m.isdir() or m.isfile() or m.issym(),'archive_type')
                if m.isdir():continue
                relative=name[len(top)+1:]
                check(relative and '..' not in PurePosixPath(relative).parts,'archive_relative_path')
                if m.issym():
                    target=posixpath.normpath(posixpath.join(posixpath.dirname(relative),m.linkname))
                    check(not target.startswith('/') and '..' not in PurePosixPath(target).parts,'archive_link')
                    target_is_dir=top+'/'+target in directories
                    destination=mapped(relative,target_is_dir)
                    mapped_target=mapped(target,target_is_dir)
                    row={'kind':'symlink','target':posixpath.relpath(mapped_target,posixpath.dirname(destination) or '.')}
                else:
                    destination=mapped(relative,False)
                    h=hashlib.sha256()
                    with t.extractfile(m) as stream:
                        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
                    row={'kind':'file','bytes':m.size,'sha256':h.hexdigest(),'mode':0o555 if m.mode&0o111 else 0o444}
                check(destination not in expected or expected[destination]==row,'archive_destination_collision')
                expected[destination]=row
    if any(k.startswith('lib/') for k in expected) and 'lib64' not in expected and not any(k.startswith('lib64/') for k in expected):
        expected['lib64']={'kind':'symlink','target':'lib'}
    return expected


def verify_prefix(prefix,expected,*,sealed=True):
    check(prefix.is_dir() and prefix.resolve()==prefix and (not sealed or not prefix.stat().st_mode&0o222),'prefix_readonly')
    observed={}
    for p in sorted(prefix.rglob('*')):
        st=p.lstat();name=p.relative_to(prefix).as_posix()
        check(st.st_uid==os.getuid(),'prefix_owner')
        if stat.S_ISLNK(st.st_mode):
            check(p.exists() and p.resolve().is_relative_to(prefix),'prefix_link_escape')
            observed[name]={'kind':'symlink','target':os.readlink(p)}
        elif stat.S_ISDIR(st.st_mode):check(not st.st_mode&(0o222 if sealed else 0o022),'directory_writable')
        else:
            check(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and not st.st_mode&(0o222 if sealed else 0o022),'prefix_regular_readonly')
            observed[name]={'kind':'file','bytes':st.st_size,'sha256':digest_file(p),'mode':stat.S_IMODE(st.st_mode)&~0o222}
    check(observed==expected,'archive_prefix_mismatch')
    return observed


def main():
    check(ROOT.resolve()==ROOT and ROOT.stat().st_uid==os.getuid(),'installation_root')
    recovery=(ROOT/'RECOVERY_COMPLETE.json').is_file()
    check(recovery or not (ROOT/'FAILURE.json').exists(),'installation_failed')
    complete_path=ROOT/('RECOVERY_COMPLETE.json' if recovery else 'INSTALL_COMPLETE.json')
    complete=json.loads(complete_path.read_bytes())
    intent=json.loads((ROOT/'intent.json').read_bytes())
    check(complete['source_commit']==intent['source_commit']==SOURCE,'source_binding')
    if recovery:
        check(digest_file(ROOT/'FAILURE.json')==complete['original_failure_sha256'],'failure_preserved')
        check(complete['nvcc_host_compiler']=='/usr/bin/g++','explicit_host_compiler')
    check(complete['gpu_jobs']==complete['model_runs']==0 and complete['system_or_venv_modified'] is False
          and complete['compiled_object_executed'] is False and complete['production_training_admitted'] is False,'scope')
    check(complete['manifest_sha256']=='daa0d766b36feaa933592162c27be5fb63b68fc547ca6886c160a35d96ee8891','official_manifest')
    check(digest_file(ROOT/'installed_manifest.json')==complete['installed_manifest_sha256'],'manifest_binding')
    archives={}
    for component,(version,h,size) in ARCHIVES.items():
        p=ROOT/'archives'/f'{component}-linux-x86_64-{version}-archive.tar.xz'
        check(p.is_file() and not p.is_symlink() and p.stat().st_size==size and digest_file(p)==h,'archive_hash')
        archives[component]=p
    expected=archive_expected(archives)
    observed=verify_prefix(ROOT/'prefix',expected)
    check(observed==json.loads((ROOT/'installed_manifest.json').read_bytes()),'installer_manifest_disagrees')
    for label in ('nvcc_version','compile_only_r2' if recovery else 'compile_only'):
        check(json.loads((ROOT/(label+'.rc.json')).read_bytes())['returncode']==0,'compile_receipt')
    check(b'V12.8.61' in (ROOT/'nvcc_version.txt').read_bytes(),'compiler_version')
    obj=ROOT/('validation/headers_and_kernel_r2.o' if recovery else 'validation/headers_and_kernel.o')
    check(obj.is_file() and obj.stat().st_size>0,'compiled_object')
    receipt={'status':'INDEPENDENT_ARCHIVE_PREFIX_MATCH_NOT_GPU_QUALIFICATION','source_commit':SOURCE,
        'verifier_sha256':digest_file(Path(__file__)),'installed_manifest_sha256':digest_file(ROOT/'installed_manifest.json'),
        'install_complete_sha256':digest_file(complete_path),'recovered_original_failure':recovery,'archives_verified':len(archives),
        'files_verified':sum(r['kind']=='file' for r in observed.values()),
        'links_verified':sum(r['kind']=='symlink' for r in observed.values()),
        'nvcc_sha256':digest_file(ROOT/'prefix/bin/nvcc'),'compiled_object_sha256':digest_file(obj),
        'gpu_context_created':False,'model_fit':False,'production_training_admitted':False}
    with (ROOT/'INDEPENDENT_VERIFIED.json').open('x') as stream:json.dump(receipt,stream,sort_keys=True,indent=2)
    print(json.dumps(receipt,sort_keys=True))


if __name__=='__main__':main()
