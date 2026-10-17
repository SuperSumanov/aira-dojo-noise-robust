"""Failure hints from bounded remote tails; no raw log/code/value export."""
import hashlib,json,sys
from pathlib import Path

ROOT=Path('/research/d7/spc/yzyang4/scheduling-generation-quota-20261017-v3')
assert hashlib.sha256((ROOT/'plan.json').read_bytes()).hexdigest()=='2736fb9326f62f3c83bc0cebc4854ba629991e5b5e4bb69e708aa91e24b74e7e'
assert json.loads((ROOT/'closed.json').read_text())['complete']==31
sys.path.insert(0,str(ROOT))
from live_status import log_shape
paths=['episode-26/worker.private.log','block-3/executor.private.log']
result=dict(job='19136',index=26,scope='bounded tail syntax hints, not causal proof',
 logs={name:dict(sha256=hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),**log_shape(ROOT/name)) for name in paths})
with (ROOT/'failure-shape-20261018.safe.json').open('x') as f:json.dump(result,f,indent=2,sort_keys=True)
print(json.dumps(result,sort_keys=True))
