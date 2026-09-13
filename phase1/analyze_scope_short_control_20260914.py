"""Post-closure short-code control on fully observed two-candidate pools."""
from collections import Counter,defaultdict
from contextlib import closing
import hashlib,json,math,os
from pathlib import Path
import re,sqlite3,statistics

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-88v5m9dr')
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(p):
    raw=p.read_bytes()
    if SECRET.search(raw):raise ValueError('credential shape; no raw output')
    return json.loads(raw)
def label(node):
    ec=node.get('exit_code')
    if ec is None:return None
    if ec!=0:return 0
    values=[]
    if 'valid_submission' in (node.get('metric_info') or {}):values.append(node['metric_info']['valid_submission'])
    if 'metric_info/valid_submission' in node:values.append(node['metric_info/valid_submission'])
    if any(v not in (None,0,1,False,True) for v in values) or (values and any(v!=values[0] for v in values)):raise ValueError('validity schema')
    return int(values[0]==1) if values and values[0] is not None else None
def choice(lengths,labels):
    if len(lengths)!=2 or len(labels)!=2 or any(x not in (0,1) for x in labels):raise ValueError('observed pair required')
    uniform=sum(labels)/2
    selected=uniform if lengths[0]==lengths[1] else labels[0 if lengths[0]<lengths[1] else 1]
    return dict(short_validity=selected,uniform_validity=uniform,oracle_validity=max(labels),gain=selected-uniform,
        discordant=labels[0]!=labels[1],equal_length=lengths[0]==lengths[1])
def evaluate_pool(value,nodes):
    candidates=value['candidates']
    if len(candidates)!=2:return None,'not_two_candidates'
    if value['phase']!='complete':return None,'incomplete_pool'
    if set(value['selected'] or [])!={0,1}:return None,'not_both_selected'
    original=[c for c in value['task_calls'] if c['intent']['role']=='candidate']
    if len(original)!=2 or {c['slot'] for c in original}!={0,1}:return None,'not_both_initial_calls'
    labels=[];lengths=[];rejects=[]
    for slot in (0,1):
        call=next(c for c in original if c['slot']==slot);generated=candidates[slot]['node']
        if call['state']!='returned':return None,'initial_call_unknown'
        if not isinstance(generated,dict) or generated['id'] not in nodes:return None,'initial_journal_missing'
        node=nodes[generated['id']];code=generated['code'];digest=sha(code.encode())
        if digest!=call['intent']['code_sha256'] or digest!=sha(node['code'].encode()):raise ValueError('code binding')
        meta=call['execution_metadata']
        if meta['exit_code_reported']!=node.get('exit_code'):raise ValueError('exit/journal disagreement')
        observed=label(node)
        if observed is None:return None,'initial_validity_unknown'
        labels.append(observed);lengths.append(len(code))
        scopes=[m['edit_scope'] for m in generated.get('operators_metrics',[]) if isinstance(m,dict) and 'edit_scope' in m]
        rejects.append(any(m.get('interface_accepted') is False for m in scopes))
    return dict(**choice(lengths,labels),lengths=lengths,labels=labels,interface_rejected=rejects),'eligible'
def main():
    import numpy as np
    os.umask(0o077);finish=read(ROOT/'readout-finished.json')
    if finish['status']!='verified':raise ValueError('full frozen readout required')
    path=ROOT/'edit-scope-summary.json'
    if sha(path.read_bytes())!=finish['files']['edit-scope-summary.json']:raise ValueError('summary drift')
    summary=read(path)
    if len(summary['rows'])!=16:raise ValueError('full matrix required')
    expected={(r['run_id'],r['pool']):r['sha256'] for r in summary['selection_replays']}
    rows=[];runs=[]
    for row in summary['rows']:
        cfg=read(ROOT/'configs'/(row['run_id']+'.json'));cp=Path(cfg['solver']['checkpoint_path'])
        if not cp.resolve().is_relative_to(ROOT/'runs'):raise ValueError('checkpoint path')
        jp=cp/'journal.jsonl';nodes={}
        if jp.exists():
            raw=jp.read_bytes()
            if SECRET.search(raw):raise ValueError('credential shape in journal')
            for line in raw.splitlines():
                node=json.loads(line)
                if node['id'] in nodes:raise ValueError('duplicate journal id')
                nodes[node['id']]=node
        reasons=Counter();local=[]
        for pool in sorted((cp/'forets-candidates-private').glob('batch-*.sqlite')):
            digest=sha(pool.read_bytes())
            if digest!=expected[(row['run_id'],pool.name)]:raise ValueError('pool drift from frozen readout')
            with closing(sqlite3.connect(pool.as_uri()+'?mode=ro',uri=True)) as db:
                payload,h=db.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchone()
            if sha(payload.encode())!=h or sha(pool.read_bytes())!=digest or SECRET.search(payload.encode()):raise ValueError('pool content/hash/security')
            value,reason=evaluate_pool(json.loads(payload),nodes);reasons[reason]+=1
            if value is not None:
                result=dict(run_id=row['run_id'],task=row['task'],arm=row['arm'],seed=row['seed'],pool=pool.name,
                    technical_eligible=row['technical_eligible'],pool_sha256=digest,**value)
                rows.append(result);local.append(result)
        runs.append(dict(run_id=row['run_id'],task=row['task'],arm=row['arm'],seed=row['seed'],technical_eligible=row['technical_eligible'],
            reasons=dict(reasons),observed_pairs=len(local),discordant=sum(r['discordant'] for r in local),
            mean_gain=statistics.mean(r['gain'] for r in local) if local else None,
            mean_short_validity=statistics.mean(r['short_validity'] for r in local) if local else None,
            mean_uniform_validity=statistics.mean(r['uniform_validity'] for r in local) if local else None))
    groups=[];rng=np.random.default_rng(20260914)
    for task in ('leaf-classification','spaceship-titanic'):
        for arm in ('whole_program','model_module'):
            selected=[r for r in runs if r['task']==task and r['arm']==arm and r['technical_eligible'] and r['observed_pairs']]
            gains=np.array([r['mean_gain'] for r in selected]);boots=gains[rng.integers(len(gains),size=(2000,len(gains)))].mean(axis=1) if len(gains) else None
            groups.append(dict(task=task,arm=arm,runs=len(selected),pairs=sum(r['observed_pairs'] for r in selected),discordant=sum(r['discordant'] for r in selected),
                run_equal_mean_gain=float(gains.mean()) if len(gains) else None,
                run_bootstrap_interval=[float(np.quantile(boots,.025)),float(np.quantile(boots,.975))] if boots is not None else None))
    result=dict(role='postclosure_observed_pool_short_code_control_not_counterfactual_search',source_summary_sha256=finish['files']['edit-scope-summary.json'],
        script_sha256=sha(Path(__file__).read_bytes()),rows=rows,runs=runs,groups=groups,api_calls=0,gpu_jobs=0,external_regrading=False,
        caveats=['All observed pools reported; primary descriptive groups retain frozen whole-run technical eligibility.',
            'Two real sequential executions may interfere via workspace; not a solo-execution or later-search counterfactual.',
            'Initial candidate validity only, not repair-success, final quality, savings or novel algorithm.',
            'Module rejection programs retain their actual lengths; not raw generator response length.',
            'Intervals with very few runs can be degenerate and are not evidence of precise effects.'])
    raw=(json.dumps(result,sort_keys=True,allow_nan=False)+'\n').encode()
    with (ROOT/'short-code-pool-control.json').open('xb') as f:f.write(raw)
    print(json.dumps(dict(sha256=sha(raw),groups=groups,total_observed_pairs=len(rows))))
if __name__=='__main__':main()
