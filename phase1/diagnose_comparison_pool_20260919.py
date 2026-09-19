"""After closure: error names only and selected-program replay consistency.

No raw program output/code is exported. This diagnoses, never repairs/retries.
"""
import argparse,hashlib,json,re
from collections import Counter
from pathlib import Path

KNOWN={'ValueError','TypeError','KeyError','IndexError','AttributeError','NameError',
       'ImportError','ModuleNotFoundError','FileNotFoundError','RuntimeError',
       'MemoryError','SyntaxError','AssertionError','OSError','PermissionError',
       'ZeroDivisionError','OutOfMemoryError','XGBoostError','CatBoostError','LightGBMError'}
OLD=Path('/research/d7/spc/yzyang4/comparison-quarantine-20260919-_tda9fh6/qwen-readout-v1/nodes.json')
OLD_SHA='370976e31c8a9f501bc75fb7826f529f85b0e34059146291f2e7bb3cab4062c9'


def exception_name(text):
    names=re.findall(r'^\s*(?:[a-zA-Z_][\w.]*\.)?([a-zA-Z_][\w]*(?:Error|Exception))\s*:',text,re.M)
    return names[-1] if names and names[-1] in KNOWN else 'unclassified_program_failure'


def main(root):
    raw=(root/'summary.json').read_bytes();summary=json.loads(raw)
    if summary['allocation_state'].split()[0].rstrip('+') not in {'COMPLETED','FAILED','CANCELLED','TIMEOUT','NODE_FAIL','OUT_OF_MEMORY','PREEMPTED'}:
        raise ValueError('not closed')
    oldraw=OLD.read_bytes()
    if hashlib.sha256(oldraw).hexdigest()!=OLD_SHA:raise ValueError('historical export changed')
    old={(n['run'],n['id']):n for n in json.loads(oldraw)}
    rows=[]
    for r in summary['rows']:
        row={k:r[k] for k in ('seed','slot','node','original_selected','status','valid')}
        if r['valid'] is False:
            if r.get('timed_out'):row['failure_category']='program_timeout'
            elif r.get('exit_code')==0:row['failure_category']='returned_without_valid_submission'
            else:
                log=root/('output-'+str(r['index'])+'.private.log')
                if log.is_symlink():raise ValueError('unexpected log symlink')
                with log.open('rb') as handle:
                    handle.seek(0,2);length=handle.tell();handle.seek(max(0,length-65536))
                    row['failure_category']=exception_name(handle.read().decode(errors='replace'))
        if r['original_selected']:
            n=old[(r['run'],r['node'])]
            if n['code_sha256']!=r['raw_code_sha256']:raise ValueError('historical code drift')
            row.update(historical_buggy=n['is_buggy'],historical_recorded_grade=n['score'],fresh_grade=r['score'],
                caveat='Historical grade/buggy state is not identical to fresh validation; environments/hardware differ.')
        rows.append(row)
    result=dict(summary_sha256=hashlib.sha256(raw).hexdigest(),rows=rows,
        failure_categories=dict(Counter(r['failure_category'] for r in rows if 'failure_category' in r)),
        caveat='Exception names are coarse diagnostics, not proven causes; no program has been repaired or replaced.')
    with (root/'diagnostic.json').open('x') as handle:json.dump(result,handle,indent=2,allow_nan=False)
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);main(p.parse_args().root)
