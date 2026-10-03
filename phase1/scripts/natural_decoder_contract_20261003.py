"""Pre-outcome semantic check of the actual extracted pure decoder function."""
import ast,hashlib,json
from pathlib import Path
import numpy as np
R=Path('/research/d7/spc/yzyang4/natural-opportunity-20261003-v1')
code=(R/'starts/5.py').read_text();node=next(n for n in ast.parse(code).body if isinstance(n,ast.FunctionDef) and n.name=='argmax_span')
src=ast.unparse(node)
assert src.count('e = e_logit[:tl, None]')==1 and src.count('np.tril(')==1
variants={}
for name,axis,mask in [('original',False,False),('mask_only',False,True),('axis_only',True,False),('both',True,True)]:
    c=src.replace('e = e_logit[:tl, None]','e = e_logit[None, :tl]') if axis else src
    if mask:c=c.replace('np.tril(','np.triu(')
    env={'np':np,'LEN_PENALTY':.02};exec(compile(c,'pure_decoder','exec'),env);variants[name]=env['argmax_span']
rng=np.random.default_rng(104033);cases=[]
for _ in range(1000):
    n=int(rng.integers(2,129));s=rng.normal(size=n);e=rng.normal(size=n)
    out={k:f(s,e,n) for k,f in variants.items()}
    assert out['original'][1]==0
    assert out['mask_only'][0]==out['mask_only'][1]
    expected=max(((i,j) for i in range(n) for j in range(i,n)),key=lambda p:s[p[0]]+e[p[1]]-.02*(p[1]-p[0]+1))
    assert out['both']==expected
    cases.append(out)
s=np.array([4.,0.,0.]);e=np.array([0.,0.,4.]);example={k:list(f(s,e,3)) for k,f in variants.items()}
out=dict(status='PASS',utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
    original_code_sha256=hashlib.sha256(code.encode()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    draws=1000,seed=104033,original_always_end_zero=True,mask_only_always_single_character=True,both_matches_exhaustive_legal_argmax=True,
    synthetic_example=example,scope='Pure decoder only, no models or real labels. No quality result. Function axis error and triangle error are separate natural defects; correcting only triangle leaves wrong score matrix.',
    proposed_pre_score_followup='4 extra executions: axis-only and both x42/173. Preserve original 20 and gate; report 2x2 interaction as separate exploratory diagnostic. Freeze before first external score; no future candidate changes.')
with (R/'decoder-contract-pre-score.json').open('x') as f:json.dump(out,f,indent=2,sort_keys=True)
print(json.dumps(out))
