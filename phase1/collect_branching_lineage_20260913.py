"""Closed development lineage, actual interventions, and immutable next-budget facts."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from forets_environment_build_20260912 import read,write,encode,sha
from verify_branching_selection_20260913 import replay
ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-y_p2tlmi')

def main():
    finish=read(ROOT/'readout-finished.json');assert finish['status']=='verified'
    summary=read(ROOT/'common-start-summary.json',finish['files']['common-start-summary.json'])
    rows=[]
    for r in summary['rows']:
        directory=ROOT/'runs'/r['run_id']/'checkpoint';p=directory/'journal.jsonl'
        nodes=[json.loads(x) for x in p.read_bytes().splitlines() if x.strip()] if p.exists() else []
        matching=[n for n in nodes if sha(n['code'].encode())==r['selected_code_sha256']]
        pools=[]
        for p in sorted((directory/'forets-candidates-private').glob('batch-*.sqlite')):
            before=sha(p.read_bytes())
            with closing(sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)) as db:
                raw,digest=db.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchone()
            if sha(raw.encode())!=digest or sha(p.read_bytes())!=before:raise ValueError('snapshot drift')
            v=json.loads(raw);n=len(v['candidates']);binding=v['binding']
            if v['selected'] is None:continue
            uniform=replay(n,None,'uniform_random',r['seed'],r['task'],binding['step'])
            selected=v['selected'];scores=[c['score'] for c in v['candidates']]
            ranked=sorted(scores,reverse=True) if all(s is not None for s in scores) else None
            sources=[]
            for c in v['task_calls']:
                if c['intent']['code_sha256']==r['selected_code_sha256']:
                    sources.append(dict(role=c['intent']['role'],slot=c['slot'],call_state=c['state'],
                        same_pool_uniform_would_attempt_slot=c['slot'] in uniform,
                        candidate_original_same_code=sha(v['candidates'][c['slot']]['node']['code'].encode())==r['selected_code_sha256']))
            pools.append(dict(step=binding['step'],phase=v['phase'],pool_width=n,
                actual_slots=selected,same_pool_uniform_slots=uniform,
                selected_set_changed=set(selected)!=set(uniform),order_changed=selected!=uniform,
                strict_top2_boundary=(ranked[1]>ranked[2]) if ranked and len(ranked)>2 else None,
                final_program_sources=sources))
        rows.append(dict(run_id=r['run_id'],technical_eligible=r['technical_eligible'],improvement=r['improvement'],
            final_program_journal_nodes=[dict(step=n['step'],parents=n['parents'],is_buggy=n['is_buggy']) for n in matching],pools=pools))
    result=dict(role='posthoc_lineage_not_counterfactual_score',source_tree=summary['source_tree'],rows=rows,
        limitation='Uniform slots are replayed on the critic observed pool only. No claim about unexecuted scores, alternative downstream generations, ordering-mediated gain, or causal attribution.')
    print(json.dumps(dict(lineage_sha256=write(ROOT/'branching-lineage.json',encode(result)),rows=rows)))
    with closing(sqlite3.connect((ROOT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        auth=db.execute('SELECT digest,stopped FROM auth').fetchall();calls=db.execute('SELECT * FROM calls ORDER BY id').fetchall()
    expected='ee05b65d5870a607144bed13bdcd474337cd5b46228552fdf36d0ca6df74c9a5'
    if auth!=[(expected,0)]:raise ValueError('parent auth changed')
    facts=dict(root=str(ROOT),source_tree=summary['source_tree'],prepared_sha256=sha((ROOT/'prepared.json').read_bytes()),
        authorization=expected,finish_sha256=sha((ROOT/'readout-finished.json').read_bytes()),calls_sha256=sha(encode(calls)),
        billing_counts=[len(calls),sum(r[2] for r in calls),sum(r[3] or 0 for r in calls),sum(r[4]=='unresolved' for r in calls)])
    print(json.dumps(dict(facts=facts,sha256=write(ROOT/'reference-parent-facts.json',encode(facts)))))

if __name__=='__main__':main()
