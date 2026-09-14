"""Closed-run exception classification only; retain original qualification."""
import hashlib, json, re
from pathlib import Path

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-9uosb6me')
SHA='aa9c4610c0c6bc91011fca4e0edc8a6f6a8f7459351978bc73298d1a70258609'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
MESSAGES=(b'execution code security/schema gate',b'runtime and configured execution timeout mismatch',b'positive execution-call cap required',b'finite positive configured execution timeout required',b'invalid execution role',b'task returned without valid execution metadata',b'invalid task return shape',b'invalid execution metadata')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def main():
    raw=(ROOT/'cheap-selector-summary.json').read_bytes()
    if sha(raw)!=SHA or SECRET.search(raw):raise ValueError('summary gate')
    summary=json.loads(raw);bad=[r for r in summary['rows'] if not r['technical_eligible']]
    if len(bad)!=1 or (bad[0]['task'],bad[0]['arm'])!=('spaceship-titanic','uniform'):raise ValueError('fixed failed row')
    rid=bad[0]['run_id'];matches=[]
    for p in (ROOT/'runs/srun_pool').glob('*/identities/*.bounded/execution/stderr.private.log'):
        identity=p.parents[1].with_suffix('.json')
        if not identity.exists():continue
        ident=json.loads(identity.read_bytes())
        if ident['run_id']!=rid:continue
        data=p.read_bytes()
        row={'run_id':rid,'log_sha256':sha(data),'credential_shape_hits':len(SECRET.findall(data))}
        # Even a hit never causes raw output. Only exact source-owned messages.
        row['known_exception_messages']=[msg.decode() for msg in MESSAGES if b'ExecutionWitnessError: '+msg in data or b"ExecutionWitnessError(\""+msg+b'\")' in data]
        row['execution_witness_exception']=b'ExecutionWitnessError' in data
        matches.append(row)
    if len(matches)!=1:raise ValueError('one fixed failed log required')
    out={'role':'posthoc_exception_diagnosis_not_requalification','source_summary_sha256':SHA,'rows':matches,'original_technical_eligible':False,'qualification_changed':False,'experiments_restarted':0,'script_sha256':sha(Path(__file__).read_bytes())}
    raw=(json.dumps(out,sort_keys=True)+'\n').encode()
    with (ROOT/'exception-diagnosis.json').open('xb') as f:f.write(raw)
    print(json.dumps({'sha256':sha(raw),**out}))
if __name__=='__main__':main()
