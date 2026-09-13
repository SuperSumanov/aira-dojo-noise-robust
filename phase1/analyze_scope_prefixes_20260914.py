"""Predefined prefixes of a 1200s policy, NOT counterfactual shorter-budget runs.

All sixteen runs must close first. Selection is the original search-visible
incumbent; external scores are accessed only after prefix identity is fixed.
"""
import ast
import hashlib
import json
from pathlib import Path
import math
import sys
from forets_environment_build_20260912 import read,write,encode,sha

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-88v5m9dr')
PREFIXES=(300,600,900,1200)


def select_prefix(records,*,start_ns,seconds):
    deadline=start_ns+seconds*10**9
    eligible=[r for r in records if r[2] and r[1]<deadline]
    return eligible[-1][3] if eligible else None


def independent_records(base,start_ns):
    import read_forets_action_delivery_20260913 as frozen
    path=Path(frozen.__file__);tree=ast.parse(path.read_bytes())
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='read_latest']
    if len(nodes)!=1:raise ValueError('reader identity')
    node=nodes[0]
    if not isinstance(node.body[-1],ast.Return):raise ValueError('reader final return shape')
    # Preserve every original hash, time, schema and original-selection check;
    # return the already-verified sequence instead of only its final member.
    node.body[-1]=ast.Return(value=ast.Name(id='records',ctx=ast.Load()))
    ast.fix_missing_locations(node);ns=dict(vars(frozen))
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),ns)
    records=ns['read_latest'](base,start_ns=start_ns,seconds=1200)
    if select_prefix(records,start_ns=start_ns,seconds=1200)!=frozen.read_latest(base,start_ns=start_ns,seconds=1200):
        raise ValueError('final frozen endpoint disagreement')
    return records


def run():
    closure=read(ROOT/'readout-finished.json')
    if closure.get('status')!='verified':raise ValueError('all-run frozen readout first')
    action=read(ROOT/'edit-scope-summary.json',closure['files']['edit-scope-summary.json'])
    original=read(ROOT/'wallclock-summary.json',closure['files']['wallclock-summary.json'])
    if len(action['rows'])!=16 or len(original['rows'])!=16:raise ValueError('fixed complete matrix')
    sys.path[:0]=[str(ROOT/'source/src'),str(ROOT/'code')]
    import pandas as pd
    from mlebench.registry import registry
    from readout_forets_generation_capacity_20260912 import numerical
    registry=registry.set_data_dir(ROOT.parent/'mle-bench-data');answers={};cache={};rows=[]
    for r in action['rows']:
        o=next(v for v in original['rows'] if v['run_id']==r['run_id'])
        start=o['search_start_ns'];cfg=read(ROOT/'configs'/(r['run_id']+'.json'))
        records=independent_records(ROOT/'incumbents'/r['run_id'],start) if start is not None else []
        for seconds in PREFIXES:
            chosen=select_prefix(records,start_ns=start,seconds=seconds) if start is not None else None
            row={k:r[k] for k in ('run_id','task','seed','arm','technical_eligible')}
            row.update(prefix_seconds=seconds,policy_budget_seconds=1200,valid=False,score=None,
                       selected_code_sha256=None,observed_actions=None,durable_seconds=None)
            if chosen is not None:
                row['observed_actions']=chosen['action']
                row['durable_seconds']=(next(v[1] for v in records if v[0]==chosen['action'])-start)/1e9
                if chosen['submission'] is not None:
                    receipt=chosen['submission'];archive=Path(receipt['archive_dir'])
                    if archive.is_symlink() or archive.parent.resolve()!=(Path(cfg['task']['results_output_dir'])/'submission-escrow').resolve():
                        raise ValueError('selected archive scope')
                    complete=read(archive/'complete.json')
                    if any(receipt.get(k)!=v for k,v in complete.items()):raise ValueError('selected receipt binding')
                    for name,key in [('submission.csv','submission_sha256'),('report.json','report_sha256')]:
                        if sha((archive/name).read_bytes())!=receipt[key]:raise ValueError('archive hash')
                    report=read(archive/'report.json')
                    if report['valid_submission'] is not True:raise ValueError('selected report validity')
                    key=(r['task'],receipt['submission_sha256'])
                    if key not in cache:
                        if r['task'] not in answers:answers[r['task']]=pd.read_csv(registry.get_competition(r['task']).answers)
                        value=numerical(r['task'],pd.read_csv(archive/'submission.csv'),answers[r['task']])
                        if not math.isfinite(value) or round(value,5)!=report['score']:raise ValueError('independent prefix grade')
                        cache[key]=report['score']
                    row.update(valid=True,score=cache[key],selected_code_sha256=receipt['code_sha256'])
            if seconds==1200 and (row['valid'],row['score'],row['selected_code_sha256'])!=(r['action_valid'],r['action_score'],r['action_code_sha256']):
                raise ValueError('primary endpoint differs')
            rows.append(row)
    result=dict(role='predefined_exploratory_prefixes_not_budget_scaling',prefixes=list(PREFIXES),rows=rows,
        unique_independent_regrades=len(cache),source_summary_sha256=closure['files']['edit-scope-summary.json'],
        script_sha256=sha(Path(__file__).read_bytes()),
        limitations=['The 1200s policy knows its remaining budget. Prefixes are not independent 300/600/900s policies.',
            'No external-score-based best-so-far, task removal, horizon selection, or change to the 1200s primary endpoint.',
            'Technical eligibility remains that of the entire planned run, even if an early incumbent exists.',
            'Repeated prefixes/nodes are not independent observations. Small two-task exploratory evidence only.'])
    print(json.dumps(dict(sha256=write(ROOT/'edit-scope-prefixes.json',encode(result)),rows=len(rows),unique_regrades=len(cache))))


if __name__=='__main__':run()
