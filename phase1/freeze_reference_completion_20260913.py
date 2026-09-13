"""Freeze all direct-completion readers before the sole submission."""
import hashlib
import json
from pathlib import Path
import sys
import forets_pool_completion_20260912 as worker


def main(root):
    root,p=worker.checked(root)
    if len(p['rows'])!=9 or any((root/n).exists() for n in ('submit-intent.json','launch.json','execution.claim.json')):
        raise ValueError('prelaunch nine-program freeze only')
    stage=Path(__file__).parent
    files=('readout_reference_completion_20260913.py','readout_forets_generation_capacity_20260912.py',
           'readout_forets_pool_completion_20260912.py')
    plan=dict(root=str(root),utc=worker.now(),planned_programs=9,all_original_candidates=16,
        prepared_sha256=worker.sha((root/'prepared.json').read_bytes()),
        readers={n:worker.sha((stage/n).read_bytes()) for n in files},
        freeze_script_sha256=worker.sha(Path(__file__).read_bytes()),
        no_api=True,no_retry=True,no_debug=True,unknown='preserve tri-state, no missing-to-zero')
    worker.write(root/'completion-readout-plan.json',plan)
    print(json.dumps(dict(readout_plan_sha256=worker.sha((root/'completion-readout-plan.json').read_bytes()),planned_programs=9)))


if __name__=='__main__':main(Path(sys.argv[1]))
