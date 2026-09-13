"""Secondary fixed-time delivery curve after whole-matrix closure.

Cutoffs fixed before seed30/31 outcome readout. Not a searched best budget and
not an action-level reconstruction. Primary result remains the full 600 seconds.
"""
from contextlib import closing
import csv
import datetime as dt
import json
import os
from pathlib import Path
import sys
from forets_environment_build_20260912 import read,write,encode,sha

CUTOFFS=(120,240,360,480,600)


def choose_prefix(receipts,start_ns,cutoff_seconds):
    eligible=[r for r in receipts if r['eligible'] and r['durable_ns']<start_ns+cutoff_seconds*10**9]
    return max(eligible,key=lambda r:r['step'],default=None)


def run(root):
    root=root.resolve(strict=True)
    if root.parent!=Path('/research/d7/spc/yzyang4') or not root.name.startswith('forets-wallclock-20260912-'):
        raise ValueError('explicit development root')
    finish=read(root/'readout-finished.json')
    if finish['status']!='verified':raise ValueError('whole independent readout required')
    summary=read(root/'common-start-summary.json',finish['files']['common-start-summary.json'])
    if {r['seed'] for r in summary['rows']} not in ({30,31},{32,33}):raise ValueError('registered development seeds only')
    artifact=read(root/'artifact.json')
    for name,digest in artifact['source_files'].items():
        if sha((root/'source'/name).read_bytes())!=digest:raise ValueError('source drift')
    sys.path[:0]=[str(root/'source/src'),str(root/'code')]
    os.environ['PYTHON_DOTENV_DISABLED']='1'
    from dojo.solvers.fore_ts.wallclock import read_incumbent
    from readout_forets_generation_capacity_20260912 import numerical
    from mlebench.registry import registry
    import pandas as pd
    registry=registry.set_data_dir(root.parent/'mle-bench-data')
    rows=[];answers={};grades={};receipts_proof={}
    for r in summary['rows']:
        rid=r['run_id'];directory=root/'incumbents'/rid
        cfg=read(root/'configs'/(rid+'.json'))
        commits=sorted(directory.glob('step-*.commit.json'))
        receipts=[]
        if commits:
            first=read(commits[0]);data=read(directory/first['data_file'],first['data_sha256']);start=data['start_ns']
            read_incumbent(directory,expected_start_ns=start,expected_seconds=600)
            for p in commits:
                c=read(p);d=read(directory/c['data_file'],c['data_sha256'])
                receipts.append(dict(step=d['current_step'],durable_ns=c['durable_ns'],eligible=c['eligible'],data=d))
            receipts_proof[rid]={p.name:sha(p.read_bytes()) for p in commits}
        else:start=0;receipts_proof[rid]={}
        for cutoff in CUTOFFS:
            selected=choose_prefix(receipts,start,cutoff);valid=False;score=None;selected_step=None
            if selected is not None:
                data=selected['data'];association=data['submission']
                if association is not None:
                    archive=Path(association['archive_dir'])
                    if archive.parent.resolve()!=(Path(cfg['task']['results_output_dir'])/'submission-escrow').resolve():
                        raise ValueError('archive outside run')
                    complete=read(archive/'complete.json')
                    if any(association.get(k)!=v for k,v in complete.items()):raise ValueError('archive association')
                    report=read(archive/'report.json',association['report_sha256'])
                    raw=(archive/'submission.csv').read_bytes()
                    if sha(raw)!=association['submission_sha256']:raise ValueError('submission hash')
                    valid=report['valid_submission'] is True
                    if valid:
                        selected_step=data['current_step']
                        task=r['task'];key=(task,association['submission_sha256'])
                        if key not in grades:
                            if task not in answers:answers[task]=pd.read_csv(registry.get_competition(task).answers)
                            grades[key]=numerical(task,pd.read_csv(archive/'submission.csv'),answers[task])
                        if round(grades[key],5)!=report['score']:raise ValueError('independent intermediate score mismatch')
                        score=report['score']
            if cutoff==600 and (valid,score,selected_step)!=(r['valid'],r['score'],r['selected_step']):
                raise ValueError('curve disagrees with frozen primary endpoint')
            rows.append(dict(run_id=rid,task=r['task'],seed=r['seed'],arm=r['arm'],cutoff_seconds=cutoff,
                valid=valid,score=score,selected_step=selected_step,whole_run_technical_eligible=r['technical_eligible']))
        if receipts_proof[rid]!={p.name:sha(p.read_bytes()) for p in commits}:raise ValueError('concurrent receipt change')
    result=dict(role='secondary_fixed_time_delivery_not_budget_optimization',cutoffs=list(CUTOFFS),
        utc=dt.datetime.now(dt.timezone.utc).isoformat(),source_tree=summary['source_tree'],
        summary_sha256=finish['files']['common-start-summary.json'],inspector_sha256=sha(Path(__file__).read_bytes()),
        rows=rows,receipt_hashes=receipts_proof,independently_regraded_distinct_submissions=len(grades),
        limitation='Primary endpoint is 600 seconds. No best-cutoff selection, partial-iteration recovery, missing-to-zero or statistical significance claim.')
    digest=write(root/'anytime-curve.json',encode(result))
    with (root/'anytime-curve.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(dict(cutoffs=CUTOFFS,rows=len(rows),regraded=len(grades),sha256=digest)))


if __name__=='__main__':run(Path(sys.argv[1]))
