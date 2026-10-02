"""Public-training-only example selection; not an error-correction algorithm."""
import hashlib
import json
import numpy as np

def packet(texts, labels, probabilities, names, seed, policy):
    y=np.asarray(labels,dtype=int);p=np.asarray(probabilities,dtype=float)
    assert policy in ('uniform','contrast')
    assert p.shape==(len(y),len(names)) and len(texts)==len(y)
    assert np.isfinite(p).all() and np.all(p>=0) and np.allclose(p.sum(1),1)
    assert set(y)==set(range(len(names))) and len(names) in (2,3)
    losses=-np.log(np.maximum(p[np.arange(len(y)),y],1e-12))
    rng=np.random.RandomState(seed);selected=[];per_class=12//len(names)
    for c in range(len(names)):
        ids=np.flatnonzero(y==c);assert len(ids)>=4*per_class
        if policy=='uniform': chosen=rng.choice(ids,per_class,replace=False)
        else:
            # Sample tails, not just the single most extreme outliers.
            order=ids[np.argsort(losses[ids],kind='stable')]
            tail=max(per_class,len(ids)//4)
            chosen=np.concatenate([rng.choice(order[:tail],per_class//2,replace=False),
                                   rng.choice(order[-tail:],per_class//2,replace=False)])
        selected.extend(int(i) for i in chosen)
    rng.shuffle(selected);assert len(set(selected))==12
    rows=[dict(row_index=i,text=str(texts[i])[:600],true_class=names[int(y[i])],
               prediction={name:round(float(p[i,j]),6) for j,name in enumerate(names)}) for i in selected]
    # An identical interpretation warning in both conditions; policies are recorded
    # privately rather than adding different persuasion/instructions to prompts.
    shown=dict(scope='Twelve class-balanced PUBLIC TRAINING examples with out-of-fold predictions. Not a representative population sample or independent validation. Predictions have already been used for model/hyperparameter selection. Do not memorize row IDs or treat individual errors as causal explanations.',
               examples=rows)
    metadata=dict(policy=policy,seed=seed,selected_indices=selected,
                  population_rows=len(y),class_counts={names[c]:int(sum(y==c)) for c in range(len(names))},
                  mean_selected_loss=float(losses[selected].mean()),mean_population_loss=float(losses.mean()),
                  predictions_sha256=hashlib.sha256(np.ascontiguousarray(p,dtype='<f8').tobytes()).hexdigest(),
                  labels_sha256=hashlib.sha256(np.ascontiguousarray(y,dtype='<i8').tobytes()).hexdigest(),
                  shown_sha256=hashlib.sha256(json.dumps(shown,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
    return shown,metadata

def from_namespace(ns,task,seed,policy):
    if task=='random-acts-of-pizza':
        train=ns['train'];y=np.asarray(ns['y'])
        if ns['blend_auc']>=ns['aucs'][ns['best_single']]: positive=np.asarray(ns['blend_oof'])
        else: positive=np.asarray(ns['to_rank'](ns['models'][ns['best_single']][0]))
        texts=(train['request_title'].fillna('').astype(str)+' | '+train['request_text_edit_aware'].fillna('').astype(str)).tolist()
        p=np.column_stack([1-positive,positive]);names=['not_received','received']
        source='Public OOF rank scores of the selected initial model/blend; ranks are not calibrated probabilities.'
    elif task=='spooky-author-identification':
        train=ns['train_df'];y=ns['y_train'];texts=train['text'].fillna('').astype(str).tolist()
        p=ns['oof_tfidf_c'];names=list(ns['classes'])
        source='Public OOF predictions of the TF-IDF component only, not the potentially stochastic embedding component or the full final blend.'
    else: raise ValueError('task not allowed')
    shown,meta=packet(texts,y,p,names,seed,policy);shown['prediction_source']=source
    meta['shown_sha256']=hashlib.sha256(json.dumps(shown,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    print('PUBLIC_EXAMPLE_PACKET '+json.dumps(dict(shown=shown,metadata=meta),sort_keys=True,ensure_ascii=False))
