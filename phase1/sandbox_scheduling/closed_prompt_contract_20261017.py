"""Inspect recorded Improve prompts, not replayed/template-only inputs.

Exact returned-code/native-node join; export booleans/counts/lengths only.
No prompt, code, credentials, prediction, or label text leaves the DEV roots.
"""
from collections import Counter
import json
from pathlib import Path
import re
import closed_adaptation_lineage_20261017 as m
from closed_parent_delta_20261017 import SPECS

ALL=SPECS+((18412,'scheduling-metric-deployment-20261015-v2','adaptation-lineage-20261017.safe.json',
            '45400a0d57b706268343287a9e0d438e4077b992f13c427e786c394416aba0cc'),)

def prompts(value):
    result=[]
    if isinstance(value,dict):
        for k,v in value.items():
            if k=='prompt_messages':
                assert isinstance(v,list)
                text=[]
                for x in v:
                    assert isinstance(x,dict) and isinstance(x.get('content'),str)
                    text.append(x['content'])
                result.append('\n'.join(text))
            else:result.extend(prompts(v))
    elif isinstance(value,list):
        for x in value:result.extend(prompts(x))
    return result

def main():
    for job,name,file,pin in ALL:
        root=Path('/research/d7/spc/yzyang4')/name;dest=root/'prompt-contract-20261017.safe.json'
        assert not dest.exists() and m.sha(root/file)==pin
        origin=m.load(root/file);rows=[];hashes={}
        for i in sorted({c['index'] for c in origin['candidates']}):
            rel=f'episode-{i}/checkpoint/journal.jsonl';path=root/rel
            assert m.sha(path)==origin['source_hashes'][rel];nodes=m.load(path,True)
            assert m.sha(path)==origin['source_hashes'][rel];hashes[rel]=m.sha(path)
            by_step={n['step']:n for n in nodes};assert len(by_step)==len(nodes)
            returns=[c for c in origin['candidates'] if c['index']==i]
            for c in returns:
                if not c['category'].startswith('improve_'):continue
                relc=f'episode-{i}/candidate-{c["candidate"]}.json';cp=root/relc
                assert m.sha(cp)==origin['source_hashes'][relc];receipt=m.load(cp)
                matches=[n for n in nodes if isinstance(n.get('code'),str) and m.codehash(n['code'])==receipt['code_sha256']]
                row={k:c[k] for k in ('index','candidate','block','task','category')}
                if len(matches)!=1:rows.append(row|dict(status='ambiguous_native_match'));continue
                n=matches[0];parents=n.get('parents',[])
                if len(parents)!=1 or parents[0] not in by_step:rows.append(row|dict(status='parent_unresolved'));continue
                parent=by_step[parents[0]];pp=prompts(n.get('operators_metrics',[]))
                if not pp:rows.append(row|dict(status='no_recorded_prompt'));continue
                assert isinstance(parent.get('code'),str) and parent['code']
                rows.append(row|dict(status='recorded',prompt_count=len(pp),
                    full_parent_in_all_prompts=all(parent['code'] in x for x in pp),
                    prompt_characters=[len(x) for x in pp],parent_characters=len(parent['code']),
                    explicit_five_fold=[bool(re.search(r'(?i)USE 5-FOLD CROSS-VALIDATION|PRINTS THE 5-FOLD CROSS-VALIDATION',x)) for x in pp],
                    claims_six_cpus=[bool(re.search(r'(?i)6 CPUs available',x)) for x in pp],
                    claims_two_cpus=[bool(re.search(r'(?i)2 CPUs available',x)) for x in pp],
                    explicit_five_minutes=[bool(re.search(r'(?i)complete within 5 minutes',x)) for x in pp]))
        summary=dict(eligible_returned_improve=len(rows),statuses=dict(Counter(r['status'] for r in rows)),
            full_parent_all=sum(r.get('full_parent_in_all_prompts',False) for r in rows),
            forced_five_fold=sum(any(r.get('explicit_five_fold',[])) for r in rows),
            claims_six_cpus=sum(any(r.get('claims_six_cpus',[])) for r in rows),
            claims_two_cpus=sum(any(r.get('claims_two_cpus',[])) for r in rows))
        out=dict(job=job,lineage_sha256=pin,reader_sha256=m.sha(__file__),helper_sha256=m.sha(m.__file__),
            source_hashes=hashes,rows=rows,summary=summary,
            limits=['Recorded client-side prompts, not server HTTP capture or a prompt intervention.',
                    'Template wording mismatch can coexist with fair identical treatment inputs; it does not invalidate all earlier comparisons.',
                    'No proof that instructions caused failure. Do not modify closed protocols or claim prompt fixes as method gains.'])
        with dest.open('x') as f:json.dump(out,f,indent=2,sort_keys=True,allow_nan=False)
        print(json.dumps(dict(job=job,sha256=m.sha(dest),summary=summary)),flush=True)

if __name__=='__main__':main()
