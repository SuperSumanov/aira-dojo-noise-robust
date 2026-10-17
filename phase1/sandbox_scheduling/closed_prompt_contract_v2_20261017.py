"""Role-specific correction of a diagnostic, without changing any experiment.

V1 joined Improve and Analyze prompts; requiring parent code in BOTH was wrong.
This separate immutable receipt selects the Improve metrics by recorded role.
"""
from collections import Counter
import json
from pathlib import Path
import re
import closed_adaptation_lineage_20261017 as m
from closed_prompt_contract_20261017 import ALL, prompts

def improve_prompts(node):
    roles=node['operators_used'];metrics=node['operators_metrics']
    assert len(roles)==len(metrics)
    assert roles.count('improve')==1
    return prompts(metrics[roles.index('improve')])

def main():
    for job,name,file,pin in ALL:
        root=Path('/research/d7/spc/yzyang4')/name
        dest=root/'prompt-contract-v2-20261017.safe.json'
        assert not dest.exists() and m.sha(root/file)==pin
        origin=m.load(root/file);rows=[];hashes={}
        for i in sorted({c['index'] for c in origin['candidates']}):
            rel=f'episode-{i}/checkpoint/journal.jsonl';path=root/rel
            assert m.sha(path)==origin['source_hashes'][rel];nodes=m.load(path,True)
            assert m.sha(path)==origin['source_hashes'][rel];hashes[rel]=m.sha(path)
            by_step={n['step']:n for n in nodes};assert len(by_step)==len(nodes)
            for c in (x for x in origin['candidates'] if x['index']==i and x['category'].startswith('improve_')):
                relc=f'episode-{i}/candidate-{c["candidate"]}.json';cp=root/relc
                assert m.sha(cp)==origin['source_hashes'][relc];receipt=m.load(cp)
                matches=[n for n in nodes if isinstance(n.get('code'),str) and m.codehash(n['code'])==receipt['code_sha256']]
                row={k:c[k] for k in ('index','candidate','block','task','category')}
                if len(matches)!=1:rows.append(row|dict(status='ambiguous_native_match'));continue
                n=matches[0];parents=n.get('parents',[])
                if len(parents)!=1 or parents[0] not in by_step:rows.append(row|dict(status='parent_unresolved'));continue
                parent=by_step[parents[0]];pp=improve_prompts(n)
                if not pp:rows.append(row|dict(status='no_recorded_improve_prompt'));continue
                assert isinstance(parent.get('code'),str) and parent['code']
                rows.append(row|dict(status='recorded',prompt_count=len(pp),
                    full_parent_in_all_improve_prompts=all(parent['code'] in x for x in pp),
                    full_parent_in_any_improve_prompt=any(parent['code'] in x for x in pp),
                    prompt_characters=[len(x) for x in pp],parent_characters=len(parent['code']),
                    explicit_five_fold=[bool(re.search(r'(?i)USE 5-FOLD CROSS-VALIDATION|PRINTS THE 5-FOLD CROSS-VALIDATION',x)) for x in pp],
                    numeric_cpu_mentions=[sorted(set(int(n) for n in re.findall(r'(?i)\b(\d+)\s*(?:cpu|CPU)',x))) for x in pp],
                    explicit_five_minutes=[bool(re.search(r'(?i)complete within 5 minutes',x)) for x in pp]))
        summary=dict(eligible_returned_improve=len(rows),statuses=dict(Counter(r['status'] for r in rows)),
            full_parent_all=sum(r.get('full_parent_in_all_improve_prompts',False) for r in rows),
            full_parent_any=sum(r.get('full_parent_in_any_improve_prompt',False) for r in rows),
            forced_five_fold=sum(any(r.get('explicit_five_fold',[])) for r in rows))
        out=dict(job=job,lineage_sha256=pin,reader_sha256=m.sha(__file__),helper_sha256=m.sha(m.__file__),
            v1_receipt_sha256=m.sha(root/'prompt-contract-20261017.safe.json'),
            source_hashes=hashes,rows=rows,summary=summary,
            correction='V1 erroneously required parent in subsequent Analyze prompts too; V2 selects the recorded Improve role only.',
            limits=['Returned Improve nodes only; not all attempts or an HTTP capture.',
                    'No prompt intervention, no proof of failure cause, no change to closed gates.'])
        with dest.open('x') as f:json.dump(out,f,indent=2,sort_keys=True,allow_nan=False)
        print(json.dumps(dict(job=job,sha256=m.sha(dest),summary=summary)),flush=True)

if __name__=='__main__':main()
