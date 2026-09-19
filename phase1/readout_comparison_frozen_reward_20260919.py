"""One closed readout of every frozen reward, joined to fixed closed replay grades."""
import argparse,csv,json,math,os,re,subprocess
from pathlib import Path
import local_generator_runtime_20260914 as rt
from analyze_comparison_frozen_reward_20260919 import summarize

ROOT=rt.BASE/'comparison-frozen-reward-20260919-ac_f34fz'
PREPARED='a16acaa7b96946f90d1a171a7accf16a3e0c170c08f1df7545f7d9f958ba2362'
LABELS=[('comparison-pool-20260919-7ujiaajp','238bd65e00edd0f678b1f9dc6fbce0c92bf49247030765b64c703ed4d469547a',(1,2)),
 ('comparison-pool-20260919-1z7l72bz','051c550d80b3d9fa50d592f6a615d1ebb02c14a87c6c2dbf0a861b928b52bae4',(3,)),
 ('comparison-spooky-pool-20260919-04qsl2xc','721f995ca597568303f65c32e9d04667bcdd173c174b2e6af99bb78e765c0eb1',(1,2))]
IDENTITY=('task','seed','run','slot','node','code_sha256')

def join_rows(prepared,predictions,labels):
    if len(prepared)!=30 or len(predictions)!=30 or len(labels)!=30:raise ValueError('all thirty required')
    def keyed(rows):
        result={r['node']:r for r in rows}
        if len(result)!=30:raise ValueError('duplicate node')
        return result
    pp,ll=keyed(predictions),keyed(labels)
    if set(pp)!=set(ll) or set(pp)!=set(keyed(prepared)):raise ValueError('population mismatch')
    output=[]
    for expected in prepared:
        prediction,label=pp[expected['node']],ll[expected['node']]
        for k in IDENTITY:
            if expected[k]!=prediction[k] or expected[k]!=label[k]:raise ValueError('identity mismatch')
        if prediction['source_prepared_sha256']!=expected['source_prepared_sha256']:raise ValueError('source mismatch')
        if label['status']!='returned' or type(label['valid']) is not bool:raise ValueError('unknown replay; do not drop')
        if type(prediction['reward']) not in (int,float) or not math.isfinite(prediction['reward']):raise ValueError('nonfinite reward')
        seconds=prediction['inference_seconds']
        if type(seconds) not in (int,float) or not math.isfinite(seconds) or seconds<0:raise ValueError('latency')
        output.append({k:expected[k] for k in IDENTITY}|dict(reward=prediction['reward'],inference_seconds=seconds,
            valid=label['valid'],score=label['score'],independent_score=label['independent_score'],
            original_selected=label['original_selected'],exit_code=label['exit_code'],timed_out=label['timed_out']))
    return output

def allocation(job):
    raw=subprocess.check_output(['sacct','-X','-j',job,'-nP','-o','JobIDRaw,State%32,ElapsedRaw,NodeList,AllocTRES%128'],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=25)
    row,=[line.split('|') for line in raw.splitlines() if line.split('|')[0]==job]
    if row[3]!='gpu28' or not re.search(r'(?:^|,)gres/gpu=1(?:,|$)',row[4]):raise ValueError('one GPU allocation')
    return dict(job=job,state=row[1],seconds=int(row[2]),node=row[3],tres=row[4])

def main(commit):
    if not re.fullmatch('[a-f0-9]{40}',commit) or commit=='0'*40:raise ValueError('actual reader commit')
    if rt.sha(ROOT/'prepared.json')!=PREPARED:raise ValueError('prepared drift')
    p=rt.read(ROOT/'prepared.json')
    for name,digest in p['files'].items():
        if rt.sha(ROOT/name)!=digest:raise ValueError('code drift')
    if rt.read(ROOT/'launch.json')['job']!='14170':raise ValueError('allocation identity')
    current,prior,repair=allocation('14170'),allocation('14168'),allocation('14169')
    if current['state']!='COMPLETED' or prior['state']!='FAILED' or prior['seconds']!=12 or repair['state']!='FAILED' or repair['seconds']!=4:raise ValueError('not closed as planned; no values read')
    if current['seconds']+prior['seconds']+repair['seconds']>1800:raise ValueError('allocation budget exceeded')
    finished=rt.read(ROOT/'finished.json')
    if finished['predictions']!=30 or finished['job']!='14170' or finished['training'] is not False or finished['api_calls']!=0:raise ValueError('complete inference closure')
    if {f.name for f in ROOT.glob('prediction-*.json')}!={f'prediction-{i:02d}.json' for i in range(30)}:raise ValueError('prediction inventory')
    identity=rt.read(ROOT/'device-identity.json');ready=rt.read(ROOT/'model-ready.json')
    if identity['disjoint'] is not True or identity['paired_devices_seen']!=6 or ready['context']!=16384 or ready['head_frac']!=.25 or ready['task_cond'] is not True or ready['training'] is not False:raise ValueError('device/model contract')
    rt.write(ROOT/'readout-claim.json',dict(utc=rt.utc(),reader_commit=commit,prepared_sha256=PREPARED,allocations=[prior,repair,current]))
    labels=[];hashes={}
    for name,digest,seeds in LABELS:
        path=rt.BASE/name/'summary.json'
        if rt.sha(path)!=digest:raise ValueError('closed label source drift')
        labels.extend(r for r in rt.read(path)['rows'] if r['seed'] in seeds)
        hashes[name]=digest
    predictions=[rt.read(ROOT/f'prediction-{i:02d}.json') for i in range(30)]
    rows=join_rows(p['rows'],predictions,labels)
    result=summarize(rows)
    result.update(rows=rows,utc=rt.utc(),reader_commit=commit,deployment_commit=p['commit'],prepared_sha256=PREPARED,
        allocations=[prior,repair,current],gpu_hours=(current['seconds']+prior['seconds']+repair['seconds'])/3600,
        api_calls=0,label_source_sha256=hashes,prediction_sha256={f'prediction-{i:02d}.json':rt.sha(ROOT/f'prediction-{i:02d}.json') for i in range(30)},
        model=p['model'],encoder=ready,device=identity,prior_failure_kept=True)
    digest=rt.write(ROOT/'summary.json',result)
    with (ROOT/'runs.csv').open('x',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=list(rows[0])+['reader_commit','deployment_commit','inference_job'])
        writer.writeheader()
        for row in rows:writer.writerow(row|dict(reader_commit=commit,deployment_commit=p['commit'],inference_job='14170'))
    print(json.dumps(dict(status='COMPLETE_ALL_FIVE_POOLS',summary_sha256=digest,runs_sha256=rt.sha(ROOT/'runs.csv'),gpu_hours=result['gpu_hours'],policies=result['policies'],pools=result['pools']),allow_nan=False))

if __name__=='__main__':
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('--reader-commit',required=True);a=p.parse_args();main(a.reader_commit)
