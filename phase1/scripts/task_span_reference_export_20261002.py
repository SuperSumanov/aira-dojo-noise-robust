"""Add reproducibility columns to frozen summary rows; never fit or rescore."""
import csv
import hashlib
import json
import sys
from pathlib import Path

def main(root):
    plan=json.loads((root/'plan.json').read_bytes())
    summary=json.loads((root/'summary.json').read_bytes())
    verification=json.loads((root/'verification.json').read_bytes())
    assert verification['status']=='PASS'
    assert hashlib.sha256((root/'summary.json').read_bytes()).hexdigest()==verification['summary_sha256']
    records=[dict(task='tweet-sentiment-extraction',arm='classical_token_span_with_frozen_neutral_rule',
                  source_commit=plan['source_commit'],source_sha256=plan['script_sha256'],
                  total_cpu_wall_cap_seconds=plan['hard_wall_seconds'],cpu_threads=plan['cpu_threads'],
                  total_fits=plan['total_fits'],new_gpu=0,agent_calls=0,
                  training_rows=plan['train_rows'],development_rows=plan['query_rows'],
                  model_json=json.dumps(plan['model'],sort_keys=True),versions_json=json.dumps(plan['versions'],sort_keys=True),
                  **r) for r in summary['rows']]
    with (root/'rows-repro.csv').open('x',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    print(json.dumps(dict(rows=len(records),median=summary['seed_score_median'],
                          median_difference_original=summary['seed_score_median']-summary['baselines']['original_plus_rule'],
                          median_difference_strong=summary['seed_score_median']-summary['baselines']['historical_strong_F_plus_rule'],
                          sample_variance=summary['seed_score_sample_variance'],summary_sha256=verification['summary_sha256']),sort_keys=True))

if __name__=='__main__': main(Path(sys.argv[1]))
