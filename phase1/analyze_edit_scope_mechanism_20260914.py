"""Predefined descriptive diagnostics; callable only after the full frozen readout.

No effect-based row exclusion, taxonomy tuning, outcome selection, or new runs.
Saved nodes are correlated and may miss interrupted work: no mediation claim.
"""
import argparse
import ast
from collections import Counter
import json
import math
import os
from pathlib import Path
import re
import sys

from forets_environment_build_20260912 import read,write,encode,sha

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-88v5m9dr')
SECRET=re.compile(r'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')


def taxonomy():
    path=Path(__file__).with_name('audit_closed_error_families_20260913.py');tree=ast.parse(path.read_bytes())
    pure=[n for n in tree.body if
        (isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('ANSI','EXCEPTION','RULES')) or
        (isinstance(n,ast.FunctionDef) and n.name=='classify')]
    if len(pure)!=4:raise ValueError('fixed old taxonomy')
    space={'re':re};exec(compile(ast.Module(body=pure,type_ignores=[]),str(path),'exec'),space)
    return space['classify'],sha(path.read_bytes())


def outer_key(code):
    tree=ast.parse(code)
    return sha(ast.dump(ast.Module(body=[n for n in tree.body if not (isinstance(n,ast.FunctionDef) and n.name=='build_model')],type_ignores=[])).encode())


def node_summary(nodes,expected_outer):
    classify,_=taxonomy();count=Counter();seconds=Counter();rejections=Counter();outside=Counter()
    for n in nodes:
        if n.get('step')==0 or n.get('exec_time') is None:continue
        duration=n['exec_time']
        if not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<0:raise ValueError('execution duration')
        count['saved_executed']+=1;seconds['saved_executed']+=duration
        valid=(n.get('metric_info') or {}).get('valid_submission')==1
        failed=n.get('exit_code') not in (None,0)
        count['valid_submission']+=int(valid);seconds['valid_submission']+=duration if valid else 0
        count['nonzero_exit']+=int(failed);seconds['nonzero_exit']+=duration if failed else 0
        kind,patterns=classify(n.get('term_out') or '')
        if failed:
            count['exception:'+kind]+=1
            for name in patterns or ['unclassified']:
                count['pattern:'+name]+=1;seconds['pattern:'+name]+=duration
        for metrics in n.get('operators_metrics') or []:
            if not isinstance(metrics,dict):continue
            scope=metrics.get('edit_scope')
            if isinstance(scope,dict):
                count['interface_observed']+=1
                if scope.get('interface_accepted') is False:
                    count['interface_rejected']+=1;seconds['interface_rejected']+=duration
                    rejections[str(scope.get('rejection'))]+=1
        code=n.get('code')
        if isinstance(code,str):
            try:outside['static_outer_unchanged' if outer_key(code)==expected_outer else 'static_outer_changed']+=1
            except SyntaxError:outside['syntax_unparseable']+=1
    return dict(counts=dict(count),seconds=dict(seconds),interface_rejections=dict(rejections),static_outer=dict(outside))


def run():
    closed=read(ROOT/'readout-finished.json')
    if closed.get('status')!='verified':raise ValueError('full effect closure required; do not peek')
    summary=read(ROOT/'edit-scope-summary.json',closed['files']['edit-scope-summary.json'])
    if len(summary['rows'])!=16:raise ValueError('fixed matrix')
    sys.path.insert(0,str(ROOT/'source/src'))
    from dojo.solvers.fore_ts.common_start import code_for
    expected={task:outer_key(code_for(task)) for task in ('leaf-classification','spaceship-titanic')}
    rows=[];proof=[]
    for r in summary['rows']:
        p=ROOT/'runs'/r['run_id']/'checkpoint/journal.jsonl'
        row={k:r[k] for k in ('run_id','task','seed','arm','technical_eligible')};row['journal_present']=p.exists()
        if p.exists():
            raw=p.read_bytes();text=raw.decode()
            if SECRET.search(text):raise ValueError('credential-shaped journal; no raw output')
            nodes=[json.loads(line) for line in text.splitlines() if line.strip()]
            if len({n['step'] for n in nodes})!=len(nodes):raise ValueError('duplicate saved step')
            row.update(node_summary(nodes,expected[r['task']]))
            if sha(p.read_bytes())!=sha(raw):raise ValueError('closed journal changed')
            proof.append(dict(run_id=r['run_id'],journal_sha256=sha(raw)))
        rows.append(row)
    result=dict(role='predefined_descriptive_mechanism_not_causal_mediation',rows=rows,proof=proof,
        summary_sha256=closed['files']['edit-scope-summary.json'],script_sha256=sha(Path(__file__).read_bytes()),taxonomy_sha256=taxonomy()[1],
        limitations=['Saved executed nodes only; interrupted/unpersisted work is not complete coverage.',
            'Error patterns overlap; their times cannot be added to infer total counterfactual savings.',
            'Static outer equality is not a sandbox, valid-learning proof, or runtime noninterference guarantee.',
            'All planned runs retained; node counts are not independent samples. Primary final scores remain in the frozen report.'])
    raw=encode(result)
    if SECRET.search(raw.decode()):raise ValueError('public diagnostic credential shape')
    print(json.dumps(dict(sha256=write(ROOT/'edit-scope-mechanism.json',raw),runs=len(rows))))


if __name__=='__main__':run()
