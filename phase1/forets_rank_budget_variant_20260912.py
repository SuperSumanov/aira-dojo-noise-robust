"""Undeployed single-vote control and common timing for a future isolated source.

Not an adaptive policy or claimed new method. Current/closed runs stay unchanged.
The same two-order implementation is the reference, not a separately rewritten judge.
"""
def once(text,old,new):
    if text.count(old)!=1:raise ValueError('rank source differs; do not patch approximately')
    return text.replace(old,new,1)

def variant(text,votes):
    if type(votes) is not int or votes not in (1,2):raise ValueError('one or two pre-frozen votes')
    text=once(text,'import re\n','import re\nimport time\n')
    text=once(text,'    orders=[list(range(n)),list(reversed(range(n)))];rankings=[]\n',
        '    orders=[list(range(n)),list(reversed(range(n)))][:VOTE_COUNT];rankings=[];timings=[]\n'.replace('VOTE_COUNT',str(votes)))
    text=once(text,"aggregation='two_order_borda_v1'",
        "aggregation="+repr('two_order_borda_v1' if votes==2 else 'single_order_rank_v1'))
    text=once(text,"        write(root/f'request-{j}.json',payload)",
        "        timer=time.monotonic()\n        write(root/f'request-{j}.json',payload)")
    text=once(text,"        rank=decode_rank(raw,order);rankings.append(rank)",
        "        rank=decode_rank(raw,order);rankings.append(rank)\n"
        "        timings.append(dict(order_index=j,request_through_parse_seconds=time.monotonic()-timer))")
    text=once(text,'    result=borda(rankings,n)',
        '    result=borda(rankings,n)' if votes==2 else
        '    result=[float(n-rankings[0].index(i)) for i in range(n)]')
    text=once(text,'top2_order_invariant=set(rankings[0][:2])==set(rankings[1][:2]),',
        'top2_order_invariant=(set(rankings[0][:2])==set(rankings[1][:2]) if len(rankings)==2 else None),')
    text=once(text,'model=MODEL,paid_calls=2,observed_task_outcomes=False)',
        'model=MODEL,paid_calls=len(rankings),observed_task_outcomes=False,rank_timings=timings,\n'
        '        timing_definition="request receipt write through reservation, transport, settlement and strict parse; excludes input construction and execution")')
    return text
