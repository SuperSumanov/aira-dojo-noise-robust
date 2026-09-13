"""Independent alignment/coverage computation, not a recovered historical score."""
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def measure(y,concatenated,aligned,order,counts):
    n=len(y)
    if n==0 or any(len(x)!=n for x in (concatenated,aligned,order,counts)):
        raise ValueError('array coverage')
    if any(type(x) is not int for x in order+counts) or sorted(order)!=list(range(n)) or counts!=[1]*n:
        raise ValueError('exact one OOF prediction per row')
    if any(x not in (0,1) for x in y+concatenated+aligned):raise ValueError('binary labels/predictions')
    if concatenated!=[aligned[i] for i in order]:raise ValueError('not the same fold predictions')
    before=sum(a==b for a,b in zip(y,concatenated))/n
    after=sum(a==b for a,b in zip(y,aligned))/n
    return dict(rows=n,original_concatenated_accuracy=before,aligned_accuracy=after,aligned_minus_original=after-before,
        nonidentity_row_positions=sum(i!=v for i,v in enumerate(order)),exact_coverage_once=True,same_fold_predictions=True)


def main(root):
    import forets_pool_completion_20260912 as worker
    root,p=worker.checked(root);worker.source_check()
    plan=json.loads((root/'cv-readout-plan.json').read_bytes())
    for name,h in plan['readers'].items():
        if worker.sha(Path(__file__).with_name(name).read_bytes())!=h:raise ValueError('frozen reader drift')
    launch=json.loads((root/'launch.json').read_bytes())
    if launch['prepared_sha256']!=worker.sha((root/'prepared.json').read_bytes()):raise ValueError('prepared drift')
    env={**os.environ,'SLURM_CONF':'/opt1/slurm/gpu-slurm.conf'}
    acct=subprocess.check_output(['sacct','-X','-j',launch['job'],'-nP','-o','JobIDRaw,State,ElapsedRaw,NodeList,AllocTRES%128'],env=env,text=True,timeout=25).strip().split('|')
    if len(acct)!=5 or acct[0]!=launch['job'] or acct[1].split()[0] not in {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY'} or acct[3]!='gpu28':raise ValueError('closed allocation required')
    done=json.loads((root/'execution-finished.json').read_bytes());result=json.loads((root/'result-0.json').read_bytes())
    if done['planned']!=1 or done['completed']!=1 or result['code_sha256']!=p['rows'][0]['code_sha256']:
        raise ValueError('single execution binding')
    out=dict(role='same_fit_measurement_diagnostic_not_e2e',job=launch['job'],status=result['status'],
        source_tree=p['source_tree'],controller_commit=p['commit'],seed=p['seed'],
        prepared_sha256=launch['prepared_sha256'],code_sha256=result['code_sha256'],
        allocation_gpu_hours=int(acct[2])/3600,api_calls=0,metrics=None,external_submission_score=None,
        original_model_replayed=False,
        limitation='One selected diagnostic case; original unseeded Optuna now seeded. Both statistics share one fit/predictions. Remaining CV preprocessing/HPO bias not fixed; no recovered old endpoint or prospective method effect.')
    if result['status']=='valid':
        binding=json.loads((root/'identity-0.native-binding.json').read_bytes())
        if binding['native_identity']['job']!=launch['job'] or not binding['namespace']['exact_device_namespace']:raise ValueError('hardware binding')
        import numpy as np
        import pandas as pd
        path=root/'work-0/cv_alignment_private.npz'
        with np.load(path,allow_pickle=False) as a:arrays={k:a[k].tolist() for k in ('y','concatenated','aligned','order','counts')}
        expected=pd.read_csv(worker.BASE/'mle-bench-data/spaceship-titanic/prepared/public/train.csv')['Transported'].astype(int).tolist()
        if arrays['y']!=expected:raise ValueError('labels not original task training rows')
        out['metrics']=measure(**arrays);out['private_array_sha256']=worker.sha(path.read_bytes())
        raw=(root/'program-0.txt').read_bytes()
        if worker.sha(raw)!=result['output_sha256']:raise ValueError('stdout drift')
        tags=[json.loads(l.split('FORETS_CV_ALIGNMENT_DIAGNOSTIC ',1)[1]) for l in raw.decode().splitlines() if l.startswith('FORETS_CV_ALIGNMENT_DIAGNOSTIC ')]
        if len(tags)!=1 or any(abs(tags[0][k]-out['metrics'][k])>1e-12 for k in ('original_concatenated_accuracy','aligned_accuracy')):
            raise ValueError('independent measurement differs')
        from readout_forets_generation_capacity_20260912 import numerical
        from mlebench.registry import registry
        competition=registry.set_data_dir(worker.BASE/'mle-bench-data').get_competition('spaceship-titanic')
        submission=root/'work-0/submission.csv'
        if worker.sha(submission.read_bytes())!=result['submission_sha256']:raise ValueError('submission drift')
        grade=numerical('spaceship-titanic',pd.read_csv(submission),pd.read_csv(competition.answers))
        if round(grade,5)!=result['score']:raise ValueError('external independent numeric check')
        out.update(external_submission_score=result['score'],independent_external_score=grade,submission_sha256=result['submission_sha256'])
    out['reader_sha256']=worker.sha(Path(__file__).read_bytes());worker.write(root/'cv-alignment-summary.json',out)
    row={k:v for k,v in out.items() if k!='metrics'};row.update(out['metrics'] or {})
    with (root/'cv-alignment-run.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(row));w.writeheader();w.writerow(row)
    print(json.dumps(dict(summary_sha256=worker.sha((root/'cv-alignment-summary.json').read_bytes()),**out)))


if __name__=='__main__':main(Path(sys.argv[1]))
