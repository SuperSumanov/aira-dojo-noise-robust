"""Post-closure mechanism trace for all eight runs; never outcome re-selection."""
from contextlib import closing
from pathlib import Path
import json
import sqlite3
from forets_environment_build_20260912 import read,write,encode,sha
from read_forets_action_delivery_20260913 import replay

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-7wzrny21')
FINISH='34eafb5d6a6e2b347f86b380697f0d4eb5ff52fc45ce441cd5361e4e60c33011'

def run():
    done=read(ROOT/'readout-finished.json',FINISH)
    for name,digest in done['files'].items():
        if sha((ROOT/name).read_bytes())!=digest:raise ValueError('closed byte drift')
    summary=read(ROOT/'action-delivery-summary.json');prepared=read(ROOT/'prepared.json');rows=[]
    for result in summary['rows']:
        rid=result['run_id'];planned=next(p for p in prepared['run_configs'] if p['run_id']==rid)
        cfg=read(ROOT/'configs'/(rid+'.json'),planned['config_sha256']);base=ROOT/'incumbents'/rid
        roles={};pools=[]
        for path in sorted((Path(cfg['solver']['checkpoint_path'])/'forets-candidates-private').glob('batch-*.sqlite')):
            before=sha(path.read_bytes())
            with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
                payload,digest=db.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchone()
            if sha(payload.encode())!=digest or sha(path.read_bytes())!=before:raise ValueError('closed pool drift')
            value=json.loads(payload)
            for call in value['task_calls']:
                intent=call['intent'];roles.setdefault(intent['code_sha256'],set()).add(intent['role'])
            pools.append(dict(pool=path.name,phase=value.get('phase'),roles=[c['intent']['role'] for c in value['task_calls']],
                states=[c['state'] for c in value['task_calls']],sha256=before))
        actions=[];iterations=[]
        for pattern,directory,kind in [('action-*.commit.json',base/'action-incumbents','action'),('step-*.commit.json',base,'iteration')]:
            for path in sorted(directory.glob(pattern)):
                c=read(path);data=directory/c['data_file'];d=read(data,c['data_sha256'])
                if not c['eligible']:continue
                h=None if d['submission'] is None else d['submission']['code_sha256']
                entry=dict(step=d['current_step'],seconds=(c['durable_ns']-d['start_ns'])/1e9,code_sha256=h)
                if kind=='action':
                    chosen=replay(d['observed_nodes'])
                    if (None if chosen is None else chosen['node_id'])!=d['node_id']:raise ValueError('original selection differs')
                    latest=d['observed_nodes'][-1]
                    entry.update(action=d['action'],latest_exit_code=latest['exit_code'],latest_buggy=latest['is_buggy'],
                        latest_execution_roles=sorted(roles.get(latest['code_sha256'],set())),
                        selected_roles=sorted(roles.get(h,set())),selected_search_value=None if chosen is None else chosen['search_value'])
                    actions.append(entry)
                else:iterations.append(entry)
        chosen_hash=result['action_code_sha256']
        first=next((a['seconds'] for a in actions if a['code_sha256']==chosen_hash),None)
        rows.append(dict(run_id=rid,task=result['task'],seed=result['seed'],action_gain=result['action_oriented_gain'],
            first_action_selection_of_final_submission_seconds=first,selected_roles=sorted(roles.get(chosen_hash,set())),
            final_submission_ever_in_iteration_receipt=any(i['code_sha256']==chosen_hash for i in iterations),
            actions=actions,iterations=iterations,pools=pools))
    value=dict(role='all_closed_action_delivery_mechanisms_not_new_effects',source_finish_sha256=FINISH,rows=rows,
        api_calls=0,gpu_jobs=0,protected_cohort_read=False)
    digest=write(ROOT/'action-timeline.json',encode(value))
    print(json.dumps(dict(sha256=digest,rows=[{k:v for k,v in r.items() if k not in ('actions','iterations','pools')} for r in rows])))

if __name__=='__main__':run()
