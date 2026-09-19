"""Grade only the actual internal-metric incumbent, after the whole job closes."""
import argparse,math
from pathlib import Path
import readout_comparison_online_continuation_20260919 as shared
from readout_comparison_pizza_online_20260919 import numerical

ROOT=shared.rt.BASE/'comparison-native-batch-order-20260919-hz3c589n'
PREPARED='25d55a42517e586b677dd72a7296a4453c0c68bfda03c551eeb30570e8274428'

def completed_request_time(records):
    seconds={'generation':0.,'analysis':0.};counts={'generation':0,'analysis':0}
    for kind,record in records:
        if kind not in seconds:raise ValueError('model request kind')
        value=(record.get('info',{}).get('usage') or {}).get('latency')
        if type(value) not in (float,int) or not math.isfinite(value) or value<0:raise ValueError('missing/nonfinite measured request time')
        seconds[kind]+=value;counts[kind]+=1
    return dict(completed_generation_request_seconds=seconds['generation'],completed_analysis_request_seconds=seconds['analysis'],
                completed_generation_requests=counts['generation'],completed_analysis_requests=counts['analysis'],
                observed_model_request_seconds=sum(seconds.values()),request_time_is_lower_bound=True,
                unrecorded_time_not_assigned_to_model=True)

def selection_history(actions):
    """Independent plain scan; does not import the execution selector."""
    best=None;decisions=[];first=None
    for i,a in enumerate(actions):
        if a.get('native_accepted') is not True:continue
        metric=a.get('internal_metric');elapsed=a.get('completed_seconds')
        if type(metric) not in (float,int) or not math.isfinite(metric):raise ValueError('nonfinite native metric')
        if type(elapsed) not in (float,int) or not 0<=elapsed<=2100:raise ValueError('late accepted action')
        if a.get('status')!='returned' or not a.get('submission_sha256') or a.get('timed_out') or a.get('exit_code')!=0:raise ValueError('unexecuted accepted action')
        if first is None:first=i
        if best is None or metric>actions[best]['internal_metric']:
            best=i;decisions.append(i)
    return first,best,decisions

def audit(ep,actions,start,finished):
    first,best,decisions=selection_history(actions)
    kinds=[a['kind'] for a in actions]
    if any(k not in ('repair','sibling') for k in kinds) or kinds.count('sibling')>1:raise ValueError('unexpected action')
    expected=['sibling','repair'] if start['cache'] else ['repair','sibling']
    compressed=[k for i,k in enumerate(kinds) if not i or k!=kinds[i-1]]
    if compressed!=expected[:len(compressed)]:raise ValueError('stage order changed')
    depths=[a['depth'] for a in actions if a['kind']=='repair']
    if depths!=list(range(1,len(depths)+1)) or len(depths)>20:raise ValueError('repair depth changed')
    actual_decisions={int(p.stem.rsplit('-',1)[1]):p for p in ep.glob('incumbent-decision-*.json')}
    if set(actual_decisions)!=set(decisions):raise ValueError('missing or extra incumbent decision')
    for i in decisions:
        chosen=shared.safe(actual_decisions[i]);a=actions[i]
        expected_choice=dict(action_index=i,submission_sha256=a['submission_sha256'],accepted_seconds=a['completed_seconds'],code_sha256=a['code_sha256'],internal_metric=a['internal_metric'])
        if chosen!=expected_choice:raise ValueError('incumbent decision differs from native action')
    incumbent=ep/'incumbent.json';first_path=ep/'first-accepted.json'
    if (best is not None)!=incumbent.exists() or (first is not None)!=first_path.exists():raise ValueError('acceptance bookkeeping')
    first_seconds=None
    if best is not None:
        if shared.safe(incumbent)!=shared.safe(actual_decisions[best]):raise ValueError('not the best native incumbent')
        first_seconds=actions[first]['completed_seconds']
        if shared.safe(first_path)!=dict(action_index=first,accepted_seconds=first_seconds):raise ValueError('first vs best latency')
    if finished:
        if finished['actions']!=len(actions) or finished['native_accepted'] is not (best is not None):raise ValueError('closure disagrees')
        if finished['first_valid_seconds']!=first_seconds:raise ValueError('closure latency disagrees')
        if finished['status']=='batch_complete' and finished['completed_stages']!=expected:raise ValueError('premature first-success stop')
    # Only completed response timing metadata is exported, never model content.
    # Timed-out/killed calls have no completed receipt and are NOT imputed.
    requests=[(kind,shared.safe(p)) for kind,stem in (('generation','generation'),('analysis','analysis')) for p in sorted(ep.glob(stem+'-*.private.json'))]
    timing=completed_request_time(requests)
    elapsed=finished['elapsed_seconds'] if finished else 2100
    if timing['observed_model_request_seconds']>elapsed+1:raise ValueError('request timing exceeds sequential episode')
    return dict(arm='original_second_then_native_repair' if start['cache'] else 'native_repair_then_original_second',
                selection_audit='PASS_INTERNAL_METRIC_FINAL_INCUMBENT',first_native_accept_seconds=first_seconds,
                native_accepted_actions=sum(a.get('native_accepted') is True for a in actions),
                incumbent_updates=len(decisions),completed_stages=finished['completed_stages'] if finished else None,**timing)

def configure():
    shared.ROOT=ROOT;shared.PREPARED=PREPARED;shared.TASK='random-acts-of-pizza'
    shared.ROLE='conditioned_native_batch_order_not_full_e2e';shared.NUMERICAL=numerical
    shared.METRIC_DELTA='auc_delta_cache_minus_baseline';shared.LATENCY_FIELD='first_native_accept_seconds';shared.EPISODE_AUDIT=audit
    shared.READOUT_CONTEXT=dict(previous_frozen_reader_commit='ee3c6da24bfdf453dbdf0e124deca9b06500b10e',
        amendment='CSV round_trip parsing to match official MLE-bench; metric, incumbent selection, budget, and run population unchanged.',
        amendment_before_batch_outcome_read=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--reader-commit',required=True);args=parser.parse_args()
    configure();shared.main(args.reader_commit)
