"""Closed error diagnosis; no grader or cached candidates."""
import json
from pathlib import Path
from audit_comparison_third_prefix_20260919 import core
from run_comparison_pizza_prefix_20260919 import old,prepared
ROOT=old.BASE/'comparison-pizza-prefix-20260919-0guhqznb'
p=prepared(ROOT);summary=old.read(ROOT/'summary.json')
rows=[]
for row in p['rows']:
    r,=[r for r in summary['rows'] if r['index']==row['index']]
    log=ROOT/f'output-{row["index"]}.private.log';raw=log.read_bytes()
    if old.sha(raw)!=r['log_sha256'] or old.SECRET.search(raw):raise ValueError('closed log identity/security')
    rows.append(dict(seed=row['seed'],historical_error=row['historical_error'],fresh_error=core(raw.decode()),log_sha256=old.sha(raw)))
print(json.dumps(dict(summary_sha256=old.sha((ROOT/'summary.json').read_bytes()),rows=rows),indent=2))
