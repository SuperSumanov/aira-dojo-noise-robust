"""Recover export ONLY: preserve partial CSV, all frozen rules/scores unchanged."""
import csv,hashlib,json
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/task-feedback-public-rule-20261002-v1')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
s=R/'summary.json';before=sha(s);data=json.loads(s.read_bytes());rows=data['rows']
assert len(rows)==data['full_denominator']==9
assert sum(r['baseline'] is not None for r in rows)==data['valid_sources']
assert all(r.get('independent_match') is True for r in rows if r['baseline'] is not None)
keys=list(dict.fromkeys(k for r in rows for k in r))
dest=R/'rows-v2.csv'
with dest.open('x',newline='') as f:
    w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
with dest.open(newline='') as f:out=list(csv.DictReader(f))
assert len(out)==9 and sha(s)==before
review=dict(status='EXPORT_ONLY_FIXED',summary_sha256=before,original_partial_csv_sha256=sha(R/'rows.csv'),
    corrected_csv_sha256=sha(dest),rows=9,
    reason='first row was a missing endpoint; optional independent_match appeared only on scored rows; writer used first-row keys',
    experiment_rerun=False,rule_or_score_changed=False,original_preserved=True)
with (R/'export-review.json').open('x') as f:json.dump(review,f,sort_keys=True,indent=2);f.write('\n')
print(json.dumps(data,sort_keys=True));print(json.dumps(review,sort_keys=True))
