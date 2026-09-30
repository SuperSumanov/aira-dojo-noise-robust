"""Bind the four extraction/admission source files to every recorded producer ref."""
import argparse,collections,csv,hashlib,json,subprocess
from pathlib import Path

REFERENCE='e385f863cb531904e611e987f7f71606796db656'
PATHS=['src/dojo/core/solvers/utils/response.py','src/dojo/utils/code_parsing.py',
       'src/dojo/tasks/mlebench/task.py','src/dojo/core/interpreters/base.py']


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True)
    ap.add_argument('--per-run',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();rows=list(csv.DictReader(a.per_run.open()))
    commits=collections.Counter(r['producer_commit'] for r in rows)
    def git(*args):return subprocess.check_output(['git','-c','safe.directory='+a.repo.resolve().as_posix(),'-C',str(a.repo),*args])
    ref={p:git('rev-parse',REFERENCE+':'+p).decode().strip() for p in PATHS}
    results=[]
    for commit,count in sorted(commits.items()):
        full=git('rev-parse','--verify',commit+'^{commit}').decode().strip()
        blobs={p:git('rev-parse',commit+':'+p).decode().strip() for p in PATHS}
        assert blobs==ref
        results.append({'metadata_commit':commit,'resolved_commit':full,'directories':count,'git_blobs':blobs,'all_reference_blobs_equal':True})
    result={'status':'PASS','reference_commit':REFERENCE,'producer_refs':results,
            'per_run_sha256':hashlib.sha256(a.per_run.read_bytes()).hexdigest(),
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'boundary':'Recorded commit source equality, not proof of absence of uncommitted production edits or exact historical Python/package environment.'}
    with a.output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
