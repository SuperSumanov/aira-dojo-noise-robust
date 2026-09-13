"""Read-only independent request/fairness and runtime-readiness preflight."""
import ast
import json
import re
import sqlite3
from pathlib import Path
from decimal import Decimal
from contextlib import closing
import subprocess
import os
from run_repair_transfer_20260913 import ROOT, PARENT, SOURCE, TREE, OLD_AUTH, OLD_COUNTS, checked, source_check
from prepare_repair_transfer_20260913 import read, sha, ARMS, SECRET


def main():
    p=checked();source_check();secret_hits=0
    raw=read(ROOT/'inputs.private.json',p['private_input_sha256'])['rows']
    requests=[read(ROOT/'requests'/f'{r["index"]}.private.json',r['request_sha256']) for r in p['rows']]
    origins=read(ROOT/'selection-public.json')['rows']
    if len({(r['root'],r['run_id']) for r in origins})!=8:raise ValueError('case run independence')
    if len({r['ast_sha256'] for r in origins})!=8:raise ValueError('target AST aliases')
    for case in range(8):
        indices=[i for i,r in enumerate(raw) if r['case']==case]
        if len(indices)!=3 or {raw[i]['arm'] for i in indices}!=set(ARMS):raise ValueError('matrix')
        targets={(raw[i]['code'],raw[i]['error'],raw[i]['seed'],raw[i]['task']) for i in indices}
        if len(targets)!=1:raise ValueError('different target or seed across arms')
        baseline=next(i for i in indices if raw[i]['arm']=='no_external_memory')
        system=requests[baseline]['messages'][0]
        common={k:v for k,v in requests[baseline].items() if k!='messages'}
        for i in indices:
            q=requests[i]
            if q['messages'][0]!=system or {k:v for k,v in q.items() if k!='messages'}!=common:
                raise ValueError('model/tool/decoding/system differs across arms')
            actual=q['messages'][1]['content']
            # The original debug template conditionally emits this single block.
            if raw[i]['memory']:
                pattern=r'# Previous debugging attempts:\n````markdown\n'+re.escape(raw[i]['memory'])+r'\n````\n'
                actual,n=re.subn(pattern,'',actual)
                if n!=1:raise ValueError('memory not delivered exactly once')
            expected=requests[baseline]['messages'][1]['content']
            # Only blank-line runs surrounding the conditional block differ.
            normalize=lambda x:re.sub(r'\n{2,}','\n\n',x)
            if normalize(actual)!=normalize(expected):raise ValueError('non-memory user prompt difference')
            secret_hits+=len(SECRET.findall(json.dumps(q)))
            if raw[i]['code'] not in actual or raw[i]['error'] not in actual:raise ValueError('target context truncated')
    if secret_hits:raise ValueError('unsafe request')
    upper=(Decimal(102000)*Decimal('0.00000065')+Decimal(8192)*Decimal('0.0000026'))
    if upper>Decimal('.10'):raise ValueError('reservation price bound')
    with closing(sqlite3.connect((PARENT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        auth=db.execute('SELECT digest,stopped FROM auth').fetchall()
        counts=db.execute('SELECT COUNT(*),SUM(held),SUM(COALESCE(cost,0)),SUM(state="unresolved") FROM calls').fetchone()
    if auth!=[(OLD_AUTH,0)] or counts!=OLD_COUNTS:raise ValueError('predecessor not closed active ledger')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    queue=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i %T %j'],env=env,text=True,timeout=25)
    if any('RUNNING' in line or 'repair-transfer' in line for line in queue.splitlines()):raise ValueError('unexpected active/duplicate work')
    image=PARENT/'source'  # Exact source tree already verified; no GPU acceptance rerun.
    print(json.dumps(dict(status='PASS',source_tree=TREE,commit=p['commit'],requests=24,cases=8,
        paired_prompt_only_memory_difference=True,full_target_context=True,credential_shape_hits=secret_hits,
        conservative_request_cost_bound_usd=str(upper),reservation_usd='.10',
        planned_allocation_gpu_hours=4,old_unresolved_preserved=2,original_total_cap_usd=10,
        task_image_change=False,model_fit=False,protected_cohort_access=False,
        caveats=['Random and retrieved memory coincide in four cases; no exclusion/reselection.',
                 'Prompt length not matched; cost reported. This is not e2e, causal mediation, or clean learning verification.'])))


if __name__=='__main__':main()
