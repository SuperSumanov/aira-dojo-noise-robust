"""Post-hoc same-pool diagnostic using already predicted old development nodes.

Never scores new EScope programs or reads a trained model. No deployment gate.
"""
from collections import Counter,defaultdict
from contextlib import closing
import csv
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import statistics

ROOT=Path('/research/d7/spc/yzyang4/forets-legacy-transfer-20260914-0ukne5fq')
SUMMARY_SHA='7a15c9abef48c5e8da4729decb5b42908112476143ac405c6b3680d30ea6bfb3'
BASE=ROOT.parent
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
def sha(b):return hashlib.sha256(b).hexdigest()
def checked(path,h):
    raw=path.read_bytes()
    if sha(raw)!=h or SECRET.search(raw):raise ValueError('identity/security')
    return raw
def pick(scores,labels):
    base=sum(labels)/2
    selected=base if scores[0]==scores[1] else labels[int(scores[1]>scores[0])]
    return dict(selected_validity=selected,uniform_validity=base,oracle_validity=max(labels),gain=selected-base)
def main():
    s=json.loads(checked(ROOT/'summary.json',SUMMARY_SHA))
    predictions=list(csv.DictReader(checked(ROOT/'predictions.csv',s['predictions_sha256']).decode().splitlines()))
    lookup={(r['scope'],r['model'],r['run'],int(r['step'])):r for r in predictions}
    models=sorted({(r['scope'],r['model']) for r in predictions});rows=[];reasons=Counter();proof=[];run_counts=Counter()
    for source in s['target_source_proofs']:
        run=source['root']+'/'+source['run_id'];cp=BASE/source['root']/'runs'/source['run_id']/'checkpoint'
        nodes={n['id']:n for n in (json.loads(line) for line in checked(cp/'journal.jsonl',source['journal_sha256']).splitlines())}
        for path in sorted((cp/'forets-candidates-private').glob('batch-*.sqlite')):
            before=sha(path.read_bytes())
            with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
                payload,digest=db.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchone()
            if sha(payload.encode())!=digest or SECRET.search(payload.encode()) or sha(path.read_bytes())!=before:raise ValueError('pool drift/security')
            value=json.loads(payload);calls=[c for c in value['task_calls'] if c['intent']['role']=='candidate']
            if len(calls)!=2:reasons['not_two_initial_attempts']+=1;continue
            if any(c['state']!='returned' for c in calls):reasons['incomplete_initial_return']+=1;continue
            pair=[];reason=None
            for c in sorted(calls,key=lambda c:c['slot']):
                generated=value['candidates'][c['slot']]['node'];node=nodes.get(generated['id'])
                if node is None or (models[0][0],models[0][1],run,node['step']) not in lookup:
                    reason='original_node_not_in_fixed_predicted_targets';break
                p=lookup[models[0][0],models[0][1],run,node['step']]
                if not (p['code_sha256']==c['intent']['code_sha256']==sha(generated['code'].encode())==sha(node['code'].encode())):raise ValueError('initial code mismatch')
                pair.append(p)
            if reason:reasons[reason]+=1;continue
            if len({r['task'] for r in pair})!=1:raise ValueError('mixed task')
            labels=[int(r['label']) for r in pair];reasons['eligible_observed_pair']+=1;run_counts[run]+=1
            methods=[]
            for scope,model in models:
                scores=[float(lookup[scope,model,run,int(r['step'])]['predicted_validity']) for r in pair]
                methods.append(dict(scope=scope,model=model,**pick(scores,labels)))
            methods.append(dict(scope='no_fit',model='short_code',**pick([float(r['short_code_score']) for r in pair],labels)))
            rows.append(dict(run=run,task=pair[0]['task'],pool=path.name,pool_width=len(value['candidates']),
                observed_slots=[c['slot'] for c in sorted(calls,key=lambda c:c['slot'])],labels=labels,discordant=labels[0]!=labels[1],methods=methods))
            proof.append(dict(run=run,pool=path.name,sha256=before))
    groups=[]
    for task in ('leaf-classification','spaceship-titanic'):
        subset=[r for r in rows if r['task']==task]
        for scope,model in models+[('no_fit','short_code')]:
            per_run=defaultdict(list);gains=[]
            for r in subset:
                d=next(m['gain'] for m in r['methods'] if (m['scope'],m['model'])==(scope,model));per_run[r['run']].append(d);gains.append(d)
            groups.append(dict(task=task,scope=scope,model=model,pairs=len(subset),runs=len(per_run),
                discordant=sum(r['discordant'] for r in subset),pair_mean_validity_gain=statistics.mean(gains) if gains else None,
                run_equal_validity_gain=statistics.mean(statistics.mean(v) for v in per_run.values()) if per_run else None,
                strict_better_pairs=sum(d>0 for d in gains),strict_worse_pairs=sum(d<0 for d in gains)))
    result=dict(role='posthoc_already_predicted_old_observed_pair_diagnostic',source_summary_sha256=SUMMARY_SHA,rows=rows,groups=groups,
        reasons=dict(reasons),proofs=proof,script_sha256=sha(Path(__file__).read_bytes()),api_calls=0,gpu_jobs=0,models_refit_or_loaded=False,
        limits='Only two original candidates actually executed and present in fixed prediction targets. Incomplete, unexecuted and repair nodes excluded explicitly. Pair may be a selected subset of a wider pool, with sequential workspace interference. No EScope access, policy counterfactual, cost saving, final quality, deployment or changed gate.')
    raw=(json.dumps(result,sort_keys=True)+'\n').encode()
    with (ROOT/'same-pool-diagnostic.json').open('xb') as f:f.write(raw)
    print(json.dumps(dict(sha256=sha(raw),groups=groups,reasons=dict(reasons))))
if __name__=='__main__':main()
