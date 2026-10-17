"""Two fixed closed cohorts; descriptive cross-batch check, not a new strategy.

Does not reuse the invalid19004 contrast. Exact source hashes and original
endpoints stay pinned. Outputs are exclusive-create; original readouts untouched.
"""
import json
from pathlib import Path
from closed_adaptation_lineage_20261017 import extract,sha

SPECS=(
    (18770,'scheduling-pooling-20261016-v3',
     'a7cc9780c927cdeac3fc1effb214643a387353122e1fa542d3a40116b248d477',
     'bef23ec17e2fd3e561a690e2aa7328c3df592cb315070fbc293d69c4ce84def5'),
    (18807,'scheduling-colocation-20261016-v1',
     '36ce5852b26de2299755c19a8b9711a1f4161d68abd25a3de6cc7687cdde8560',
     'c8c2f71009a39e9932ec59e388f9b052ce190730179119aed5d73e4fa38576a4'))

def main():
    for job,name,plan,summary in SPECS:
        root=Path('/research/d7/spc/yzyang4')/name
        dest=root/'adaptation-lineage-extension-20261017.safe.json'
        if dest.exists():raise FileExistsError('closed diagnostic already exists; do not overwrite')
        out=extract(root,plan,summary,'readout-20261016-v1')
        out.update(job=job,driver_sha256=sha(__file__))
        with dest.open('x') as f:json.dump(out,f,indent=2,sort_keys=True,allow_nan=False)
        print(json.dumps(dict(job=job,path=str(dest),sha256=sha(dest),
            returned=out['candidate_receipts'],groups=out['groups']),sort_keys=True),flush=True)

if __name__=='__main__':main()
