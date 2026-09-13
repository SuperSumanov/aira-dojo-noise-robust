"""Independent reference replay from prior executed journal nodes, no re-ranking."""
import hashlib
import json
from pathlib import Path


def read(p):return json.loads(Path(p).read_bytes())
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()


def expected_references(nodes, parent_id, step):
    prior=[n for n in nodes if n['step']<step and n.get('exec_time') is not None
           and not (n['step']==0 and n['code']=='' and not n['parents'])]
    parents=[n for n in prior if n['id']==parent_id]
    if len(parents)!=1:raise ValueError('exact previously executed parent absent')
    good=[n for n in prior if n.get('is_buggy') is False and n['metric'].get('value') is not None]
    best=None
    if good:
        if len({n['metric']['maximize'] for n in good})!=1:raise ValueError('metric direction disagreement')
        best=(max if good[0]['metric']['maximize'] else min)(good,key=lambda n:n['metric']['value'])
    requested=[('parent',parents[0]),('incumbent',best)]+[('recent',n) for n in prior[-2:]]
    result=[];seen={}
    for role,n in requested:
        if n is None:continue
        if n['id'] in seen:result[seen[n['id']]]['roles'].append(role);continue
        seen[n['id']]=len(result)
        result.append(dict(roles=[role],step=n['step'],code=n['code'],
            code_sha256=hashlib.sha256(n['code'].encode()).hexdigest(),execution_seconds=n['exec_time'],
            exit_code=n['exit_code'],agent_marked_buggy=n['is_buggy'],search_validation=n['metric']['value'],
            search_validation_maximize=n['metric']['maximize']))
    return result


def verify_reference(pool,checkpoint,rank,inp,done):
    request=read(rank/'request-0.json');messages=request['messages']
    if len(messages)!=2 or [m['role'] for m in messages]!=['system','user']:raise ValueError('request message roles')
    context=json.loads(messages[1]['content'])['executed_reference_context']
    if set(context)!={'protocol','decision_step','remaining_search_seconds','references','unexecuted_candidate_feedback','caveat'}:
        raise ValueError('unexpected reference fields')
    if (context['protocol']!='executed_reference_v1' or context['unexecuted_candidate_feedback'] is not False
        or not 0<context['remaining_search_seconds']<=600 or context['decision_step']!=pool['binding']['step']):
        raise ValueError('reference decision boundary')
    if (inp['reference_sha256']!=digest(context) or done['reference_sha256']!=digest(context)
        or done['observed_candidate_outcomes'] is not False or done['observed_reference_feedback'] is not True):
        raise ValueError('reference hash/visibility')
    nodes=[json.loads(line) for line in (checkpoint/'journal.jsonl').read_bytes().splitlines() if line.strip()]
    if context['references']!=expected_references(nodes,pool['binding']['parent_id'],pool['binding']['step']):
        raise ValueError('references differ from independently replayed prior journal')
    return dict(reference_count=len(context['references']),prior_only=True)
