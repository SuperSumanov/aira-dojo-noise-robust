"""Fixed all-row reinspection of the previously qualified development edits.

These development runs were already analyzed historically; this is not a new blind
validation set. Current extraction/selection ignores scores and preserves all rows.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import sys

import collateral_sample_20261006 as c
import collateral_bindings_20261006 as b

BASE=Path('/research/d7/spc/yzyang4')
SRC=BASE/'edit-factorization-census-20261002-v1'
OUT=BASE/'collateral-local-20261006-v2'
ROOTS={
 'task-feedback-real-20261001-v6':'15751d3b52bdc42617df02006ce724635f4bf49df6e477686769fd1979d53403',
 'task-feedback-upper-20261002-v1':'9fe231e1b9e2da8cb51fadb7ff9844b074c10e8e3dc64d1d1f3be170fb0703a0',
 'task-feedback-local-edit-20261002-v1':'7bd84ff0e867043b2787d5c07af867eff50370f4e7b6bafa811ef215196c4139',
}
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')


def main():
    os.umask(0o077)
    raw=(SRC/'summary.json').read_bytes();data=json.loads(raw)
    assert data['status']=='STRUCTURAL_ONLY_NO_EXECUTION_OR_EFFECT'
    sys.path.insert(0,str(BASE/'task-feedback-real-20261001-v6'))
    import task_feedback_real_20261001 as runtime
    runtime.setup()
    from dojo.utils.code_parsing import extract_code
    OUT.mkdir(mode=0o700,exist_ok=False)
    c.save(OUT/'plan.json',dict(source_summary_sha256=c.digest(raw),root_plan_pins=ROOTS,
        source_script_sha256=c.digest(Path(__file__).read_bytes()), selection='Every row in old structural census; no outcome-based filtering',
        protected_access=False, model_fits=0, gpu_hours=0, generator_calls=0,boundary=__doc__))
    rows=[];seen=set()
    for i,r in enumerate(data['rows']):
        root=BASE/r['batch']
        assert c.digest((root/'plan.json').read_bytes())==ROOTS[r['batch']]
        assert (root/'all-closed.json').exists()
        out={k:r[k] for k in ('batch','task','episode','step','parent_step','arm','generation_seed')}
        codes=[]
        for step,key in ((r['parent_step'],'parent_raw_sha256'),(r['step'],'child_raw_sha256')):
            raw=(root/f"episode-{r['episode']}"/f'action-{step}/node.private.json').read_bytes()
            assert not SECRET.search(raw)
            code=json.loads(raw)['code'];assert c.digest(code)==r[key]
            try:
                code=extract_code(code);ast.parse(code)
            except Exception:  # Native extractor uses generic Exception on invalid Python.
                code=None
            codes.append(code)
        if None in codes:
            rows.append(dict(**out,status='EXTRACTION_OR_PARSE_UNSUPPORTED'));continue
        a,z=codes;pair=c.digest(a),c.digest(z)
        out.update(parent_sha256=pair[0],child_sha256=pair[1],duplicate_pair=pair in seen)
        seen.add(pair)
        out['direct']=c.inspect_pair(a,z);out['bindings']=b.compare(a,z)
        out['status']='PARSED'
        if out['direct']['numeric_changes'] or out['bindings']['changes']:
            folder=OUT/f'{i:03d}.private';folder.mkdir()
            for n,code in zip(('parent','child'),codes):
                with (folder/(n+'.py')).open('x') as f:f.write(code)
            out['private_index']=i
        rows.append(out)
    counts=dict(rows=len(rows),parsed=sum(r['status']=='PARSED' for r in rows),unique_pairs=len(seen),
        rows_with_numeric_changes=sum('private_index' in r for r in rows),
        unique_changed_pairs=len({(r['parent_sha256'],r['child_sha256']) for r in rows if 'private_index' in r}))
    c.save(OUT/'summary.json',dict(counts=counts,rows=rows,boundary=__doc__))
    print(json.dumps(dict(counts=counts,summary_sha256=c.digest((OUT/'summary.json').read_bytes()))))


if __name__=='__main__':main()
