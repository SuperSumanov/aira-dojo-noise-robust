"""Post-closure structural-only prompt diff; no text/quality export."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import re

root=Path('/research/d7/spc/yzyang4/scheduling-weight-effort-20261014-v4')
assert (root/'closed.json').exists()
plan=json.loads((root/'plan.json').read_text())
identity=json.loads((root/'runtime-prompt-identity.json').read_text())
prompts=[]
for row in plan['schedule']:
    ep=root/f"episode-{row['index']}"
    found=None
    for line in (ep/'worker.private.log').read_text(errors='replace').splitlines():
        marker='Improve Node Created - Metrics: '
        if marker not in line:continue
        part=re.sub(r'\x1b\[[0-9;]*m','',line.split(marker,1)[1])
        found=ast.literal_eval(part)['prompt_messages']
        break
    assert found is not None, f"no prompt record index={row['index']}"
    digest=hashlib.sha256(json.dumps(found,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    assert digest==identity['rows'][row['index']]['prompt_sha256']
    prompts.append(found)

out=[]
for slot in range(8):
    for block in range(1,4):
        i=slot+8*block
        assert len(prompts[slot])==len(prompts[i])
        diffs=[]
        for k,(a,b) in enumerate(zip(prompts[slot],prompts[i])):
            assert a['role']==b['role']
            aa,bb=a['content'].splitlines(),b['content'].splitlines()
            for kind,x,y,u,v in difflib.SequenceMatcher(a=aa,b=bb,autojunk=False).get_opcodes():
                if kind=='equal':continue
                left,right=aa[x:y],bb[u:v]
                both=left+right
                numeric=lambda lines: re.sub(r'\d+(?:\.\d+)?','N','\n'.join(lines))
                identifiers=lambda lines: re.sub(r'\b[a-fA-F0-9]{8,}(?:-[a-fA-F0-9]{4,})*\b','<ID>','\n'.join(lines))
                templates=[]
                if slot==0 and block==1 and all(len(s)<150 for s in both):
                    assert not any(re.search(r'sk-|Bearer|api.?key|primary.?key|password',s,re.I) for s in both)
                    templates=[identifiers([s]) for s in both]
                headings=lambda lines: [name for name in ('Previous Solution','Memory','Summary','Code','Metric','Analysis','Instructions')
                    if any(s.lstrip().startswith('#') and name.lower() in s.lower() for s in lines)]
                guard=lambda lines: re.sub(r'kernel-shutdown-guard-installed-[A-Za-z0-9_-]+\.json','kernel-shutdown-guard-installed-<NONCE>.json','\n'.join(lines))
                anomaly=[]
                if i==25 and len(right)<=4:
                    assert not any(re.search(r'sk-|Bearer|api.?key|primary.?key|password',s,re.I) for s in right)
                    anomaly=right
                diffs.append(dict(message=k,kind=kind,left_lines=[x,y],right_lines=[u,v],
                    left_chars=sum(map(len,left)),right_chars=sum(map(len,right)),
                    package_enumeration=all('packages installed:' in s for s in both),
                    budget_related=all(re.search(r'\b(time|seconds|budget|remaining)\b',s,re.I) for s in both),
                    same_word_multiset=sorted(' '.join(left).split())==sorted(' '.join(right).split()),
                    numeric_only_change=numeric(left)==numeric(right),
                    identifier_only_change=identifiers(left)==identifiers(right),
                    safe_identifier_templates=templates, left_heading_classes=headings(left),right_heading_classes=headings(right),
                    guard_filename_only_change=guard(left)==guard(right),safe_anomaly_lines=anomaly))
        out.append(dict(reference=slot,index=i,differences=diffs))
result=dict(comparisons=out,first_returned_prompt_digests_reproduced=32,
            diagnostic_only=True,original_exact_prompt_gate=False,original_receipt_unchanged=True)
with (root/'runtime-prompt-difference-diagnostic.json').open('x') as f:
    json.dump(result,f,indent=2,sort_keys=True)
print(json.dumps(result))
