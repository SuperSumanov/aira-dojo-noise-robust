"""Independent, post-terminal consistency check of job 13115 DEVELOPMENT finals.

Not a numerical regrade: the unmodified task removes submission CSVs. No old
result is rescued and no other cohort, run, model or API is opened.
"""
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import subprocess

ROOT=Path('/research/d7/spc/yzyang4/forets-review-20260912-csh5q4i8')
PREPARED='e6ec9d4c6664a98a6c069b13cb85624ece78b864adf036591ed34f4c8df18718'
TREE='6ca01fba9892a350cbb24152054b5296dc7095f1'
SECRET=re.compile(r'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')


def check_selection(event, nodes, task):
    data=event['data']
    selected=[n for n in nodes if n['id']==data['selected_node_id']]
    if len(selected)!=1:raise ValueError('selected node missing or duplicated')
    node=selected[0];grade=node['metric_info'];score=data['score']
    if type(score) not in (int,float) or not math.isfinite(score):raise ValueError('nonfinite final')
    if node['exit_code']!=0 or node['is_buggy'] is not False:raise ValueError('unsuccessful selected node')
    if grade.get('valid_submission')!=1 or grade.get('submission_exists')!=1:
        raise ValueError('selected submission not externally valid')
    if grade.get('competition_id')!=task:raise ValueError('wrong competition grade')
    lower=task=='leaf-classification'
    if grade.get('is_lower_better')!=int(lower):raise ValueError('wrong metric orientation')
    if type(grade.get('score')) not in (int,float) or not math.isfinite(grade['score']):
        raise ValueError('invalid external grade')
    if score!=grade['score']:raise ValueError('final differs from selected external grade')
    if score<0 or (not lower and score>1):raise ValueError('invalid score domain')
    return score


def main():
    # Require the primary closeout AND a fresh, independent scheduler observation.
    if not (ROOT/'diagnostics.json').is_file():raise ValueError('whole-block closeout not yet available')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    text=subprocess.run(['sacct','-X','-nP','-j','13115','-o',
        'JobIDRaw,State%32,NodeList,ElapsedRaw,AllocTRES%256,User'],
        check=True,capture_output=True,text=True,timeout=20,env=env).stdout.strip()
    lines=text.splitlines()
    if len(lines)!=1:raise ValueError('ambiguous allocation')
    job,state,node,seconds,tres,user=lines[0].split('|')
    if (job!='13115' or node!='gpu28' or user!='yzyang4' or state.split()[0].rstrip('+') not in
        {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED'}):
        raise ValueError('allocation not independently closed')
    resources=dict(x.split('=',1) for x in tres.split(',') if '=' in x)
    if resources.get('gres/gpu')!='2':raise ValueError('allocation hardware changed')
    evidence={}
    def read(path):
        raw=path.read_bytes()
        evidence[str(path.relative_to(ROOT))]=hashlib.sha256(raw).hexdigest()
        return json.loads(SECRET.sub('[REDACTED]',raw.decode()))
    prepared=read(ROOT/'prepared.json')
    if evidence['prepared.json']!=PREPARED or prepared['source_tree']!=TREE:raise ValueError('fixed package changed')
    primary=read(ROOT/'final-readout/summary.json');diagnostic=read(ROOT/'diagnostics.json')
    expected=prepared['run_configs'];runs=primary['runs']
    if len(expected)!=4 or [x['run_id'] for x in runs]!=[x['run_id'] for x in expected]:
        raise ValueError('planned slots missing or reordered')
    rows=[]
    for original,row in zip(expected,runs):
        base=ROOT/'runs'/original['run_id'];journal=base/'checkpoint/journal.jsonl'
        nodes=[]
        if journal.exists():
            raw=journal.read_bytes();evidence[str(journal.relative_to(ROOT))]=hashlib.sha256(raw).hexdigest()
            nodes=[json.loads(s) for s in SECRET.sub('[REDACTED]',raw.decode()).splitlines() if s.strip()][1:]
        final=base/'json/eval.jsonl'
        checked=None
        if row['comparable_final']:
            process=read(ROOT/next(r['process_summary'] for r in read(ROOT/'runtime-manifest.json')['runs'] if r['run_id']==row['run_id']))
            if process['status']!='completed' or process['returncode']!=0 or process['started'] is not True:
                raise ValueError('not a completed process')
            checked=check_selection(read(final),nodes,original['task'])
            if checked!=row['comparable_score']:raise ValueError('primary final differs')
        elif row['comparable_score'] is not None:raise ValueError('missing final assigned a score')
        rows.append(dict(run_id=original['run_id'],task=original['task'],arm=original['arm'],seed=original['seed'],
            comparable_final=row['comparable_final'],external_final_score=checked,
            final_event_present=final.exists(),executed_nodes=len(nodes),
            exit_zero_nodes=sum(n['exit_code']==0 for n in nodes)))
    with closing(sqlite3.connect((ROOT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        calls=db.execute('SELECT scope,held,cost,state FROM calls').fetchall()
    if len(calls)<55:raise ValueError('historical API charges lost')
    settled=sum(r[2] or 0 for r in calls);accounted=sum(r[1] for r in calls)
    if settled!=round(diagnostic['billing']['cumulative_settled_usd']*10**9):raise ValueError('billing disagreement')
    if accounted>3122344104:raise ValueError('authorized liability exceeded')
    report=dict(utc=datetime.now(timezone.utc).isoformat(),job=job,state=state,
        verification='selected-node/external-grade consistency passed',independent_numerical_regrade=False,
        source_tree=TREE,valid_finals=sum(r['comparable_final'] for r in rows),rows=rows,
        new_api_calls=len(calls)-55,cumulative_api_calls=len(calls)-1+124,
        cumulative_settled_usd=str(Decimal(settled)/10**9),cumulative_accounted_usd=str(Decimal(accounted)/10**9),
        unresolved_calls=sum(r[3]=='unresolved' for r in calls),allocation_gpu_hours=int(seconds)*2/3600,
        evidence_sha256=evidence,verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        limitations=['Task deletes submission files; no independent numerical regrade is claimed.',
                    'A single development seed is not a cross-seed benefit or clean scaling result.'])
    with (ROOT/'independent-final-verification.json').open('x') as stream:
        json.dump(report,stream,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in report.items() if k not in ('rows','evidence_sha256')}))


if __name__=='__main__':main()
