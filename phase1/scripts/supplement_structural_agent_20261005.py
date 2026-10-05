"""Descriptive post-closure mechanism and cost checks; never changes the gate.

Only aggregate syntax descriptors leave the remote host, never program text.
AST matches describe written constructors, not semantic correctness.
"""
import ast,csv,json,statistics
from structural_agent_20261005 import R,PREV,c,read,write,sha,check

def describe(code):
    tree=ast.parse(code);calls=[];analyzers=[]
    for node in ast.walk(tree):
        if not isinstance(node,ast.Call):continue
        name=node.func.id if isinstance(node.func,ast.Name) else node.func.attr if isinstance(node.func,ast.Attribute) else None
        if name:calls.append(name)
        if name in ('CountVectorizer','TfidfVectorizer','HashingVectorizer'):
            value=next((k.value for k in node.keywords if k.arg=='analyzer'),None)
            analyzers.append(value.value if isinstance(value,ast.Constant) and isinstance(value.value,str) else 'default-word' if value is None else 'dynamic-unknown')
    keep=('TfidfVectorizer','CountVectorizer','HashingVectorizer','LogisticRegression','MultinomialNB','ComplementNB','SVC','LinearSVC','CalibratedClassifierCV','XGBClassifier','LGBMClassifier','RandomForestClassifier','FeatureUnion','GridSearchCV','RandomizedSearchCV')
    return dict(constructors=sorted(set(calls)&set(keep)),vectorizer_analyzers=sorted(set(analyzers)),
                explicit_character_constructor=any(x in ('char','char_wb') for x in analyzers))

def verify(rows,result):
    assert len(rows)==result['assigned']==12
    assert len({(r['task'],r['seed'],r['arm']) for r in rows})==12
    assert sum(r['complete']=='True' for r in rows)==result['complete']
    for a in result['contrasts']:
        g={r['arm']:r for r in rows if r['task']==a['task'] and int(r['seed'])==a['seed']}
        assert set(g)==set(c.ARMS)
        assert a['complete']==all(r['complete']=='True' for r in g.values())
        if not a['complete']:continue
        sign=1 if a['task']==c.TASKS[0] else -1
        for arm in ('ordinary','open_hpo'):
            expected=sign*(float(g['profile']['dev_metric'])-float(g[arm]['dev_metric']))
            assert abs(a['profile_minus_'+arm]-expected)<1e-14
        assert abs(a['ordinary_minus_open_hpo']-sign*(float(g['ordinary']['dev_metric'])-float(g['open_hpo']['dev_metric'])))<1e-14
    expected=all(x['complete'] and x['profile_minus_ordinary']>0 and x['profile_minus_open_hpo']>0 for x in result['contrasts'])
    assert result['gate']==expected
    for row in result['per_task']:
        vals=[x[row['contrast']] for x in result['contrasts'] if x['task']==row['task'] and x['complete']]
        assert row['n']==len(vals)
        if vals:assert abs(row['median']-statistics.median(vals))<1e-14
        if len(vals)>1:assert abs(row['sample_variance']-statistics.variance(vals))<1e-14
    return dict(status='PASS',rows=12,gate_unchanged=True)

def main():
    plan=check();out=R/'readout-v1';result=read(out/'summary.json')
    # Existing frozen readout is the permission boundary: do not read live trials.
    assert (R/'closed.json').exists() and read(R/'closed.json')['service_closed']
    with (out/'runs.csv').open(newline='') as f:rows=list(csv.DictReader(f))
    validation=verify(rows,result);mechanisms=[];failures=[]
    for row in rows:
        ep=R/f"episode-{row['index']}";selected=ep/'selection.private.json';proposal=ep/'search/code.private.json'
        record=dict(index=int(row['index']),task=row['task'],seed=int(row['seed']),arm=row['arm'],
                    proposal_valid=row['proposal_valid']=='True',selected=row['selected'])
        if selected.exists():record['selected_syntax']=describe(read(selected)['code'])
        if row['arm']!='open_hpo' and proposal.exists():record['proposal_syntax']=describe(read(proposal)['code'])
        mechanisms.append(record)
        for action in ('parent','search','final'):
            path=ep/action/'result.json'
            if not path.exists():continue
            d=read(path)
            if d.get('valid'):continue
            # Only a fixed diagnostic label is exported, never log text.
            terminal=ep/action/'terminal.private.json';text=read(terminal)['terminal'] if terminal.exists() else ''
            readiness=('Kernel readiness timed out before candidate execution began.' in text or 'Kernel did not become ready in time.' in text)
            failures.append(dict(index=int(row['index']),action=action,timed_out=bool(d.get('timed_out')),
                kernel_readiness_marker=readiness,seconds=d.get('seconds')))
    byarm=[]
    for arm in c.ARMS:
        group=[r for r in rows if r['arm']==arm]
        values=[float(r['elapsed_seconds']) for r in group if r['elapsed_seconds']]
        byarm.append(dict(arm=arm,assigned=len(group),complete=sum(r['complete']=='True' for r in group),
            valid_proposals=sum(r['proposal_valid']=='True' for r in group),selected_proposals=sum(r['selected']=='proposal' for r in group),
            elapsed_median=statistics.median(values) if values else None,elapsed_sample_variance=statistics.variance(values) if len(values)>1 else None,
            elapsed_sum=sum(values),generation_seconds_sum=sum(float(r['generation_seconds'] or 0) for r in group)))
    with (PREV/'readout-v1/runs.csv').open(newline='') as f:prior=[r for r in csv.DictReader(f) if r['arm']=='word']
    pairs=[]
    for task in c.TASKS:
        for seed in c.SEEDS:
            g={r['arm']:r for r in rows if r['task']==task and int(r['seed'])==seed}
            for other in ('ordinary','open_hpo'):
                complete=g['profile']['complete']==g[other]['complete']=='True'
                pairs.append(dict(task=task,seed=seed,contrast='profile_minus_'+other,complete=complete,
                    difference=(1 if task==c.TASKS[0] else -1)*(float(g['profile']['dev_metric'])-float(g[other]['dev_metric'])) if complete else None))
    supplemental=dict(summary_sha256=sha(out/'summary.json'),plan_sha256=sha(R/'plan.json'),analysis_sha256=sha(__file__),verification=validation,
        interpretation='Descriptive post-closure checks only. Constructor syntax is not semantic verification. Shared initialization is excluded equally; program seconds are not allocation GPU-hours. Fixed-grid cap differs from agent proposal cap within the same episode budget.',
        shared_initialization=dict(runs=len(prior),grid_fits=sum(int(r['grid_fits']) for r in prior),refits=len(prior),
            summed_program_seconds_with_refits=sum(float(r['seconds']) for r in prior)),
        arms=byarm,mechanisms=mechanisms,failures=failures,pairwise_available_sensitivity=pairs,
        sensitivity_limitation='Added after operational missingness was seen but before any external scores were read. Keeps the frozen complete-triplet primary and gate unchanged. Available pairs do not repair missing endpoints; HPO seed coverage can be incomplete.',
        source_commit=plan['source_commit'])
    write(out/'supplement-v1.json',supplemental)
    write(out/'supplement-export-v1.json',{'supplement-v1.json':sha(out/'supplement-v1.json')})
    print(json.dumps(supplemental))

if __name__=='__main__':main()
