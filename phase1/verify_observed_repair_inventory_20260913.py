"""Independent reconstruction from old journals; no generator helper reused."""
import ast
from collections import Counter
import difflib
import json
import math
from pathlib import Path
import stat
from forets_environment_build_20260912 import read, write, encode, sha
from audit_closed_error_families_20260913 import BASE, SECRET

ROOT=BASE/'forets-repair-memory-inventory-20260913-vcg12_1y'
PUBLIC='825e8c253e72200a64be2edf9e45919cb1be21fb9fcc9b98550f5681133a8095'
SOURCE_COMMIT='b2593046982ff57e244377f08ce8e2f75c72a1a9'


def key(row): return row['root'],row['run_id'],row['parent_step'],row['child_step']


def main():
    public=read(ROOT/'inventory-public.json',PUBLIC)
    private_path=ROOT/'observed-repair-code.private.json'
    if private_path.is_symlink() or stat.S_IMODE(private_path.stat().st_mode)!=0o600:
        raise ValueError('private code permissions')
    private=read(private_path,public['private_inventory_sha256'])['rows']
    if sha(Path(__file__).with_name('build_observed_repair_memory_20260913.py').read_bytes())!=public['script_sha256']:
        raise ValueError('exact executed builder bytes')
    pub={key(r):r for r in public['rows']}; priv={key(r):r for r in private}
    if len(pub)!=len(public['rows']) or len(priv)!=len(private): raise ValueError('duplicate inventory identity')
    expected={}
    for proof in public['source_proofs']:
        path=BASE/proof['root']/'runs'/proof['run_id']/'checkpoint/journal.jsonl'
        raw=path.read_bytes()
        if sha(raw)!=proof['journal_sha256'] or SECRET.search(raw.decode()): raise ValueError('source integrity')
        nodes=[json.loads(line) for line in raw.splitlines()]
        index={n['step']:n for n in nodes}
        if len(index)!=len(nodes): raise ValueError('duplicate source step')
        for child in nodes:
            if 'debug' not in child.get('operators_used',[]) or child.get('exec_time') is None: continue
            if not isinstance(child.get('parents'),list) or len(child['parents'])!=1: raise ValueError('debug linkage')
            pstep=child['parents'][0]
            if pstep>=child['step']: raise ValueError('source chronology')
            parent=index.get(pstep)
            if parent is None or parent.get('exec_time') is None or parent.get('exit_code') in (None,0): continue
            validity=(child.get('metric_info') or {}).get('valid_submission',child.get('metric_info/valid_submission'))
            value=child.get('metric')
            if (child.get('exit_code')!=0 or validity!=1 or child.get('is_buggy') is not False or
                type(value) not in (int,float) or not math.isfinite(value) or parent['code']==child['code']): continue
            identity=(proof['root'],proof['run_id'],pstep,child['step'])
            expected[identity]=(parent['code'],child['code'])
    if set(expected)!=set(pub) or set(expected)!=set(priv): raise ValueError('complete independent eligibility differs')
    counts=[]
    for identity,(before,after) in expected.items():
        p=priv[identity]; q=pub[identity]
        if p['parent_code']!=before or p['observed_successful_child_code']!=after: raise ValueError('source code not exact')
        ast.parse(before); ast.parse(after)
        diff=''.join(difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),
            fromfile='observed_parent.py',tofile='observed_debug_child.py'))
        if p['observed_diff']!=diff: raise ValueError('source diff not exact')
        for field, text in [('parent_code_sha256',before),('child_code_sha256',after),('diff_sha256',diff)]:
            if p[field]!=sha(text.encode()) or q[field]!=p[field]: raise ValueError('content identity')
        if q!={k:v for k,v in p.items() if k not in ('parent_code','observed_successful_child_code','observed_diff')}:
            raise ValueError('public export not exact code-free projection')
        counts.append(dict(task=q['task'],added_lines=q['added_lines'],removed_lines=q['removed_lines'],
            code_pair_sha256=sha((q['parent_code_sha256']+q['child_code_sha256']).encode())))
    result=dict(status='INDEPENDENT_OLD_SOURCE_ELIGIBILITY_AND_EXACT_CODE_VERIFIED',
        inventory_public_sha256=PUBLIC,private_inventory_sha256=public['private_inventory_sha256'],
        executed_builder_commit=SOURCE_COMMIT,executed_builder_sha256=public['script_sha256'],
        transitions=len(expected),tasks=dict(Counter(q['task'] for q in pub.values())),
        patch_sizes=counts,private_code_mode='0600',api_calls=0,gpu_jobs=0,
        limitations='Independent archival verification only. No rerun, portable repair guarantee, memory efficacy, or novelty claim.',
        verifier_sha256=sha(Path(__file__).read_bytes()))
    digest=write(ROOT/'inventory-verification.json',encode(result))
    print(json.dumps(dict(sha256=digest,**result)))


if __name__=='__main__': main()
