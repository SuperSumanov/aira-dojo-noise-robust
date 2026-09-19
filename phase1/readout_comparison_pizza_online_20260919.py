"""Closed Pizza incumbent-only reader with independent tied-rank ROC AUC."""
import argparse,math
import readout_comparison_online_continuation_20260919 as shared

def rank_auc(labels,scores):
    if len(labels)!=len(scores) or not labels:raise ValueError('aligned nonempty labels')
    if any(y not in (0,1) for y in labels) or not all(math.isfinite(s) for s in scores):raise ValueError('binary/finite')
    positives=sum(labels);negatives=len(labels)-positives
    if not positives or not negatives:raise ValueError('two classes required')
    ordered=sorted(zip(scores,labels));total=0.;i=0
    while i<len(ordered):
        j=i+1
        while j<len(ordered) and ordered[j][0]==ordered[i][0]:j+=1
        rank=(i+1+j)/2
        total+=rank*sum(y for _,y in ordered[i:j]);i=j
    return (total-positives*(positives+1)/2)/(positives*negatives)

def numerical(task,pred,truth):
    if task!='random-acts-of-pizza':raise ValueError('task')
    key='request_id';target='requester_received_pizza'
    for frame in (pred,truth):
        if set(frame.columns)!={key,target} or frame[key].isna().any() or frame[key].duplicated().any():raise ValueError('columns/ids')
    if set(pred[key])!=set(truth[key]):raise ValueError('row identity')
    a=pred.set_index(key).sort_index()[target].astype(float).tolist()
    b=truth.set_index(key).sort_index()[target].astype(float).tolist()
    return rank_auc(b,a)

def configure():
    shared.ROOT=shared.rt.BASE/'comparison-pizza-full-deadline-20260919-yaywhbo1'
    shared.PREPARED='a153be4e55a98da9e07fb75f60cee4d320da5aa91b551ce7b65bbf7967ef4ee3'
    shared.TASK='random-acts-of-pizza';shared.METRIC_DELTA='auc_delta_cache_minus_baseline';shared.NUMERICAL=numerical

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--reader-commit',required=True);args=parser.parse_args()
    configure();shared.main(args.reader_commit)
