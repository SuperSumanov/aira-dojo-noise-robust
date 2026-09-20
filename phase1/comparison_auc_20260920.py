"""Independent binary tied-rank AUC, no framework metric call."""
import math

def rank_auc(labels,scores):
    if len(labels)!=len(scores) or not labels:raise ValueError('aligned nonempty labels')
    if any(y not in (0,1) for y in labels) or not all(math.isfinite(s) for s in scores):raise ValueError('binary/finite')
    positives=sum(labels);negatives=len(labels)-positives
    if not positives or not negatives:raise ValueError('two classes required')
    ordered=sorted(zip(scores,labels));total=0.;i=0
    while i<len(ordered):
        j=i+1
        while j<len(ordered) and ordered[j][0]==ordered[i][0]:j+=1
        total+=(i+1+j)/2*sum(y for _,y in ordered[i:j]);i=j
    return (total-positives*(positives+1)/2)/(positives*negatives)

def numerical(pred,truth):
    key='request_id';target='requester_received_pizza'
    for frame in (pred,truth):
        if set(frame.columns)!={key,target} or frame[key].isna().any() or frame[key].duplicated().any():raise ValueError('columns/ids')
    if set(pred[key])!=set(truth[key]):raise ValueError('row identity')
    return rank_auc(truth.set_index(key).sort_index()[target].astype(float).tolist(),pred.set_index(key).sort_index()[target].astype(float).tolist())
