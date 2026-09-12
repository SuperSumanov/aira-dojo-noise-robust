"""Bind the proven eight-slot executor to both CLOSED seed14 first pools.

Writes controller code only. Preparing programs and submitting a GPU allocation
remain separate; no model/API call is introduced. Old diagnostic is untouched.
"""
import argparse
import ast
import hashlib
from pathlib import Path
import re

from forets_paid_patch_20260911 import once

PARENT='/research/d7/spc/yzyang4/forets-repeat-20260912-x3pkniqp'
TREE='f70eb4859c48c61bba37b298fbf8e32e367644ae'
PREPARED='111a28c1c12174c00451c737435028cf8528b386fea1f723392a34e648d6f40e'


def derive(source):
    edits=[("PARENT=BASE/'forets-review-20260912-csh5q4i8'","PARENT=Path('"+PARENT+"')"),
        ("REPEAT=BASE/'forets-repeat-20260912-zuvnt3oa'","REPEAT=PARENT"),
        ("PREPARED='e6ec9d4c6664a98a6c069b13cb85624ece78b864adf036591ed34f4c8df18718'","PREPARED='"+PREPARED+"'"),
        ("TREE='6ca01fba9892a350cbb24152054b5296dc7095f1'","TREE='"+TREE+"'"),
        ("FIXED_PLAN_SHA='08ac4d511382e78efb1a1c66e5cd4c4b12c3a92712e632068d9c15fb2f9773d9'","FIXED_PLAN_SHA='FROZEN_PLAN_SHA_REQUIRED'"),
        ("verification['job']!='13115'","verification['job']!='13124'"),
        ("cfg['solver']['selector_seed']!=11","cfg['solver']['selector_seed']!=14"),
        ("verified['job']!='13118' or verified['state']!='COMPLETED'","verified['job']!='13124' or verified['seed']!=14"),
        ("verified['verification']!='selected-node/external-grade consistency passed'","verified['verification']!='passed'"),
        ("if status.strip()!='13118|COMPLETED':raise ValueError('parent still active')",
         "if status.strip()!='13124|COMPLETED':raise ValueError('parent still active')\n"
         "    active=subprocess.check_output(['sacct','-X','-j','13128','-nP','--format=JobIDRaw,State'],text=True,timeout=25).strip().split('|')\n"
         "    if len(active)!=2 or active[0]!='13128' or active[1].split()[0].rstrip('+') not in ('COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED'):\n"
         "        raise ValueError('seed15 allocation still active; no extra resource contention')")]
    for old,new in edits:source=once(source,old,new)
    # All exact appearances are prose/labels or the matching scheduler receipt;
    # no program text, task-execution loop or scoring code is rewritten.
    for old,new,count in [('independent-final-verification.json','independent-context-verification.json',3),
        ("'-j','13118'","'-j','13124'",1),('forets-first-pools-s11','forets-context-pools-s14',1),
        ('seed=11','seed=14',3)]:
        if source.count(old)!=count:raise ValueError('unexpected diagnostic binding anchor '+old)
        source=source.replace(old,new)
    source=source.replace('seed11','seed14').replace('seed12','seed14')
    ast.parse(source)
    return source


def freeze(source,digest):
    if not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('exact prepared plan SHA required')
    return once(source,"FIXED_PLAN_SHA='FROZEN_PLAN_SHA_REQUIRED'","FIXED_PLAN_SHA='"+digest+"'")


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--plan-sha');a=p.parse_args()
    raw=Path(__file__).with_name('forets_current_pool_20260912.py').read_text(encoding='utf8')
    out=derive(raw)
    if a.plan_sha:out=freeze(out,a.plan_sha)
    with a.output.open('x',encoding='utf8',newline='\n') as f:f.write(out)
    print({'status':'CODE_ONLY','sha256':hashlib.sha256(out.encode()).hexdigest(),'api_calls':0,'gpu_jobs':0})
