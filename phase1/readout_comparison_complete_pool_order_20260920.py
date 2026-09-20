"""Frozen final-incumbent-only readout for complete-pool schedule order."""
import argparse,hashlib,math,re
from pathlib import Path
import readout_comparison_online_continuation_20260919 as reader
from comparison_auc_20260920 import numerical


def audit_actions(actions,selection,programs,ready_first,incumbent):
    # Independent schedule construction; no imported scheduler or selection code.
    chosen=selection['chosen'];tail=selection['remaining']
    if sorted(chosen+tail)!=list(range(6)) or len(chosen)!=2 or len(tail)!=4:raise ValueError('action set')
    stages=([('execute',s) for s in chosen+tail]+[('repair',s) for s in chosen]) if ready_first else [
        ('execute',chosen[0]),('repair',chosen[0]),('execute',chosen[1]),('repair',chosen[1])]+[('execute',s) for s in tail]
    positions={stage:i for i,stage in enumerate(stages)};prior=-1;depths={};seen=set();accepted_by_slot={};eligible=[]
    for i,a in enumerate(actions):
        stage=(a['kind'],a['slot'])
        if stage not in positions or positions[stage]<prior:raise ValueError('schedule order')
        prior=positions[stage]
        if a['kind']=='execute':
            if a['slot'] in seen or a['depth']!=0:raise ValueError('repeated initial candidate')
            seen.add(a['slot'])
            if a.get('code_sha256') and a['code_sha256']!=programs[a['slot']]['code_sha256']:raise ValueError('initial code changed')
        else:
            if a['slot'] not in seen or accepted_by_slot.get(a['slot']):raise ValueError('ineligible repair')
            expected=depths.get(a['slot'],0)+1
            if a['depth']!=expected or not 1<=expected<=20:raise ValueError('repair depth')
            depths[a['slot']]=expected
        if a.get('native_accepted'):
            metric=a.get('internal_metric')
            if type(metric) not in (int,float) or not math.isfinite(metric) or a.get('exit_code')!=0 or a.get('timed_out') or not a.get('submission_sha256') or not 0<=a['completed_seconds']<=2100:raise ValueError('native acceptance')
            eligible.append((i,metric));accepted_by_slot[a['slot']]=True
    expected=max(eligible,key=lambda item:item[1])[0] if eligible else None
    if (incumbent or {}).get('action_index')!=expected:raise ValueError('not actual best native incumbent')
    if incumbent is not None:
        a=actions[expected]
        if any(incumbent[k]!=a[k] for k in ('code_sha256','submission_sha256','internal_metric')) or incumbent['accepted_seconds']!=a['completed_seconds']:raise ValueError('incumbent fields')
    return dict(initial_programs_executed=len(seen),repairs_executed=sum(depths.values()),native_accepted_actions=len(eligible),
        truncated_generations=sum(a.get('status')=='truncated' for a in actions),analysis_failures=sum(a.get('analysis_status')=='failed_native_empty_response' for a in actions))


def main(root,prepared,commit):
    if root.parent!=reader.rt.BASE or not re.fullmatch(r'comparison-complete-pool-order-20260920-[a-z0-9_]+',root.name):raise ValueError('scope')
    p=reader.safe(root/'prepared.json',prepared)
    if reader.rt.sha(root/Path(__file__).name)!=p['files'][Path(__file__).name] or reader.rt.sha(Path(__file__))!=p['files'][Path(__file__).name]:raise ValueError('frozen reader')
    cases=reader.safe(root/'inputs.private.json')['cases'];selections=reader.safe(root/'policy-selections.json')
    if [c['seed'] for c in cases]!=[5,6] or [s['seed'] for s in selections['selections']]!=[5,6]:raise ValueError('source seeds')
    # Recompute deterministic treatment assignment before inspecting actions.
    import random
    for case,s in zip(cases,selections['selections']):
        scores={int(k):v for k,v in s['scores'].items()}
        if sorted(scores)!=list(range(6)) or not all(math.isfinite(v) for v in scores.values()):raise ValueError('all scores')
        order=sorted(scores,key=lambda slot:(-scores[slot],slot));chosen=sorted(random.Random(f'complete-pool-order:20260920:{case["seed"]}').sample(order[:3],2),key=order.index)
        if s['critic_order']!=order or s['chosen']!=chosen or s['remaining']!=[i for i in range(6) if i not in chosen]:raise ValueError('selection changed')
    def audit(ep,actions,start,finished):
        case=cases[start['seed']-1];selection=selections['selections'][start['seed']-1]
        if selections['utc']>start['utc']:raise ValueError('scoring was not before execution')
        incumbent=reader.safe(ep/'incumbent.json') if (ep/'incumbent.json').exists() else None
        out=audit_actions(actions,selection,{p['slot']:p for p in case['programs']},start['cache'],incumbent)
        if finished and finished['source_seed']!=case['seed']:raise ValueError('source identity')
        for i,a in enumerate(actions):
            if a.get('code_sha256') and reader.rt.sha(ep/f'code-{i}.private.py')!=a['code_sha256']:raise ValueError('code drift')
        first=reader.safe(ep/'first-accepted.json') if (ep/'first-accepted.json').exists() else None
        eligible=[(i,a) for i,a in enumerate(actions) if a.get('native_accepted')]
        if first is not None and (not eligible or first['action_index']!=eligible[0][0] or first['accepted_seconds']!=eligible[0][1]['completed_seconds']):raise ValueError('first acceptance')
        return out|dict(source_seed=case['seed'],first_valid_seconds=first['accepted_seconds'] if first else None,arm='ready_first' if start['cache'] else 'repair_interleaved_with_cache_tail')
    reader.ROOT=root;reader.PREPARED=prepared;reader.TASK='random-acts-of-pizza';reader.NUMERICAL=lambda task,pred,truth:numerical(pred,truth)
    reader.METRIC_DELTA='auc_delta_ready_minus_interleaved';reader.LATENCY_FIELD='first_valid_seconds';reader.EPISODE_AUDIT=audit
    reader.ROLE='same_complete_pool_and_repair_set_order_only_conditional_final_submission'
    reader.READOUT_CONTEXT=dict(wrapper_commit=commit,wrapper_sha256=reader.rt.sha(Path(__file__)),source_seeds=[5,6],pair_ids=[1,2],
        primary='actual final native-selected submission',cold_critic_seconds=selections['load_seconds'],query_seconds=sum(s['query_seconds'] for s in selections['selections']),
        boundary='Historical draft-generation sunk prefix, exploratory new seeds, not full E2E or population confirmation; baseline also receives all six candidates.')
    reader.main(commit)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--prepared',required=True);p.add_argument('--reader-commit',required=True);a=p.parse_args();main(a.root,a.prepared,a.reader_commit)
