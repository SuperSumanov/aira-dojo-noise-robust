"""Freeze a no-API completion readout before its once-only native submission."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
FILES=('readout_branching_completion_20260913.py','readout_forets_pool_completion_20260912.py','readout_forets_generation_capacity_20260912.py')
def main(root,commit,mode):
    sys.path.insert(0,str(root));import forets_pool_completion_20260912 as worker
    root,p=worker.checked(root)
    if p['commit']!=commit:raise ValueError('controller commit')
    readers={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in FILES}
    plan=dict(readers=readers,source_tree=p['source_tree'],programs=8,api_calls=0,root=str(root),commit=commit)
    if mode=='freeze':worker.write(root/'completion-readout-plan.json',plan)
    else:
        if json.loads((root/'completion-readout-plan.json').read_bytes())!=plan:raise ValueError('reader binding')
        worker.submit(root,commit)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('freeze','submit'));p.add_argument('root',type=Path);p.add_argument('commit');a=p.parse_args();main(a.root,a.commit,a.mode)
