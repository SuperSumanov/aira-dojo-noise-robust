"""Clean extraction and local regression from the exact published Git archive."""
import hashlib
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath

ROOT=Path('/tmp/mle-progress-20260930-NRPr0f')
ARCHIVE=ROOT/'parser-published-d11beb74.tar.gz'
PIN='eb94f34d74be507418948e05bba9ff5a4a2ead9b5ded56f49dbb4f93bc723224'
COMMIT='d11beb748f1f1fa654a88debd03b64f6457fbdfa'
DEST=ROOT/'published-d11beb74-clean-verification'


def main():
    assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()==PIN
    assert not DEST.exists()
    DEST.mkdir(mode=0o700)
    repo=DEST/'repo';repo.mkdir()
    with tarfile.open(ARCHIVE,'r:gz') as stream:
        members=stream.getmembers()
        assert len(members)<150
        assert sum(m.size for m in members)<16*1024**2
        assert all(not PurePosixPath(m.name).is_absolute() and '..' not in PurePosixPath(m.name).parts
                   and (m.isfile() or m.isdir()) for m in members)
        stream.extractall(repo,filter='data')
    env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1'
    env['OMP_NUM_THREADS']='1';env['OPENBLAS_NUM_THREADS']='1'
    script=repo/'phase1/scripts/comparison_0930_parser'
    bundle=repo/'phase1/patches/python_fence_parser_20261001'
    commands=[
        [sys.executable,'-B',str(script/'check_parser_publication_0930.py'),'--root',str(repo),'--output',str(DEST/'verified_manifest.json')],
        [sys.executable,'-B','-m','unittest','discover','-s',str(repo/'phase1/scripts/comparison_0930_feedback'),'-p','test_*.py'],
        [sys.executable,'-B','-m','unittest','discover','-s',str(script),'-p','test_*.py'],
        [sys.executable,'-B',str(script/'run_parser_regression_0930.py'),'--bundle',str(bundle),'--output',str(DEST/'native_regression.json')],
        [sys.executable,'-B',str(script/'parser_contract_matrix_20261001.py'),'--bundle',str(bundle),'--output',str(DEST/'contract_matrix.json')],
    ]
    records=[]
    for command in commands:
        output=subprocess.run(command,capture_output=True,text=True,env=env,cwd=repo,timeout=120)
        records.append({'command':command,'returncode':output.returncode,
                        'stdout':output.stdout,'stderr':output.stderr})
        assert output.returncode==0,records[-1]
    published=json.loads((repo/'phase1/results/comparison_0930_parser_20261001/manifest.json').read_text())
    new=json.loads((DEST/'verified_manifest.json').read_text())
    assert new==published
    prior_matrix=json.loads((repo/'phase1/results/comparison_0930_parser_20261001/contract_matrix.json').read_text())
    current_matrix=json.loads((DEST/'contract_matrix.json').read_text())
    assert prior_matrix==current_matrix
    native=json.loads((DEST/'native_regression.json').read_text())
    assert native['status']=='PASS' and native['tests_run']==17
    result={'status':'PASS','source_commit':COMMIT,'archive_sha256':PIN,
            'extracted_members':len(members),'manifest_exact_match':True,
            'contract_matrix_exact_match':True,'native_regression_tests':17,
            'commands':records,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'boundary':'Only the public package was extracted and tested under remote /tmp. No original journals, protected cohorts, models or candidate executions.'}
    with (DEST/'receipt.json').open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='commands'}))


if __name__=='__main__':main()
