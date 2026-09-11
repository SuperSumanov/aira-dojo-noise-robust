"""Post-closeout replay of selector decisions on all seed11 candidate pools.

No model call, candidate execution, score export or protected-cohort access.
This checks that the planned intervention actually happened, not its causality.
"""
from contextlib import closing
import ast
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sqlite3
import sys

ROOT=Path('/research/d7/spc/yzyang4/forets-review-20260912-csh5q4i8')
PREPARED='e6ec9d4c6664a98a6c069b13cb85624ece78b864adf036591ed34f4c8df18718'
SEED=11


def code_contrast(codes, selected, uniform):
    """Byte/AST equality only, not semantic equivalence or usefulness."""
    if not codes or any(not isinstance(c,str) for c in codes):raise ValueError('missing code')
    if any(type(i) is not int or not 0<=i<len(codes) for i in (selected,uniform)):
        raise ValueError('invalid selected slot')
    normalized=[]
    for code in codes:
        try:normalized.append(ast.dump(ast.parse(code),include_attributes=False))
        except (SyntaxError,ValueError,RecursionError):normalized.append(None)
    complete=all(n is not None for n in normalized)
    return dict(unique_raw_programs=len(set(codes)),
        unique_ast_programs=len(set(normalized)) if complete else None,
        ast_parse_failures=sum(n is None for n in normalized),
        selected_raw_differs_from_same_pool_uniform=codes[selected]!=codes[uniform],
        selected_ast_differs_from_same_pool_uniform=(normalized[selected]!=normalized[uniform])
            if normalized[selected] is not None and normalized[uniform] is not None else None)


def replay(count, scores, policy, coupling, seed, task, step):
    if policy=='uniform_random':eligible=list(range(count))
    elif policy=='critic_topk_random':
        if len(scores)!=count or any(type(x) not in (int,float) or not math.isfinite(x) for x in scores):
            raise ValueError('incomplete finite scores')
        eligible=sorted(sorted(range(count),key=lambda slot:(-scores[slot],slot))[:2])
    else:raise ValueError('wrong policy')
    if coupling=='independent_subset_v2':
        identity={'domain':'forets-selector-v2','seed':seed,'task':task,'step':step}
    elif coupling=='common_priority_v1':
        identity={'version':'forets-common-priority-v1','seed':seed,'task':task,'step':step,'purpose':'selection_order'}
    else:raise ValueError('wrong coupling')
    key=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    rng=random.Random(key)
    if coupling=='independent_subset_v2':return rng.sample(eligible,1)
    order=list(range(count));rng.shuffle(order)
    return [slot for slot in order if slot in eligible][:1]


def main():
    os.environ['SLURM_CONF']='/opt1/slurm/gpu-slurm.conf';sys.path.insert(0,str(ROOT/'code'))
    from forets_block_collect_20260911 import collect_metadata
    raw=(ROOT/'prepared.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PREPARED:raise ValueError('preparation changed')
    prepared=json.loads(raw);collect_metadata(ROOT,prepared)
    if not (ROOT/'independent-final-verification.json').is_file():raise ValueError('finals not yet independently checked')
    rows=[];files={}
    for run in prepared['run_configs']:
        path=ROOT/'configs'/(run['run_id']+'.json');cfg=json.loads(path.read_text())['solver']
        if (cfg['critic_top_k'],cfg['num_children_to_choose'],cfg['selector_seed'])!=(2,1,SEED):raise ValueError('different selector contract')
        directory=ROOT/'runs'/run['run_id']/'checkpoint/forets-candidates-private'
        if list(directory.glob('*.lock')):raise ValueError('unfinished pool')
        for path in sorted(directory.glob('batch-*.sqlite')):
            if path.is_symlink() or path.stat().st_size>32*1024*1024:raise ValueError('unsafe ledger')
            before=hashlib.sha256(path.read_bytes()).hexdigest()
            with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
                records=db.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchall()
            if len(records)!=1:raise ValueError('ambiguous snapshot')
            raw,digest=records[0]
            if hashlib.sha256(raw.encode()).hexdigest()!=digest:raise ValueError('snapshot hash')
            payload=json.loads(raw);binding=payload['binding'];candidates=payload['candidates']
            count=len(candidates)
            if (binding['task']!=run['task'] or binding['selection_policy']!=run['arm'] or
                payload['phase']!='complete' or count!=min(cfg['num_children'],cfg['step_limit']-binding['step'])):
                raise ValueError('pool binding')
            scores=[c['score'] for c in candidates]
            bypass=bool(cfg.get('skip_redundant_critic',False) and run['arm']=='critic_topk_random' and count<=2)
            if bypass!=(binding.get('score_bypass')=='full_pool_no_pruning'):raise ValueError('unexpected score bypass')
            effective='uniform_random' if bypass else run['arm']
            if effective=='uniform_random' and any(x is not None for x in scores):raise ValueError('unplanned critic scores')
            expected=replay(count,scores,effective,binding['selection_coupling'],SEED,run['task'],binding['step'])
            if payload['selected']!=expected:raise ValueError('selector replay mismatch')
            calls=payload['task_calls'];candidate_calls=[c for c in calls if c['intent']['role']=='candidate']
            if len(candidate_calls)!=1 or candidate_calls[0]['slot']!=expected[0]:raise ValueError('wrong candidate actually executed')
            if any(c['slot']!=expected[0] or c['state']!='returned' for c in calls):raise ValueError('wrong or incomplete execution')
            widths=[len(c['node']['code'] or '') for c in candidates]
            ranked=sorted(scores,reverse=True) if effective=='critic_topk_random' else []
            uniform=replay(count,None,'uniform_random',binding['selection_coupling'],SEED,run['task'],binding['step'])
            rows.append(dict(run_id=run['run_id'],task=run['task'],arm=run['arm'],step=binding['step'],
                pool_width=count,replayed_selection_matches=True,selected_candidate_executed=True,score_bypassed=bypass,
                critic_top2_boundary_strict=(ranked[1]>ranked[2]) if len(ranked)>2 else None,
                differs_from_same_pool_uniform=(expected!=uniform) if ranked else None,
                candidate_code_max_characters=max(widths),critic_character_truncations=sum(n>40000 for n in widths) if ranked else 0,
                **code_contrast([c['node']['code'] for c in candidates],expected[0],uniform[0])))
            if hashlib.sha256(path.read_bytes()).hexdigest()!=before:raise ValueError('ledger changed')
            files[str(path.relative_to(ROOT))]=before
    report=dict(utc=datetime.now(timezone.utc).isoformat(),root=str(ROOT),seed=SEED,rows=rows,all_pools=len(rows),
        strict_critic_pools=sum(r['critic_top2_boundary_strict'] is True for r in rows),
        critic_pools_with_changed_selection=sum(r['differs_from_same_pool_uniform'] is True for r in rows),
        actual_candidate_code_exported=False,critic_scores_exported=False,ledger_sha256=files,
        verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        limitations=['Replayed intervention, not proof that unexecuted candidates were worse.',
                    'Same-pool random is an unexecuted choice comparison, not a counterfactual score.',
                    'Character truncation check does not establish tokenizer-context completeness.',
                    'AST equality removes formatting/comments only; differences need not imply different behavior.'])
    with (ROOT/'independent-selection-verification.json').open('x') as stream:json.dump(report,stream,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in report.items() if k not in ('rows','ledger_sha256')}))


if __name__=='__main__':main()
