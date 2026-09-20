"""Allowlisted structural progress only; no candidate, score or reply values."""
import argparse,datetime,json,os,re,subprocess
from pathlib import Path

BASE=Path('/research/d7/spc/yzyang4')
def main(root):
    if root.resolve()!=root or root.parent!=BASE or not re.fullmatch(r'comparison-(?:pool-native-selection|pizza-transfer|complete-pool-order)-20260920-[a-z0-9_]+',root.name):raise ValueError('explicit session scope')
    launch=json.loads((root/'launch.json').read_bytes());job=launch['job']
    if not str(job).isdigit():raise ValueError('job')
    raw=subprocess.check_output(['sacct','-X','-j',job,'-nP','-o','JobIDRaw,State%32,ElapsedRaw,NodeList,AllocTRES%128'],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=25)
    account,=[line.split('|') for line in raw.splitlines() if line.split('|')[0]==job]
    safe=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),root=str(root),job=job,state=account[1],elapsed_seconds=int(account[2]),node=account[3],tres=account[4],
        markers={name:(root/name).is_file() for name in ('ready.json','model-ready.json','prediction-complete.json','analysis-complete.json','policy-selections.json','services-ready.json','critic-stage.json','closed.json','finished.json','summary.json')},
        analysis_receipts=sum(bool(re.fullmatch(r'analysis-\d+\.json',f.name)) for f in root.glob('analysis-*.json')),
        prediction_receipts=sum(bool(re.fullmatch(r'prediction-\d+\.json',f.name)) for f in root.glob('prediction-*.json')),
        execution_receipts=sum(bool(re.fullmatch(r'result-\d+\.json',f.name)) for f in root.glob('result-*.json')))
    safe['episodes']=[dict(index=i,started=(root/f'episode-{i}/start.json').is_file(),finished=(root/f'episode-{i}/finished.json').is_file(),action_receipts=len(list((root/f'episode-{i}').glob('action-*.json')))) for i in range(4)]
    print(json.dumps(safe))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);main(p.parse_args().root)
