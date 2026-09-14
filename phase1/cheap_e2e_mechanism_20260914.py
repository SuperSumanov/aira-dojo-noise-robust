"""All closed s46/47 pools; descriptive, never a counterfactual search score."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
os.environ['PYTHON_DOTENV_DISABLED']='1'
import io,itertools,json,math,sqlite3,statistics,sys
from contextlib import closing
from pathlib import Path
from analyze_cheap_recent_transfer_20260914 import BASE,read,checked,sha
from analyze_scope_short_control_20260914 import SECRET,label
from verify_task_validity_20260914 import vector
from verify_cheap_selector_20260914 import independent_selection

ROOT=BASE/'forets-wallclock-20260912-km65uuej'
SUMMARY='a2024478c6aa23feb7457d8d45738b51c622725b71eeba928af5e4d0a9dcac82'
MODEL='05379469122879c798f1d2c571eb733956a067dac314050feeb06d3e09c641d1'
ARMS=('uniform','short_code','learned_validity','class_gate')

def binary_bounds(choices,labels,left,right):
    if any(v is not None and (type(v) is not int or v not in (0,1)) for v in labels):raise ValueError('binary labels')
    completions=itertools.product(*[(0,1) if y is None else (y,) for y in labels])
    effects=[ys[choices[left]]-ys[choices[right]] for ys in completions]
    return [min(effects),max(effects)]

def aggregate(rows):
    out=[]
    for task in ('leaf-classification','spaceship-titanic'):
        for arm in ARMS[:3]:
            rr=[r for r in rows if (r['task'],r['arm'])==(task,arm)]
            out.append(dict(task=task,arm=arm,runs=len(rr),two_code_pools=sum(r['two_code_pools'] for r in rr),
                initial_valid=sum(r['initial_valid'] for r in rr),initial_invalid=sum(r['initial_invalid'] for r in rr),initial_unknown=sum(r['initial_unknown'] for r in rr),
                median_run_prefix_chars=statistics.median([r['median_selected_prefix_chars'] for r in rr if r['median_selected_prefix_chars'] is not None]) if any(r['median_selected_prefix_chars'] is not None for r in rr) else None,
                summed_returned_original_task_seconds=sum(r['returned_original_task_seconds'] for r in rr),summed_returned_debug_task_seconds=sum(r['returned_debug_task_seconds'] for r in rr),
                short_full_choice_disagreements=sum(r['short_full_choice_disagreements'] for r in rr),category_full_choice_disagreements=sum(r['category_full_choice_disagreements'] for r in rr)))
    return out

def main():
    import joblib,numpy as np
    os.umask(0o077)
    finish=read(ROOT/'readout-finished.json');s=read(ROOT/'cheap-selector-summary.json',SUMMARY)
    if finish['status']!='verified' or finish['summary_sha256']!=SUMMARY or len(s['rows'])!=12:raise ValueError('full closed matrix first')
    expected={(r['run_id'],r['pool']):r['sha256'] for r in s['selection_replays']}
    model=joblib.load(io.BytesIO(checked(BASE/'forets-task-validity-20260914-n8q3h72y/code_only.private.joblib',MODEL,False)))['model']
    sys.path.insert(0,str(ROOT/'source/src'))
    from dojo.core.solvers.utils.response import extract_code
    pools=[];runs=[];proofs=[]
    for r in s['rows']:
        cp=Path(read(ROOT/'configs'/(r['run_id']+'.json'))['solver']['checkpoint_path'])
        if not cp.resolve().is_relative_to(ROOT/'runs'):raise ValueError('scope')
        raw=checked(cp/'journal.jsonl');ns=[json.loads(x) for x in raw.splitlines()];nodes={n['id']:n for n in ns}
        if len(nodes)!=len(ns):raise ValueError('duplicate node')
        proofs.append(dict(run_id=r['run_id'],journal_sha256=sha(raw)))
        local=[];bootstrap=0
        for p in sorted((cp/'forets-candidates-private').glob('batch-*.sqlite')):
            digest=sha(p.read_bytes())
            if expected.get((r['run_id'],p.name))!=digest:raise ValueError('frozen pool')
            with closing(sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)) as db:raw,h=db.execute('select payload,sha256 from snapshot').fetchone()
            if sha(raw.encode())!=h or SECRET.search(raw.encode()) or sha(p.read_bytes())!=digest:raise ValueError('hash/security')
            v=json.loads(raw);b=v['binding'];cs=v['candidates']
            if b.get('common_start'):bootstrap+=1;continue
            if len(cs)!=2 or len(v['selected'] or [])!=1:raise ValueError('actual opportunity')
            codes=[c['node']['code'] for c in cs];pred=[float(p) for p in model.predict_proba(np.asarray([vector(c) for c in codes]))[:,1]]
            score_sets=dict(uniform=None,short_code=[-len(c[:30000]) for c in codes],learned_validity=pred,class_gate=[int(p>.5) for p in pred])
            choices={a:independent_selection(2,scores,r['seed'],r['task'],b['step'])[0] for a,scores in score_sets.items()}
            slot=v['selected'][0]
            if choices[r['arm']]!=slot:raise ValueError('actual choice')
            candidates=[c for c in v['task_calls'] if c['intent']['role']=='candidate']
            if len(candidates)>1:raise ValueError('extra original call')
            call=candidates[0] if candidates else None;ys=[None,None];reason='not_started';duration=None
            if call:
                if call['slot']!=slot or call['intent']['code_sha256']!=sha(extract_code(codes[slot]).encode()):raise ValueError('native identity')
                reason=call['state']
                if call['state']=='returned':
                    meta=call['execution_metadata'];ec=meta['exit_code_reported'];duration=call['task_wall_ns']/1e9
                    if duration<0:raise ValueError('negative wall time')
                    node=nodes.get(cs[slot]['node']['id'])
                    if node is not None:
                        if node['code']!=codes[slot] or node.get('exit_code')!=ec:raise ValueError('journal identity/exit')
                        ys[slot]=label(node);reason='observed_journal' if ys[slot] is not None else 'journal_label_unknown'
                    elif ec is not None and ec!=0:ys[slot]=0;reason='returned_nonzero_no_journal'
                    else:reason='returned_success_without_initial_journal_label'
            debug=[c for c in v['task_calls'] if c['intent']['role']=='debug']
            rec=dict(run_id=r['run_id'],task=r['task'],seed=r['seed'],arm=r['arm'],pool=p.name,pool_sha256=digest,phase=v['phase'],selected=slot,
                prefix_chars=[len(c[:30000]) for c in codes],model_scores=pred,choices=choices,observed_initial_labels=ys,initial_label_reason=reason,
                returned_original_task_seconds=duration,debug_calls=len(debug),debug_returned=sum(c['state']=='returned' for c in debug),
                returned_debug_task_seconds=sum(c['task_wall_ns']/1e9 for c in debug if c['state']=='returned'),
                short_minus_full_validity_bounds=binary_bounds(choices,ys,'short_code','learned_validity'),category_minus_full_validity_bounds=binary_bounds(choices,ys,'class_gate','learned_validity'))
            pools.append(rec);local.append(rec)
        if bootstrap!=1:raise ValueError('common start denominator')
        values=[x['observed_initial_labels'][x['selected']] for x in local];lengths=[x['prefix_chars'][x['selected']] for x in local]
        runs.append(dict(run_id=r['run_id'],task=r['task'],seed=r['seed'],arm=r['arm'],bootstrap_pools=bootstrap,two_code_pools=len(local),
            initial_valid=sum(y==1 for y in values),initial_invalid=sum(y==0 for y in values),initial_unknown=sum(y is None for y in values),
            median_selected_prefix_chars=statistics.median(lengths) if lengths else None,
            returned_original_task_seconds=sum(x['returned_original_task_seconds'] or 0 for x in local),returned_debug_task_seconds=sum(x['returned_debug_task_seconds'] for x in local),
            short_full_choice_disagreements=sum(x['choices']['short_code']!=x['choices']['learned_validity'] for x in local),
            category_full_choice_disagreements=sum(x['choices']['class_gate']!=x['choices']['learned_validity'] for x in local)))
    out=dict(role='posthoc_selected_pool_mechanism_not_causal_search',source_summary_sha256=SUMMARY,model_sha256=MODEL,rows=pools,runs=runs,groups=aggregate(runs),source_proofs=proofs,
        script_sha256=sha(Path(__file__).read_bytes()),plan_sha256=sha(Path(__file__).with_name('CHEAP_E2E_MECHANISM_PLAN_20260914.md').read_bytes()),api_calls=0,gpu_jobs=0,models_fit=0,
        limitations='Unexecuted outcomes unknown. Policy-induced pools are not common samples across arms; returned duration excludes interrupted work and is not total resource use. Bounds are per-pool binary possibilities, not confidence intervals or full-search effects. No s48 outcomes read.')
    raw=(json.dumps(out,sort_keys=True,allow_nan=False)+'\n').encode()
    with (ROOT/'cheap-e2e-mechanism.json').open('xb') as f:f.write(raw)
    print(json.dumps(dict(sha256=sha(raw),groups=out['groups'],runs=runs)))
if __name__=='__main__':main()
