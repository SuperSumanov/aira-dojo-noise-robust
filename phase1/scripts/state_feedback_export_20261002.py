"""Export closed aggregate evidence, never labels, predictions or private code."""
import hashlib,json,re
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/state-feedback-pizza-20261002-v1')
PLAN='4b95fcc575c2f8fa438bd3737d05ec6f40ffa0aa2bfdfc89de38e76e71979b5b'
PATTERN=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    assert sha((R/'plan.json').read_bytes())==PLAN
    assert (R/'all-closed.json').is_file() and json.loads((R/'closed.json').read_bytes())['service_closed']
    v=json.loads((R/'readout-v1/verification.json').read_bytes())
    assert v['status']=='PASS' and v['summary_sha256']==sha((R/'readout-v1/summary.json').read_bytes())
    names={n:n for n in ('plan.json','launch.json','all-closed.json','closed.json')}
    names.update({'readout-v1/'+n:n for n in ('runs.csv','actions.csv','pairs.csv','summary.json','verification.json')})
    raw={dst:(R/src).read_bytes() for src,dst in names.items()}
    assert not any(PATTERN.search(b) for b in raw.values()),'credential shape withheld'
    out=R/'public-export-v1';out.mkdir(mode=0o700)
    for n,b in raw.items():
        with (out/n).open('xb') as f:f.write(b)
    receipt=dict(status='PASS',plan_sha256=PLAN,producer_sha256=sha(Path(__file__).read_bytes()),
        files={n:sha(b) for n,b in raw.items()},private_payloads_exported=0,
        scope='Closed all-assigned run/action aggregates and hashes; no labels, per-example predictions, raw candidate code or transcripts.')
    with (out/'export-receipt.json').open('x') as f:json.dump(receipt,f,sort_keys=True,indent=2)
    print(json.dumps(receipt,sort_keys=True))
if __name__=='__main__':main()
