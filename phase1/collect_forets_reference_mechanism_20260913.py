"""Only after full reference-matrix readout: lineage, costs, next-state facts."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from forets_environment_build_20260912 import read,write,encode,sha
from verify_branching_selection_20260913 import replay

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-5_czzimk')
AUTH='96191b7393556fc5c978d82d2f3f2789ffb5f8c8c0243605b425df6843c07540'

def main():
    finish=read(ROOT/'readout-finished.json')
    if finish['status']!='verified':raise ValueError('whole matrix closure')
    summary=read(ROOT/'common-start-summary.json',finish['files']['common-start-summary.json'])
    if summary['source_tree']!='f1cdee3a9e553e8efeedaa1a66a2c6bd778f9798':raise ValueError('source')
    rows=[]
    for r in summary['rows']:
        cp=ROOT/'runs'/r['run_id']/'checkpoint';jp=cp/'journal.jsonl'
        nodes=[json.loads(x) for x in jp.read_bytes().splitlines()] if jp.exists() else []
        selected_node=None
        if r['selected_step'] is not None:
            directory=ROOT/'incumbents'/r['run_id']
            commit=read(directory/f"step-{r['selected_step']:06d}.commit.json")
            chosen=read(directory/commit['data_file'],commit['data_sha256'])
            selected_node=chosen['node_id']
            if sha(chosen['code'].encode())!=r['selected_code_sha256']:raise ValueError('selected receipt drift')
        matches=[n for n in nodes if n['id']==selected_node and sha(n['code'].encode())==r['selected_code_sha256']]
        pools=[]
        for p in sorted((cp/'forets-candidates-private').glob('batch-*.sqlite')):
            before=sha(p.read_bytes())
            with closing(sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)) as db:
                raw,h=db.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchone()
            if sha(raw.encode())!=h or sha(p.read_bytes())!=before:raise ValueError('pool drift')
            v=json.loads(raw)
            if v['selected'] is None:continue
            step=v['binding']['step'];cs=v['candidates'];uniform=replay(len(cs),None,'uniform_random',r['seed'],r['task'],step)
            origin=[]
            for call in v['task_calls']:
                if call['intent']['code_sha256']==r['selected_code_sha256']:
                    origin.append(dict(role=call['intent']['role'],slot=call['slot'],state=call['state'],
                        same_pool_uniform_would_attempt_slot=call['slot'] in uniform,
                        same_as_unmodified_candidate=sha(cs[call['slot']]['node']['code'].encode())==r['selected_code_sha256'],
                        original_candidate_identity_matches=cs[call['slot']]['node']['id']==selected_node))
            pools.append(dict(step=step,phase=v['phase'],actual_slots=v['selected'],same_pool_uniform_slots=uniform,
                selected_set_changed=set(v['selected'])!=set(uniform),order_changed=v['selected']!=uniform,
                final_program_sources=origin,pool_sha256=before))
        source_matches=sum(len(p['final_program_sources']) for p in pools)
        rows.append(dict(run_id=r['run_id'],technical_eligible=r['technical_eligible'],improvement=r['improvement'],
            final_code_call_matches=source_matches,code_only_lineage_ambiguous=source_matches>1,
            final_program_journal_nodes=[dict(step=n['step'],parents=n['parents'],is_buggy=n['is_buggy']) for n in matches],pools=pools))
    result=dict(role='reference_posthoc_lineage_not_counterfactual_score',rows=rows,source_tree=summary['source_tree'],
        summary_sha256=finish['files']['common-start-summary.json'],inspector_sha256=sha(Path(__file__).read_bytes()),
        limitation='Uniform replay uses only the same observed pool. No unexecuted outcome or alternative future trajectory is claimed.')
    digest=write(ROOT/'reference-lineage.json',encode(result))
    print(json.dumps(dict(lineage_sha256=digest,rows=rows)))
    import analyze_branching_mechanism_20260913 as mechanism
    mechanism.ROOT=ROOT;mechanism.run()
    with closing(sqlite3.connect((ROOT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        auth=db.execute('SELECT digest,stopped FROM auth').fetchall()
        calls=db.execute('SELECT * FROM calls ORDER BY id').fetchall()
    if auth!=[(AUTH,0)]:raise ValueError('parent billing changed')
    facts=dict(root=str(ROOT),source_tree=summary['source_tree'],prepared_sha256=sha((ROOT/'prepared.json').read_bytes()),
        authorization=AUTH,finish_sha256=sha((ROOT/'readout-finished.json').read_bytes()),calls_sha256=sha(encode(calls)),
        billing_counts=[len(calls),sum(r[2] for r in calls),sum(r[3] or 0 for r in calls),sum(r[4]=='unresolved' for r in calls)])
    print(json.dumps(dict(facts=facts,sha256=write(ROOT/'action-parent-facts.json',encode(facts)))))

if __name__=='__main__':main()
