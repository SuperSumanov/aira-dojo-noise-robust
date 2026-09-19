"""Explain grader probability warnings using predictions only, no labels."""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd

base=Path('/research/d7/spc/yzyang4')
roots={'comparison-pool-20260919-7ujiaajp':'238bd65e00edd0f678b1f9dc6fbce0c92bf49247030765b64c703ed4d469547a',
       'comparison-pool-20260919-1z7l72bz':'051c550d80b3d9fa50d592f6a615d1ebb02c14a87c6c2dbf0a861b928b52bae4'}
out=[]
for name,expected in roots.items():
    root=base/name;raw=(root/'summary.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('closed summary identity')
    for r in json.loads(raw)['rows']:
        if r['valid'] is not True:continue
        p=root/f"work-{r['index']}/submission.csv"
        meta=json.loads((root/f"result-{r['index']}.json").read_bytes())
        if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=meta['submission_sha256']:raise ValueError('prediction identity')
        values=pd.read_csv(p).drop(columns='id').to_numpy(dtype=float)
        sums=values.sum(axis=1)
        out.append(dict(seed=r['seed'],slot=r['slot'],max_row_sum_absolute_deviation=float(np.max(np.abs(sums-1))),
                        all_finite=bool(np.isfinite(values).all()),within_independent_tolerance=bool(np.allclose(sums,1,rtol=1e-5,atol=1e-6))))
result=dict(rows=out,no_labels_read=True,no_normalization_or_results_changed=True)
with (base/'comparison-pool-20260919-1z7l72bz/probability-sum-check.json').open('x') as handle:json.dump(result,handle,indent=2,allow_nan=False)
print(json.dumps(result,indent=2))
