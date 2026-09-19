"""Independent join from published pool CSV, not producer's root selection code."""
import argparse,csv,hashlib,json,math,statistics
from collections import Counter
from pathlib import Path


def main(root):
    result=json.loads((root/'cost-diagnostic.json').read_bytes())
    nodes=json.loads((root/'nodes.json').read_bytes())
    meta=json.loads((root/'operator-cost-metadata.json').read_bytes())
    with (root/'root_pool_inventory.csv').open(newline='') as handle:inventory=list(csv.DictReader(handle))
    nmap={(n['run'],n['id']):n for n in nodes};mmap={(n['run'],n['node']):n for n in meta}
    assert len(inventory)==150 and len({(x['run'],x['node']) for x in inventory})==150
    verified=[]
    for pool in result['root_pools']:
        rr=[x for x in inventory if x['run']==pool['run']];assert len(rr)==6
        latencies=[];executions=[];graded_selected=0
        for item in rr:
            key=(item['run'],item['node']);n=nmap[key];m=mmap[key]
            assert n['code_sha256']==item['code_sha256']
            latencies.append(m['numeric_operator_fields']['.0.usage.latency'])
            if item['originally_executed']=='True':
                assert n['group']=='executed'
                executions.append(n['exec_time'])
                graded_selected+=not n['is_buggy'] and isinstance(n['score'],(int,float)) and math.isfinite(n['score'])
        assert len(executions)==2
        assert sorted(latencies)==pool['six_request_latencies_seconds']
        assert max(latencies)==pool['longest_request_seconds']
        assert math.isclose(sum(executions),pool['selected_execution_sum_seconds'],rel_tol=1e-12)
        verified.append(dict(run=pool['run'],stratum=pool['stratum'],selected_with_nonbuggy_finite_external_grade=graded_selected))
    assert len(verified)==25
    receipt=dict(status='INDEPENDENT_COST_JOIN_PASS',pools=len(verified),
        selected_grade_counts=dict(Counter(v['selected_with_nonbuggy_finite_external_grade'] for v in verified)),
        detail=verified,sha256={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in
                              ('cost-diagnostic.json','root_pool_inventory.csv','operator-cost-metadata.json','nodes.json')})
    with (root/'cost-independent.json').open('x') as handle:json.dump(receipt,handle,indent=2)
    print(json.dumps({k:v for k,v in receipt.items() if k!='detail'},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);main(p.parse_args().root)
