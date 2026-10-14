"""Read-only closure/source and public-preview audit; no outcome parsing."""
import argparse
import hashlib
import json
from pathlib import Path
from fixed_public_preview_20261014 import DONOR_PLAN_SHA, sha


def main(donor, first, final, output):
    donor,first,final,output=map(Path,(donor,first,final,output))
    assert sha(donor/'plan.json')==DONOR_PLAN_SHA
    plan=json.loads((donor/'plan.json').read_bytes())
    bad=[name for name,pin in plan['files'].items() if sha(donor/name)!=pin]
    assert not bad,'closed batch frozen input/source drift'
    a,b=(json.loads(p.read_bytes()) for p in (first,final))
    assert a['tasks']==b['tasks'],'public preview or manifest changed'
    result=dict(donor_plan_sha256=DONOR_PLAN_SHA,frozen_source_files_checked=len(plan['files']),
        frozen_source_unchanged=True,public_text_and_manifests_equal=True,
        first_bundle_sha256=sha(first),final_bundle_sha256=sha(final),
        timing_note='v1 field preparation_cpu_seconds actually used monotonic wall time; v2 correctly labels preparation_wall_seconds. Neither is GPU time.',
        public={task:{k:v for k,v in row.items() if k!='text'} for task,row in b['tasks'].items()},
        public_preparation_wall_seconds=b['preparation_wall_seconds'],
        verifier_sha256=sha(__file__),no_scores_read=True,no_gpu=True,no_model_calls=True)
    with output.open('x') as f:json.dump(result,f,indent=2,sort_keys=True)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for name in ('donor','first','final','output'):ap.add_argument(name)
    a=ap.parse_args();main(a.donor,a.first,a.final,a.output)
