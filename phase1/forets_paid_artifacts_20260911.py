"""Local reproducible Git tree construction; only public code/config artifacts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from forets_paid_patch_20260911 import patch

BASE='3aae90ae26b5ae7b65e6efed14fb49f2907c9c42'
PREFIX='src/dojo/core/solvers/llm_helpers/backends/'


def git(*args, data=None, env=None):
    return subprocess.run(['git',*args],input=data,capture_output=True,check=True,env=env).stdout


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(exist_ok=False)
    commit=git('rev-parse','HEAD').decode().strip()
    modified={PREFIX+'lite_llm.py':patch(git('show',BASE+':'+PREFIX+'lite_llm.py').decode()).encode()}
    for filename,target in [('forets_paid_budget_20260911.py','paid_budget.py'),
                            ('forets_paid_transport_20260911.py','paid_transport.py')]:
        modified[PREFIX+target]=git('show',commit+':phase1/'+filename)
    with tempfile.TemporaryDirectory(prefix='forets-paid-index-') as d:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(d)/'index'))
        git('read-tree',BASE,env=env)
        for name,raw in modified.items():
            digest=git('hash-object','-w','--stdin',data=raw).decode().strip()
            git('update-index','--add','--cacheinfo','100644,'+digest+','+name,env=env)
        tree=git('write-tree',env=env).decode().strip()
    archive=git('-c','core.autocrlf=false','archive','--format=tar',tree)
    (a.output/'source.tar').write_bytes(archive)
    inventory={}
    for row in git('ls-tree','-r',tree).decode().splitlines():
        header,name=row.split('\t'); mode,kind,blob=header.split()
        if kind!='blob':raise ValueError('unexpected tree entry')
        inventory[name]=hashlib.sha256(git('cat-file','blob',blob)).hexdigest()
    info=dict(base_tree=BASE,source_tree=tree,commit=commit,archive_sha256=hashlib.sha256(archive).hexdigest(),
              source_files=inventory)
    (a.output/'artifact.json').write_text(json.dumps(info,sort_keys=True,indent=2)+'\n')
    print(json.dumps(dict(source_tree=tree,commit=commit,files=len(inventory),archive_sha256=info['archive_sha256'])))


if __name__=='__main__':main()
