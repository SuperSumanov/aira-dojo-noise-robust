"""Exhaustive artificial ranking check; never opens experiment pools or outcomes.

Tests a mathematical property, not whether a selector improves MLE scores.
The running seed13 Borda rule remains frozen regardless of these counts.
"""
import itertools
import json


def choose(ranks,n,method):
    positions=[[r.index(i) for i in range(n)] for r in ranks]
    if method=='mean_rank':key=lambda i:(sum(p[i] for p in positions),i)
    elif method=='mean_then_worst':key=lambda i:(sum(p[i] for p in positions),max(p[i] for p in positions),i)
    elif method=='worst_rank':key=lambda i:(max(p[i] for p in positions),sum(p[i] for p in positions),i)
    else:raise ValueError('unknown artificial policy')
    return set(sorted(range(n),key=key)[:2])


def analyze(n):
    counts=dict(ordered_rank_pairs=0,nonempty_consensus=0,mean_rank_drops_consensus=0,
                worst_rank_drops_consensus=0,policies_differ=0,maximum_mean_position_cost=0,
                tie_rule_drops_consensus=0,tie_rule_differs=0,tie_rule_maximum_mean_position_cost=0)
    for left,right in itertools.product(itertools.permutations(range(n)),repeat=2):
        ranks=[left,right];consensus=set(left[:2])&set(right[:2]);counts['ordered_rank_pairs']+=1
        average=choose(ranks,n,'mean_rank');worst=choose(ranks,n,'worst_rank')
        tie=choose(ranks,n,'mean_then_worst')
        counts['nonempty_consensus']+=bool(consensus)
        counts['mean_rank_drops_consensus']+=not consensus<=average
        counts['worst_rank_drops_consensus']+=not consensus<=worst
        counts['policies_differ']+=average!=worst
        counts['tie_rule_drops_consensus']+=not consensus<=tie
        counts['tie_rule_differs']+=average!=tie
        def mean_position(slots):return sum(r.index(i) for r in ranks for i in slots)/4
        counts['maximum_mean_position_cost']=max(counts['maximum_mean_position_cost'],mean_position(worst)-mean_position(average))
        counts['tie_rule_maximum_mean_position_cost']=max(counts['tie_rule_maximum_mean_position_cost'],mean_position(tie)-mean_position(average))
    return dict(pool_width=n,**counts)


if __name__=='__main__':
    print(json.dumps(dict(artificial_rankings_only=True,experiment_pools_read=0,api_calls=0,gpu_jobs=0,
        actual_score_benefit_tested=False,running_policy_changed=False,rows=[analyze(3),analyze(4)]),indent=2))
