"""Operational classification only: no candidate data, outcomes, or raw logs."""
import json
from pathlib import Path
from forets_environment_build_20260912 import read

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-7wzrny21')

def run():
    output=[]
    for block in (1,2):
        path=ROOT/f'block-{block}.runtime/started.json'
        if not path.exists():continue
        start=read(path);pool=read(ROOT/start['pool_manifest'])
        for rid,t in pool['tasks'].items():
            if t['status'] in ('running','launching','pending') or not t['attempts']:continue
            identity=Path(t['attempts'][0]['identity_path'])
            if not identity.resolve().is_relative_to(ROOT/'runs/srun_pool'):raise ValueError('identity path')
            summary=identity.with_suffix('.bounded')/'execution/summary.json'
            if not summary.exists():
                output.append(dict(run_id=rid,controller_status=t['status'],classification='summary_missing'));continue
            s=read(summary);label=s['status']
            if label=='failed':
                p=summary.parent/'stderr.private.log'
                with p.open('rb') as f:
                    f.seek(max(0,p.stat().st_size-4096));tail=f.read()
                if tail.rstrip().endswith(b'SearchBudgetExpired: insufficient search time for a bounded API request'):
                    label='api_admission_budget_expired'
                elif b'KernelReadinessError' in tail:label='kernel_readiness_error'
                else:label='other_failure_requires_private_review'
            output.append(dict(run_id=rid,controller_status=t['status'],classification=label,elapsed_seconds=s['elapsed_seconds']))
    print(json.dumps(output))

if __name__=='__main__':run()
