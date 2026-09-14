"""Independent original-call labels and arithmetic, plus final-delivery lineage."""
import itertools,json,sqlite3,statistics
from contextlib import closing
from pathlib import Path
from analyze_cheap_recent_transfer_20260914 import BASE,read,checked,sha
ROOT=BASE/'forets-wallclock-20260912-km65uuej'
MECH='6233085f98cbd9cec440245aee25417ae2e6eb35219ee41b69e233042fcc4185'
def main():
    mech=read(ROOT/'cheap-e2e-mechanism.json',MECH)
    summary=read(ROOT/'cheap-selector-summary.json',mech['source_summary_sha256'])
    checked_nodes={};pools={};lineage=[]
    for r in summary['rows']:
        cp=Path(read(ROOT/'configs'/(r['run_id']+'.json'))['solver']['checkpoint_path'])
        proof=next(x for x in mech['source_proofs'] if x['run_id']==r['run_id'])
        nodes={n['id']:n for n in map(json.loads,checked(cp/'journal.jsonl',proof['journal_sha256']).splitlines())}
        checked_nodes[r['run_id']]=nodes;hits=[]
        for p in sorted((cp/'forets-candidates-private').glob('*.sqlite')):
            expected=next(x['sha256'] for x in summary['selection_replays'] if (x['run_id'],x['pool'])==(r['run_id'],p.name))
            if sha(p.read_bytes())!=expected:raise ValueError('pool changed')
            with closing(sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)) as db:raw,h=db.execute('select payload,sha256 from snapshot').fetchone()
            if sha(raw.encode())!=h:raise ValueError('payload changed')
            from analyze_scope_short_control_20260914 import SECRET
            if SECRET.search(raw.encode()):raise ValueError('credential shape')
            value=json.loads(raw);pools[(r['run_id'],p.name)]=value
            for call in value['task_calls']:
                if call['intent']['code_sha256']==r['action_code_sha256']:
                    hits.append(dict(pool=p.name,role='bootstrap' if value['binding'].get('common_start') else call['intent']['role'],state=call['state']))
        roles=sorted({x['role'] for x in hits})
        lineage.append(dict(run_id=r['run_id'],task=r['task'],arm=r['arm'],seed=r['seed'],final_action_origin_roles=roles,matching_calls=hits,
            final_action_origin=roles[0] if len(roles)==1 else 'ambiguous' if roles else 'unresolved'))
    for r in mech['rows']:
        v=pools[(r['run_id'],r['pool'])];chosen=r['selected'];ys=[None,None]
        cs=[c for c in v['task_calls'] if c['intent']['role']=='candidate']
        if cs and cs[0]['state']=='returned':
            ec=cs[0]['execution_metadata']['exit_code_reported'];n=checked_nodes[r['run_id']].get(v['candidates'][chosen]['node']['id'])
            if n:
                if n['exit_code']!=ec:raise ValueError('exit mismatch')
                valid=n.get('metric_info',{}).get('valid_submission')
                if ec is not None and ec!=0:ys[chosen]=0
                elif ec==0 and valid is not None:ys[chosen]=int(valid==1)
            elif ec is not None and ec!=0:ys[chosen]=0
        if ys!=r['observed_initial_labels']:raise ValueError('initial labels')
        for left,name in [('short_code','short_minus_full_validity_bounds'),('class_gate','category_minus_full_validity_bounds')]:
            vals=[]
            for a,b in itertools.product((0,1),repeat=2):
                complete=[a,b]
                if all(y is None or y==z for y,z in zip(ys,complete)):vals.append(complete[r['choices'][left]]-complete[r['choices']['learned_validity']])
            if [min(vals),max(vals)]!=r[name]:raise ValueError('sharp binary bounds')
        durations=[c['task_wall_ns']/1e9 for c in v['task_calls'] if c['intent']['role']=='candidate' and c['state']=='returned']
        if (durations[0] if durations else None)!=r['returned_original_task_seconds']:raise ValueError('call duration')
    for r in mech['runs']:
        rr=[x for x in mech['rows'] if x['run_id']==r['run_id']];ys=[x['observed_initial_labels'][x['selected']] for x in rr]
        if (len(rr),ys.count(1),ys.count(0),ys.count(None))!=(r['two_code_pools'],r['initial_valid'],r['initial_invalid'],r['initial_unknown']):raise ValueError('run counts')
        chars=[x['prefix_chars'][x['selected']] for x in rr]
        if (statistics.median(chars) if chars else None)!=r['median_selected_prefix_chars']:raise ValueError('length median')
    result=dict(status='original_call_labels_bounds_run_counts_and_selected_action_lineage_verified',summary_sha256=MECH,pools=len(mech['rows']),runs=len(mech['runs']),lineage=lineage,
        api_calls=0,gpu_jobs=0,models_fit=0,script_sha256=sha(Path(__file__).read_bytes()),
        limitation='Final code lineage is a post-hoc descriptive extension; matching code hash identifies call roles, not the causal value of a repair or the quality of an unexecuted alternative.')
    raw=(json.dumps(result,sort_keys=True)+'\n').encode()
    with (ROOT/'cheap-e2e-mechanism-independent.json').open('xb') as f:f.write(raw)
    print(json.dumps(dict(sha256=sha(raw),**result)))
if __name__=='__main__':main()
