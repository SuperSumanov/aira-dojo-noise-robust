"""Anonymous-cost arithmetic replay; no tokenizer, models, or real data files."""
import argparse
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path


def verify(root):
    summary=json.loads((root/'summary.json').read_text())
    raw=(root/'diagnostic_costs.csv').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==summary['diagnostic_costs_sha256']
    groups=defaultdict(list)
    for row in csv.DictReader(raw.decode().splitlines()):
        key=(int(row['seed']),row['source']); seq=groups[key]
        assert int(row['ordinal'])==len(seq)
        cost=int(row['valid_tokens']); assert 1<=cost<=32768
        seq.append(cost)
    assert set(groups)=={(s,k) for s in (6,7,8) for k in ('G','L')}
    checks=[]
    for row in summary['rows']:
        costs=groups[row['seed'],row['source']]
        reference=sum(groups[row['seed'],'G'])+sum(groups[row['seed'],'L'])
        count=len(groups[row['seed'],'G'])+len(groups[row['seed'],'L'])
        assert count==row['same_pair_visits']==summary['combined_pair_visits']
        assert reference==row['G_to_L_valid_tokens']==summary['combined_valid_tokens']
        spend=sum(costs[i%len(costs)] for i in range(count))
        assert spend==row['same_pair_visits_valid_tokens'] and sum(costs)==row['source_once_valid_tokens']
        assert abs((spend/reference-1)-row['relative_valid_token_difference'])<1e-15
        spent=0; pairs=0
        while spent<reference:
            spent+=costs[pairs%len(costs)]; pairs+=1
            assert pairs<100000
        exact=row['exact_token_prefix']
        assert exact['reachable']==(spent==reference)
        assert exact['overshoot_tokens']==spent-reference
        assert exact['pairs' if spent==reference else 'pairs_if_next_included']==pairs
        checks.append({'seed':row['seed'],'source':row['source'],'counts_match':True,
                       'exact_token_prefix_reachable':spent==reference})
    return {'status':'PASS_ANONYMOUS_COST_ARITHMETIC_NOT_SAMPLER_APPROVAL','checks':checks,
        'new_data_files_opened':0,'model_fits':0,
        'summary_sha256':hashlib.sha256((root/'summary.json').read_bytes()).hexdigest(),
        'verifier_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path)
    print(json.dumps(verify(p.parse_args().root.resolve()),sort_keys=True))
