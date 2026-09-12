"""Undeployed strong reference: generate one, execute one, never rank.

This is not an ablation of the selector alone. It changes proposal fanout and
therefore belongs beside, not in place of, the fixed-pool randomized control.
Caller must independently bind fresh run paths/seed and a cumulative budget.
"""
import copy

ALLOWED={('solver','num_children'),('solver','critic_top_k')}

def difference_paths(a,b,path=()):
    if isinstance(a,dict) and isinstance(b,dict):
        if set(a)!=set(b):raise ValueError('field inventory differs')
        return set().union(*(difference_paths(a[k],b[k],path+(k,)) for k in a)) if a else set()
    return set() if a==b else {path}

def single_proposal(reference):
    cfg=copy.deepcopy(reference);s=cfg['solver']
    if (s['selection_policy'],s['num_children'],s['critic_top_k'],s['num_children_to_choose'],
        s['selection_coupling'],s['time_limit_secs'],s['execution_timeout']) != (
        'uniform_random',4,2,1,'common_priority_v1',600,300):
        raise ValueError('exact current randomized development reference required')
    s['num_children']=1;s['critic_top_k']=1
    if difference_paths(reference,cfg)!=ALLOWED:raise ValueError('unexpected control mutation')
    return cfg
