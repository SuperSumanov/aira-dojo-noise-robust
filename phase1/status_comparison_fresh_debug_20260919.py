"""Allowlisted structural progress only; no predictions or program outcomes."""
import json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path('/research/d7/spc/yzyang4/comparison-fresh-debug-exec-20260919-53mn3zh0')

def main():
    if ROOT.resolve(strict=True) != ROOT:
        raise ValueError('root identity')
    job = json.loads((ROOT/'launch.json').read_bytes())['job']
    if not re.fullmatch(r'[0-9]+', job):
        raise ValueError('job identity')
    env = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    acc = subprocess.check_output(['sacct','-X','-j',job,'-nP','-o',
        'JobIDRaw,State%24,ElapsedRaw,NodeList,AllocTRES%120'], env=env, text=True, timeout=25)
    rows = [line.split('|') for line in acc.splitlines() if line.split('|')[0] == job]
    if len(rows) != 1:
        raise ValueError('accounting record')
    print(json.dumps(dict(job=job,allocation=rows[0],
        claimed=(ROOT/'execution-claim.json').exists(),finished=(ROOT/'finished.json').exists(),
        result_records=sum((ROOT/f'result-{i}.json').exists() for i in (0,1)),
        binding_records=sum((ROOT/f'identity-{i}.native-binding.json').exists() for i in (0,1)))))

if __name__ == '__main__':
    main()
