"""Build and verify a minimal patch against exact upstream Git blobs.

Only an isolated temporary repository is modified. Neither the research checkout
nor the senior branch is changed. The receipt binds source blobs and actual
post-apply file bytes, not merely a successful git-apply exit status.
"""
import argparse
import difflib
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

COMMIT='e385f863cb531904e611e987f7f71606796db656'
PATHS=['src/dojo/core/solvers/utils/response.py','src/dojo/utils/code_parsing.py',
       'src/dojo/utils/python_code_blocks.py']
BASELINE_EXTRA=['src/dojo/tasks/mlebench/task.py','src/dojo/core/interpreters/base.py']


def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True)
    ap.add_argument('--bundle',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();assert not a.output.exists();a.output.mkdir(parents=True)
    def git(*args):
        return subprocess.check_output(['git','-c','safe.directory='+a.repo.resolve().as_posix(),'-C',str(a.repo),*args])
    baseline={};blobs={};pieces=[]
    for path in PATHS[:2]+BASELINE_EXTRA:
        raw=git('show',COMMIT+':'+path)
        assert raw==(a.bundle/'baseline'/path).read_bytes(),path
        baseline[path]=raw;blobs[path]=git('rev-parse',COMMIT+':'+path).decode().strip()
    for path in PATHS:
        old=baseline.get(path,b'');new=(a.bundle/'candidate'/path).read_bytes()
        assert new.endswith(b'\n') and (not old or old.endswith(b'\n'))
        pieces.append('diff --git a/'+path+' b/'+path+'\n')
        if not old:pieces.append('new file mode 100644\n')
        pieces.extend(difflib.unified_diff(old.decode().splitlines(keepends=True),new.decode().splitlines(keepends=True),
                     fromfile='a/'+path if old else '/dev/null',tofile='b/'+path))
    patch=''.join(pieces).encode();patchfile=a.output/'fix_python_fences.patch';patchfile.write_bytes(patch)
    with tempfile.TemporaryDirectory(prefix='parser-fix-apply-') as tmp:
        root=Path(tmp);subprocess.run(['git','-c','core.autocrlf=false','init','-q',str(root)],check=True)
        for path,raw in baseline.items():
            p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        for check in [True,False]:
            command=['git','-c','core.autocrlf=false','-C',str(root),'apply']+(['--check'] if check else [])+[str(patchfile.resolve())]
            subprocess.run(command,check=True,capture_output=True)
        actual={}
        for path in PATHS:
            got=(root/path).read_bytes();expected=(a.bundle/'candidate'/path).read_bytes()
            assert got==expected, (path,sha(got),sha(expected),got.count(b'\r\n'),expected.count(b'\r\n'))
            compile(got.decode(),path,'exec');actual[path]=sha(got)
        for path in BASELINE_EXTRA:assert (root/path).read_bytes()==baseline[path]
    result={'status':'PASS','reference_commit':COMMIT,'baseline_git_blobs':blobs,
            'baseline_source_bytes_exact':True,'changed_production_paths':PATHS,
            'patch_sha256':sha(patch),'post_apply_file_sha256':actual,'actual_apply_verified':True,
            'script_sha256':sha(Path(__file__).read_bytes()),
            'scope':'Only an isolated temporary repository was patched. No production job or candidate execution.'}
    (a.output/'apply_receipt.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
