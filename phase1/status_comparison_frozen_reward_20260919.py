"""Prediction count and allocation metadata only, never prediction values."""
import json,os,subprocess
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/comparison-frozen-reward-20260919-ac_f34fz')
job=json.loads((ROOT/'launch.json').read_bytes())['job']
raw=subprocess.check_output(['sacct','-X','-j',job,'-nP','-o','JobIDRaw,State%32,ElapsedRaw,NodeList,AllocTRES%128'],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=25)
row,=[line.split('|') for line in raw.splitlines() if line.split('|')[0]==job]
print(json.dumps(dict(job=job,allocation=row,model_ready=(ROOT/'model-ready.json').exists(),identity=(ROOT/'device-identity.json').exists(),predictions=len(list(ROOT.glob('prediction-*.json'))),finished=(ROOT/'finished.json').exists())))
