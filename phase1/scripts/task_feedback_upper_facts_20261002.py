"""Public-source evidence plus a curated recommendation; not an automated analyzer."""
import hashlib,json
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/task-feedback-upper-20261002-v1')
def packet(task):
    p=json.loads((ROOT/'evidence.json').read_bytes())
    x=next(x for x in p['checks'] if x['task']==task)
    result={'role':'historical_initial_program_public_input_checks','source_code_sha256':x['raw_code_sha256'],'not_revalidated_on_current_revision':True,'limitations':'Public training evidence is not held-out benefit. Recheck applicability to your current program. No claim that a repair improves the task score.'}
    if task=='random-acts-of-pizza':result['behavioral_evidence']=x['batch_invariance']
    elif task=='tweet-sentiment-extraction':result['behavioral_evidence']=x['input_contract']
    else:raise ValueError('unregistered task')
    return result
def diagnostics(task,public,labels,submission,receipt):
    # Signature is inherited; deliberately NEVER open labels or submission here.
    if receipt.get('split')!='D_search_development_only':raise ValueError('role')
    return packet(task)
def compare_to_parent(current,parent,parent_code_sha256):return current
def feedback(arm,basic,facts,goal):
    if arm not in 'ABC':raise ValueError('arm')
    common=('Reflect carefully on the previous code, trusted development result and execution log. Diagnose likely causes, consider uncertainty and compute cost, and make a focused next revision. '
            'Retain useful working components; repair failures without gratuitous redesign. Before the Python block state your intended modification and what observation would count against it. '
            'You may inspect and validate on public training data. Development improvements are not independent generalization evidence.\n')
    data={'previous_intent':goal,'trusted_result':basic}
    if arm!='A':data['verified_initial_evidence']=facts
    encoded=json.dumps(data,sort_keys=True,ensure_ascii=False,allow_nan=False)
    advice=''
    if arm=='C' and facts:
        e=facts['behavioral_evidence']
        if 'same_record_changed_columns' in e:
            advice=('Human-curated candidate repair, NOT proven score improvement: fit the days_since_start origin ONCE from training timestamps, and reuse that same origin for both train and all prediction batches. '
                    'Check that transforming a record alone and in a batch yields identical features. Retain the working model and other features to isolate this change. If already fixed, say so; do not repeat it. ')
        else:
            advice=('Human-curated candidate repair, NOT proven score improvement: incorporate the provided sentiment in prediction. Test returning full original text for neutral tweets on public training-side validation; retain learned span extraction for non-neutral. '
                    'Preserve original-text offsets and do not clamp true spans to an unobserved end position. Prefer one small testable change first; if sentiment/coverage is already handled, say so instead of adding it again. ')
    return common+encoded+('\n'+advice if advice else ''),encoded
def auc(y,p):
    pos=[v for v,t in zip(p,y,strict=True) if t==1];neg=[v for v,t in zip(p,y,strict=True) if t==0]
    return sum((a>b)+.5*(a==b) for a in pos for b in neg)/(len(pos)*len(neg)) if pos and neg else None
