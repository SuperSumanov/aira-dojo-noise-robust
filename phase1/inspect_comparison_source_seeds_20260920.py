"""Structural availability only, no result fields or raw source text."""
import json
import run_comparison_spooky_pool_20260919 as base
structure=base.read(base.INPUT/'structure.redacted.json',base.STRUCTURE)
rows=[]
for archive in structure['archives']:
    seeds=[]
    for c in archive['configs']:
        f=c['fields']
        if '/forets-1/' in c['path'] and f.get('solver.operators.draft.llm.client.model_id')=='qwen3.8-27b' and f.get('metadata.launch_time','')[:10]>='2026-09-12':
            seeds.append(f.get('metadata.seed'))
    rows.append(dict(task=archive['archive'].removesuffix('.tar.gz'),seeds=sorted(seeds)))
print(json.dumps(dict(structure_sha256=base.STRUCTURE,available=rows)))
