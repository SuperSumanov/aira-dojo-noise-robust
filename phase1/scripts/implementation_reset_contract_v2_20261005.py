"""Repair R11's treatment delivery, not a claim of method gain.

Standalone standard-library tests can run while the research mount is unavailable.
Native Dojo rendering and real task executions remain separate required gates.
"""
from __future__ import annotations
import ast
import copy
import random

TASKS = ('random-acts-of-pizza', 'spooky-author-identification')
ARMS = ('continue', 'reimplement', 'new_idea', 'random_hpo')
IDEA = '''Use only the main text field. Fit a single sparse WORD TfidfVectorizer
on training rows, and one LogisticRegression classifier with predict_proba.
Do not add character features, metadata features, another classifier or ensembles.
Tokenization, word n-grams, vocabulary, regularization and solver may change.
The output is one final classifier, not an ensemble of CV members.
Public training-only validation is optional, never mandatory five-fold CV.'''

COMMON = '''You implement a bounded development experiment in a fresh workspace.
The experiment contract in THIS system message controls the permitted method.
Task descriptions provide file schemas and metrics, not competing strategy rules.
Use only supplied training labels and unlabeled prediction rows in ./data.
No downloads, external model services, evaluator files or hidden labels.
Return at most three sentences, then ONE complete executable Python code block.
Save ./submission.csv with the task's exact row IDs and column names.
Generation, execution, validation and scoring share a 600-second deadline;
each execution is at most 240 seconds. Optional validation uses training rows only.
Every condition retains the same incumbent externally; no cached runtime state.
Do not run exploratory or diagnostic-only code instead of a complete solution.'''

VISIBILITY = {
    'draft': '\nImplement from a blank code context. No previous code is supplied.',
    'improve': '\nImprove the supplied code while respecting the experiment contract.',
    'debug': '\nFix the supplied code. If it violates the experiment contract, correct\nthat violation; do NOT preserve an out-of-contract classifier or representation.',
}
USER = {
    'draft': '# TASK\n{{task_desc}}\n# DATA\n{{data_overview}}\n',
    'improve': '# TASK\n{{task_desc}}\n# PREVIOUS CODE\n{{prev_code}}\n# PREVIOUS EXECUTION\n{{prev_terminal_output}}\n',
    'debug': '# TASK\n{{task_desc}}\n# CODE TO CORRECT\n{{prev_buggy_code}}\n# ERROR\n{{execution_output}}\n',
}

def system_prompt(arm, kind):
    if arm not in ARMS or kind not in USER:
        raise ValueError('unregistered condition')
    if arm == 'random_hpo':
        raise ValueError('HPO must never call the generator')
    if arm == 'new_idea':
        contract = ('Implement a DIFFERENT representation or classifier family from the '
                    'following old idea, not merely another seed or hyperparameter. '
                    'The following describes the OLD idea, NOT your required method:\n' + IDEA)
    else:
        contract = 'REQUIRED MODELING FAMILY, including during debugging:\n' + IDEA
        contract += ('\nRetain and improve the provided code.' if arm == 'continue'
                     else '\nIndependently implement the same family without the old code.')
    return COMMON + '\n' + contract + VISIBILITY[kind]

def operator_config(config, arm, kind):
    """Replace (not append to) conflicting templates in native typed JSON configs."""
    out = copy.deepcopy(config)
    import re
    for key, text in (('system_message_prompt_template', system_prompt(arm, kind)),
                      ('init_user_message_prompt_template', USER[kind])):
        out[key]['template'] = text
        out[key]['input_variables'] = sorted(set(re.findall(r'{{\s*(\w+)\s*}}', text)))
    # Keep model, temperature, tokenizer, output length and transport unchanged.
    return out

def generation_failure(exc):
    """Recognize bounded transport timeouts; never hide arbitrary RuntimeErrors.

    A recognized timeout ends the episode with its incumbent, NOT an immediate
    retry whose uncancelled server work could exceed the shared budget.
    """
    if isinstance(exc, TimeoutError):
        return 'bounded_generation_timeout'
    if type(exc) is RuntimeError and str(exc) == 'bounded API attempt failed: TimeoutError':
        return 'bounded_generation_timeout'
    return None

def family_screen(code):
    """Conservative syntactic contract, explicitly NOT semantic equivalence.

    Resolve direct import aliases and module aliases. Reject alternate ML imports,
    dynamic code, custom classifiers and explicit non-word vectorization. Do not
    pretend that the presence of LR proves predictions actually came from it.
    Actual selected programs still need outcome-blind semantic review.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {'pass': False, 'reasons': ['syntax_error'], 'semantic_verified': False}
    aliases = {}; reasons = set(); calls = []
    allowed = {'numpy', 'pandas', 'scipy', 'json', 'csv', 'os', 'pathlib', 're',
               'string', 'collections', 'warnings', 'time', 'math', 'random', 'sys'}
    sklearn_allowed = {'sklearn.feature_extraction.text', 'sklearn.linear_model',
                       'sklearn.metrics', 'sklearn.model_selection', 'sklearn.pipeline'}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                aliases[a.asname or a.name.split('.')[0]] = a.name if a.asname else a.name.split('.')[0]
                if a.name.split('.')[0] not in allowed and a.name not in sklearn_allowed:
                    reasons.add('unsupported_import')
        if isinstance(n, ast.ImportFrom):
            module = n.module or ''
            if n.level or (module.split('.')[0] not in allowed and module not in sklearn_allowed):
                reasons.add('unsupported_import')
            for a in n.names:
                if a.name == '*': reasons.add('wildcard_import')
                aliases[a.asname or a.name] = module + '.' + a.name
        if isinstance(n, ast.ClassDef): reasons.add('custom_class_requires_review')
    def name(n):
        if isinstance(n, ast.Name): return aliases.get(n.id, n.id)
        if isinstance(n, ast.Attribute): return name(n.value) + '.' + n.attr
        return ''
    vectors = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call): continue
        k = name(n.func); calls.append(k)
        if k in ('eval', 'exec', '__import__', 'compile', 'getattr', 'setattr', 'globals', 'locals'):
            reasons.add('dynamic_execution_requires_review')
        if k.startswith('sklearn.'):
            leaf = k.rsplit('.', 1)[-1]
            if leaf[:1].isupper() and leaf not in ('TfidfVectorizer','LogisticRegression',
                                                 'Pipeline','StratifiedKFold','KFold'):
                reasons.add('alternate_estimator_or_features')
        if k == 'sklearn.feature_extraction.text.TfidfVectorizer':
            vectors.append(n)
            for kw in n.keywords:
                if kw.arg is None: reasons.add('dynamic_vectorizer_kwargs_requires_review')
                if kw.arg == 'analyzer' and not (isinstance(kw.value, ast.Constant) and kw.value.value == 'word'):
                    reasons.add('nonword_or_dynamic_analyzer')
    if len(vectors) != 1: reasons.add('requires_one_vectorizer_constructor')
    if calls.count('sklearn.linear_model.LogisticRegression') != 1:
        reasons.add('requires_one_lr_constructor')
    if not any(x.endswith('.fit') or x.endswith('.fit_transform') for x in calls): reasons.add('missing_fit')
    if not any(x.endswith('.predict_proba') for x in calls): reasons.add('missing_predict_proba')
    return {'pass': not reasons, 'reasons': sorted(reasons), 'semantic_verified': False}

def hpo_configs(seed, n=64):
    rng = random.Random(seed)
    grid = [dict(C=c, ngram_max=g, min_df=d, max_features=f, sublinear_tf=s)
            for c in (.1, .3, 1., 3., 10.) for g in (1, 2)
            for d in (1, 2, 3) for f in (20000, 50000) for s in (False, True)]
    rng.shuffle(grid)
    return grid[:n]

BASELINE = dict(C=1., ngram_max=2, min_df=2, max_features=50000, sublinear_tf=True)

def source_program(task, seed, params=None):
    """Human-specified fixed baseline; no selection on outcomes or old candidates."""
    if task not in TASKS: raise ValueError('task not registered')
    p = BASELINE.copy() if params is None else params.copy()
    assert set(p) == set(BASELINE)
    # No fitting on test rows, sparse-to-dense conversion, metadata or CV ensemble.
    return f'''import json, os
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
task = {task!r}
root = Path('./data')
if task == 'random-acts-of-pizza':
    train = pd.DataFrame(json.loads((root/'train.json').read_text()))
    test = pd.DataFrame(json.loads((root/'test.json').read_text()))
    key, text, target = 'request_id', 'request_text_edit_aware', 'requester_received_pizza'
    y = train[target].astype(int).to_numpy()
else:
    train, test = pd.read_csv(root/'train.csv'), pd.read_csv(root/'test.csv')
    key, text, target = 'id', 'text', 'author'
    y = train[target].to_numpy()
v = TfidfVectorizer(analyzer='word', ngram_range=(1,{p['ngram_max']!r}),
    min_df={p['min_df']!r}, max_features={p['max_features']!r},
    sublinear_tf={p['sublinear_tf']!r}, dtype=np.float64)
X = v.fit_transform(train[text].fillna('').astype(str))
Xt = v.transform(test[text].fillna('').astype(str))
m = LogisticRegression(C={p['C']!r}, solver='lbfgs', max_iter=300, random_state={seed!r})
m.fit(X, y)
pred = m.predict_proba(Xt)
out = pd.DataFrame({{key: test[key]}})
if task == 'random-acts-of-pizza':
    out[target] = pred[:, list(m.classes_).index(1)]
else:
    for c in ('EAP', 'HPL', 'MWS'): out[c] = pred[:, list(m.classes_).index(c)]
assert np.isfinite(pred).all()
out.to_csv('submission.csv', index=False)
print('submission rows', len(out))
'''

def schedule():
    # Two fixed task sources, repeated generation seeds; NOT four independent ideas.
    rows=[]
    for b in range(2):
        order=ARMS if b==0 else tuple(reversed(ARMS))
        for j,arm in enumerate(order):
            for t,task in enumerate(TASKS):
                rows.append(dict(index=len(rows), wave=4*b+j, task=task, start=t,
                                 seed=111501+10*b+t, execution_seed=111401+t, arm=arm))
    return rows

def decision(contrasts):
    """Predeclared numerical screen only; cannot authorize expansion by itself."""
    if len(contrasts)!=4 or any(not x.get('complete') for x in contrasts):
        return 'incomplete'
    keys=('continue','new_idea','random_hpo')
    if all(all(x['reimplement_minus_'+k]>0 for k in keys) for x in contrasts):
        return 'numerical_signal_requires_semantic_review_and_fresh_confirmation'
    return 'no_consistent_advantage_under_this_protocol'
