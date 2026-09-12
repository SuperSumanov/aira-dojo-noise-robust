"""Read-only in-session observer. No auto-closeout, submit, retry or model call."""
import argparse
import importlib.util
import json
from pathlib import Path
import time

ROOT=Path('/research/d7/spc/yzyang4/forets-context-e2e-20260912-5xz0w6iy')


def main(watch):
    spec=importlib.util.spec_from_file_location('session',ROOT/'forets_environment_session_20260912.py')
    session=importlib.util.module_from_spec(spec);spec.loader.exec_module(session)
    previous=None
    while True:
        status=session.status(emit=False)
        structures=[]
        for run in status['runs']:
            checkpoint=ROOT/'runs'/run['run_id']/'checkpoint'
            structures.append(dict(run_id=run['run_id'],
                completed_contextual_pools=len(list((checkpoint/'forets-contextual-judge-private').glob('batch-*/finished.json')))))
        status['structures']=structures
        key=([ (r['run_id'],r['status'],r['attempt']) for r in status['runs'] ],
            status['job'].split('|')[1],structures,status['billing']['new_api_calls'])
        if key!=previous:print(json.dumps(status),flush=True);previous=key
        state=status['job'].split('|')[1].split()[0].rstrip('+')
        if not watch or state in {'COMPLETED','FAILED','CANCELLED','TIMEOUT','NODE_FAIL','OUT_OF_MEMORY','PREEMPTED','BOOT_FAIL'}:return
        time.sleep(45)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--watch',action='store_true');a=p.parse_args();main(a.watch)
