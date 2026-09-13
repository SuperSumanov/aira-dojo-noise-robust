"""Read one observed diagnostic case after remote credential redaction."""
import json
from pathlib import Path
from inspect_branching_completion_errors_20260913 import SECRET

path=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-5_czzimk/runs/02-spaceship-titanic-s32-critic_topk_random/checkpoint/journal.jsonl')
matches=[json.loads(x) for x in path.read_bytes().splitlines() if json.loads(x)['step']==4]
if len(matches)!=1:raise ValueError('one exact saved node')
text=SECRET.sub('[REDACTED]',matches[0]['code'])
if len(text)>18000:raise ValueError('bounded diagnostic output')
print(json.dumps(dict(role='posthoc_source_diagnosis_not_reexecution',redacted_code=text)))
