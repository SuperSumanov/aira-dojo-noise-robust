"""Aggregate-only development diagnostics. Never an independent test evaluator."""
from __future__ import annotations
import csv,json,math,statistics
from pathlib import Path

TASKS=('spooky-author-identification','random-acts-of-pizza','tweet-sentiment-extraction')

def csvrows(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def text_length(task,row):
    key='request_text_edit_aware' if task==TASKS[1] else 'text'
    return len(str(row.get(key) or '').split())

def groups(task,public):
    if task not in TASKS:raise ValueError('unregistered task')
    if task==TASKS[1]:
        train=json.loads((public/'train.json').read_bytes());test=json.loads((public/'test.json').read_bytes());key='request_id'
    else:
        train=csvrows(public/'train.csv');test=csvrows(public/'test.csv');key='id' if task==TASKS[0] else 'textID'
    lengths=sorted(text_length(task,r) for r in train)
    if not lengths:raise ValueError('empty public training')
    cuts=[lengths[(len(lengths)-1)*q//3] for q in (1,2)]
    bins={r[key]:sum(text_length(task,r)>c for c in cuts) for r in test}
    if len(bins)!=len(test):raise ValueError('duplicate public IDs')
    return cuts,bins

def auc(y,p):
    pos=[v for v,t in zip(p,y,strict=True) if t==1];neg=[v for v,t in zip(p,y,strict=True) if t==0]
    if not pos or not neg:return None
    return sum((a>b)+.5*(a==b) for a in pos for b in neg)/(len(pos)*len(neg))

def aggregate(task,truth,pred):
    if task==TASKS[0]:
        classes=('EAP','HPL','MWS')
        return statistics.mean(-math.log(max(float(p[r['author']]),1e-15)) for r,p in zip(truth,pred,strict=True))
    if task==TASKS[1]:return auc([int(r['requester_received_pizza']) for r in truth],[float(p['requester_received_pizza']) for p in pred])
    if task==TASKS[2]:
        def j(a,b):
            x=set(a.lower().split());z=set(b.lower().split())
            if not x:raise ValueError('empty truth')
            return len(x&z)/len(x|z)
        return statistics.mean(j(r['selected_text'],p['selected_text']) for r,p in zip(truth,pred,strict=True))
    raise ValueError('task')

def diagnostics(task,public,labels,submission,receipt):
    """Call only AFTER the pinned native scorer validates IDs, files and values."""
    if receipt.get('split')!='D_search_development_only':raise ValueError('wrong role')
    cuts,bins=groups(task,public);truth=csvrows(labels);predrows=csvrows(submission)
    key={'spooky-author-identification':'id','random-acts-of-pizza':'request_id','tweet-sentiment-extraction':'textID'}[task]
    pred={r[key]:r for r in predrows}
    if len(pred)!=len(predrows) or set(pred)!=set(bins) or {r[key] for r in truth}!=set(bins):raise ValueError('identity drift')
    metric={'spooky-author-identification':'log_loss','random-acts-of-pizza':'auc','tweet-sentiment-extraction':'mean_word_jaccard'}[task]
    overall=aggregate(task,truth,[pred[r[key]] for r in truth])
    if not math.isclose(overall,receipt[metric],rel_tol=1e-11,abs_tol=1e-11):raise ValueError('independent metric mismatch')
    slices=[]
    for group in range(3):
        rows=[r for r in truth if bins[r[key]]==group]
        value=aggregate(task,rows,[pred[r[key]] for r in rows]) if rows else None
        slices.append({'group':['short','medium','long'][group],'n':len(rows),'metric':value,'status':'observed' if value is not None else 'not_estimable'})
    return {'role':'development_descriptive_only','metric':metric,'lower_is_better':task==TASKS[0],
            'group_rule':'word_count_public_train_tertiles','cutpoints':cuts,'overall':overall,'slices':slices,
            'limitations':'No causal attribution or significance claim. D_search is reused adaptively. Single-class AUC slices are unknown, not zero.'}

def feedback(arm,basic,facts,goal):
    if arm not in ('A','B','C'):raise ValueError('arm')
    common=('Reflect carefully on the previous code, trusted development result and execution log. '
            'Diagnose likely causes, consider uncertainty and compute cost, and make a focused next revision. '
            'Do not claim a held-out improvement or causality from an observed development difference. '
            'Retain useful working parts; repair runtime/submission failures without gratuitous redesign. '
            'Before the Python block state the intended modification and what observation would count against it.\n')
    data={'previous_intent':goal,'trusted_result':basic}
    if arm!='A':data['aggregate_diagnostics']=facts
    suffix='' if arm!='C' else (
        '\nEvidence-use rule: separate OBSERVATION, HYPOTHESIS and NEXT CHANGE. '
        'Tie the next change to the previous intent and to a supplied observation; explicitly state missing evidence. '
        'If a target slice improves but the whole task worsens, keep both facts visible. '
        'Do not turn a missing/uncertain slice into failure or invent a new favorable slice. '
        'You may change the goal, but state why the available evidence warrants that change.\n')
    facts_text=json.dumps(data,sort_keys=True,ensure_ascii=False,allow_nan=False)
    return common+facts_text+suffix,facts_text

def compare_to_parent(current,parent,parent_code_sha256):
    """Attach only the actual generating parent's contrast; missing is not failure."""
    if current is None:return None
    import copy
    result=copy.deepcopy(current)
    result['reference']='actual_generating_parent'
    result['parent_code_sha256']=parent_code_sha256
    result['parent_overall_delta']=None if parent is None else current['overall']-parent['overall']
    for i,row in enumerate(result['slices']):
        prior=None if parent is None else parent['slices'][i]['metric']
        row['parent_delta']=None if prior is None or row['metric'] is None else row['metric']-prior
    return result
