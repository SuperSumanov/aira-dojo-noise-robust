"""Frozen failure observations for a future generator-side contrast; no scores."""
import copy
import hashlib
import json
from pathlib import Path

TAXONOMY_SHA='fbea5f58486ea518255e6227f5d26014a5e5b0d138c78ce335b66086e3c1ef2b'
RECURRENCE_SHA='f6b3b807c6c859e9c3fec6aff69a55467181f8131bb9dabd568c22b2e3bec97f'
TEXT_SHA='222da8b9d643c2023bc17683eed9b3a112260cbf443598b7275c753f7626a25c'
OPERATORS=('draft','improve','debug')
HEADER='Historical execution-error observations (frozen development memory):'

def frozen_memory(taxonomy_path,recurrence_path):
    raw=Path(taxonomy_path).read_bytes();other=Path(recurrence_path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=TAXONOMY_SHA or hashlib.sha256(other).hexdigest()!=RECURRENCE_SHA:
        raise ValueError('fixed prior-only error sources')
    t=json.loads(raw);r=json.loads(other)
    # Only the nonempty recognized families; unknown errors stay outside the
    # three-item memory rather than being represented as known failure causes.
    ranked=sorted(((v,k[8:]) for k,v in t['totals'].items() if k.startswith('pattern:') and k!='pattern:unclassified'),key=lambda x:(-x[0],x[1]))
    if [k for _,k in ranked[:3]]!=['categorical_new_fill_value','fit_or_train_keyword','early_stopping_without_validation']:
        raise ValueError('frozen family selection')
    best=sorted(r['keyword_examples'],key=lambda x:(-x['occurrences'],x['callable'],x['argument']))[0]
    if (best['callable'],best['argument'])!=('XGBClassifier.fit','early_stopping_rounds'):raise ValueError('frozen observed API exemplar')
    errors=[
        'TypeError: Cannot setitem on a Categorical with a new category; set the categories first.',
        best['callable']+"() got an unexpected keyword argument '"+best['argument']+"'.",
        'ValueError: For early stopping, at least one dataset and eval metric is required for evaluation.',
    ]
    text=HEADER+'\nThese errors occurred in earlier development programs using the same installed environment. They may not apply to the present program. Consider them when writing or repairing code; all existing task, validation, data-access and time constraints remain unchanged.\n'+ '\n'.join('- '+x for x in errors)
    return dict(schema=1,taxonomy_sha256=TAXONOMY_SHA,recurrence_sha256=RECURRENCE_SHA,
        selection_rule='three_most_frequent_recognized_error_families_and_most_frequent_keyword_exemplar',
        errors=errors,text=text,text_sha256=hashlib.sha256(text.encode()).hexdigest(),contains_scores_or_solutions=False)

def apply_memory(config,memory,enabled):
    if type(enabled) is not bool:raise ValueError('explicit memory switch')
    if (memory['taxonomy_sha256'],memory['recurrence_sha256'],memory['text_sha256'])!=(TAXONOMY_SHA,RECURRENCE_SHA,TEXT_SHA):
        raise ValueError('fixed prior-only memory identity')
    if hashlib.sha256(memory['text'].encode()).hexdigest()!=TEXT_SHA or not memory['text'].startswith(HEADER):
        raise ValueError('frozen memory text')
    out=copy.deepcopy(config)
    if (out['solver']['execution_timeout'],out['solver']['selection_policy'],out['solver']['num_children'],out['solver']['num_children_to_choose'])!=(300,'uniform_random',2,2):
        raise ValueError('exact common two-proposal execution config')
    for name in OPERATORS:
        template=out['solver']['operators'][name]['system_message_prompt_template']
        if HEADER in template['template']:raise ValueError('duplicate or already-applied memory')
        if enabled:template['template']+='\n\n'+memory['text']
    return out
