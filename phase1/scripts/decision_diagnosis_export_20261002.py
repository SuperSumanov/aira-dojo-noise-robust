"""Export only named, credential-scanned aggregate receipts; no private payloads."""
import hashlib, json, re, shutil
from pathlib import Path

R=Path('/research/d7/spc/yzyang4/decision-diagnosis-20261002-v1')
NAMES={
    'plan.json':'plan.json', 'launch.json':'launch.json',
    'all-closed.json':'all-closed.json', 'closed.json':'closed.json',
    'source-audit.json':'source-audit.json','token-audit.json':'length-audit.json',
    'output-channel-review.json':'output-channel-review.json',
    'output-channel-fix-test.json':'output-channel-fix-test.json',
    'readout-v1/runs.csv':'runs.csv','readout-v1/actions.csv':'actions.csv',
    'readout-v1/pairs.csv':'pairs.csv','readout-v1/summary.json':'summary.json',
    'readout-v1/verification.json':'verification.json',
    'readout-v1/census.json':'census.json'
}
PATTERN=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')

def main():
    assert (R/'all-closed.json').is_file() and (R/'closed.json').is_file()
    verification=json.loads((R/'readout-v1/verification.json').read_bytes())
    assert verification['status']=='PASS'
    assert verification['summary_sha256']==hashlib.sha256((R/'readout-v1/summary.json').read_bytes()).hexdigest()
    raw={dst:(R/src).read_bytes() for src,dst in NAMES.items()}
    assert not any(PATTERN.search(data) for data in raw.values()),'Credential shape found; no value emitted'
    out=R/'public-export-v1';out.mkdir(mode=0o700)
    for name,data in raw.items():
        with (out/name).open('xb') as f:f.write(data)
    receipt=dict(status='PASS',files={name:hashlib.sha256(data).hexdigest() for name,data in raw.items()},
        credential_shape_file_hits=0,private_payloads_exported=0,
        scope='Named aggregate outcome/count/hash receipts only. No labels, row-level predictions, candidate code or raw model/terminal transcripts.')
    with (out/'export-receipt.json').open('x') as f:json.dump(receipt,f,sort_keys=True,indent=2)
    print(json.dumps(receipt,sort_keys=True))

if __name__=='__main__':main()
