"""Outcome-field-blind sample of public edits, not a regression-rate estimator.

Only base_code/code are accessed. No downloaded source is executed. The sample is
fixed before AST inspection; unsupported parses/matches stay in the denominator.
Changing a literal is not evidence of an unintended or harmful change.
"""
import argparse
import ast
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import time

ROOT = Path('/research/d7/spc/yzyang4/external-gome-structure-20261004-v1')
OUT = Path('/research/d7/spc/yzyang4/collateral-sample-20261006-v1')
PINS = {
    'Trace_1.json': 'ee50756cd940a1add0e44bcbb04e710233709d81f823111d70846cfe6278afb0',
    'Trace_2.json': '5a451c60ead8ac85e8eca86502cd92efe3ff1d12949510ccec394ca44dfe4cbd',
    'Trace_3.json': '8977dd468ed50d22aa173cb0aec208286e9b73142b72568861b60d55b3243ae2',
}
SALT = 'collateral-106061-task-balanced-v1'
MODELS = frozenset(('LogisticRegression Ridge RidgeClassifier Lasso ElasticNet LinearRegression '
    'SGDClassifier SGDRegressor SVC SVR LinearSVC LinearSVR MultinomialNB ComplementNB GaussianNB '
    'RandomForestClassifier RandomForestRegressor ExtraTreesClassifier ExtraTreesRegressor '
    'HistGradientBoostingClassifier HistGradientBoostingRegressor GradientBoostingClassifier '
    'GradientBoostingRegressor XGBClassifier XGBRegressor LGBMClassifier LGBMRegressor '
    'CatBoostClassifier CatBoostRegressor KNeighborsClassifier KNeighborsRegressor '
    'MLPClassifier MLPRegressor Adam AdamW SGD RMSprop Adagrad').split())
FEATURES = frozenset(('TfidfVectorizer CountVectorizer HashingVectorizer TfidfTransformer '
    'StandardScaler MinMaxScaler RobustScaler PCA TruncatedSVD PolynomialFeatures '
    'FeatureUnion ColumnTransformer OneHotEncoder OrdinalEncoder SimpleImputer').split())
CLASSES = MODELS | FEATURES


def digest(x):
    return hashlib.sha256(x if isinstance(x, bytes) else x.encode()).hexdigest()


def save(p, x):
    with p.open('x', encoding='utf-8') as f:
        json.dump(x, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        f.write('\n')


def permitted_pairs(obj, filename):
    for task, loops in sorted(obj.items()):
        assert re.fullmatch('[A-Za-z0-9_-]+', task)
        for key, loop in sorted(loops.items()):
            if key == 'scenario':
                continue
            assert re.fullmatch(r'loop_\d+', key)
            a, b = loop.get('base_code'), loop.get('code')
            if isinstance(a, str) and a.strip() and isinstance(b, str) and b.strip():
                yield dict(task=task, file=filename, loop=key,
                           base_sha256=digest(a), code_sha256=digest(b)), a, b


def rank(row):
    return digest('|'.join((SALT, row['task'], row['base_sha256'], row['code_sha256'])))


def literal(n):
    """Never export arbitrary strings, comments, docstrings or source fragments."""
    if isinstance(n, ast.Constant) and (n.value is None or type(n.value) in (int, float, bool)):
        return {'literal': n.value}
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
        v = literal(n.operand)
        if v is not None and type(v['literal']) in (int, float):
            return {'literal': -v['literal'] if isinstance(n.op, ast.USub) else v['literal']}
    if isinstance(n, (ast.Tuple, ast.List)):
        v = [literal(x) for x in n.elts]
        if all(x is not None for x in v):
            return {'literal': [x['literal'] for x in v]}
    return None


def calls(code):
    tree = ast.parse(code)
    aliases = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            for a in n.names:
                if a.name in CLASSES:
                    aliases[a.asname or a.name] = a.name
    found = collections.defaultdict(list)
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        name = n.func.id if isinstance(n.func, ast.Name) else n.func.attr if isinstance(n.func, ast.Attribute) else ''
        name = aliases.get(name, name)
        if name in CLASSES:
            params = {k.arg: literal(k.value) for k in n.keywords if k.arg is not None}
            found[name].append(dict(params=params, expanded_kwargs=any(k.arg is None for k in n.keywords),
                                    positional_arguments=len(n.args)))
    return dict(found)


def inspect_pair(a, b):
    try:
        left, right = calls(a), calls(b)
    except (SyntaxError, ValueError, RecursionError) as exc:
        return {'parse': type(exc).__name__, 'eligible_unique_common_classes': [], 'numeric_changes': []}
    common, changes, ambiguous = [], [], []
    for name in sorted(left.keys() & right.keys()):
        if len(left[name]) != 1 or len(right[name]) != 1:
            ambiguous.append(name)
            continue
        l, r = left[name][0], right[name][0]
        if l['expanded_kwargs'] or r['expanded_kwargs'] or l['positional_arguments'] != r['positional_arguments']:
            ambiguous.append(name)
            continue
        common.append(name)
        for k in sorted(l['params'].keys() & r['params'].keys()):
            x, y = l['params'][k], r['params'][k]
            if x is not None and y is not None and x != y:
                changes.append(dict(component=name, parameter=k, before=x['literal'], after=y['literal'],
                                    role='model_or_optimizer' if name in MODELS else 'feature'))
    inventory_l = {k: len(v) for k, v in left.items()}
    inventory_r = {k: len(v) for k, v in right.items()}
    return dict(parse='PASS', before_inventory=inventory_l, after_inventory=inventory_r,
        inventory_changed=inventory_l != inventory_r, eligible_unique_common_classes=common,
        ambiguous_common_classes=ambiguous, numeric_changes=changes,
        numeric_change_flag=bool(changes),
        joint_model_feature_numeric_change=any(x['role']=='model_or_optimizer' for x in changes)
            and any(x['role']=='feature' for x in changes))


def tests():
    class Forbidden:
        def __str__(self): raise AssertionError('outcome access')
        def __bool__(self): raise AssertionError('outcome access')
    bad = Forbidden()
    o = {'a': {'scenario': bad, 'loop_0': dict(base_code='x', code='y', final_hypothesis=bad,
        valid_score=bad, test_report=bad, feedback=bad)}}
    assert len(list(permitted_pairs(o, 'synthetic'))) == 1
    x = inspect_pair('from sklearn.linear_model import LogisticRegression as LR\na=LR(C=30)\nb=TfidfVectorizer(min_df=2)',
        'from sklearn.linear_model import LogisticRegression as LR\na=LR(C=.1)\nb=TfidfVectorizer(min_df=1)')
    assert x['joint_model_feature_numeric_change'] and len(x['numeric_changes']) == 2
    x = inspect_pair('a=LogisticRegression(C=1); b=LogisticRegression(C=2)', 'a=LogisticRegression(C=3)')
    assert x['ambiguous_common_classes'] == ['LogisticRegression'] and not x['numeric_changes']
    x = inspect_pair('a=LogisticRegression(C=1)', 'a=LogisticRegression(C=1, **p)')
    assert not x['numeric_changes']
    assert literal(ast.parse("'secret free text'", mode='eval').body) is None
    return {'fixtures': 5, 'forbidden_field_sentinel': 'PASS'}


def main(commit):
    assert re.fullmatch('[0-9a-f]{40}', commit)
    os.umask(0o077)
    OUT.mkdir(mode=0o700, exist_ok=False)
    start = time.monotonic()
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('analysis timeout')))
    signal.alarm(240)
    save(OUT/'plan.json', dict(question='Do fixed task-balanced natural edits change numeric settings of uniquely matched components?',
        source_commit=commit, script_sha256=digest(Path(__file__).read_bytes()), source_pins=PINS,
        salt=SALT, selection='Two minimum SHA256 ranks per task, unique exact base/code pair; before AST analysis',
        supported_classes=sorted(CLASSES), tests=tests(), gpu_hours=0, generator_calls=0, model_fits=0,
        max_seconds=240, start_unix=time.time(),
        inference_boundary='Descriptive syntactic support, not harmfulness, unintended edits, execution, population representativeness or method benefit. No outcome/intent/scenario accessor.'))
    rows, seen, totals = {}, set(), collections.Counter()
    for name, pin in PINS.items():
        raw = (ROOT/name).read_bytes()
        assert digest(raw) == pin
        rec = json.loads((ROOT/(name+'.download.json')).read_text())
        assert rec['sha256'] == pin and not rec['credential_categories']
        obj = json.loads(raw)
        del raw
        for row, a, b in permitted_pairs(obj, name):
            totals['pairs'] += 1
            key = row['task'], row['base_sha256'], row['code_sha256']
            if key in seen:
                totals['duplicate_pairs'] += 1
                continue
            seen.add(key)
            pool = rows.setdefault(row['task'], [])
            pool.append((rank(row), row, a, b))
            pool.sort(key=lambda x: x[0])
            del pool[2:]
        del obj
    sample = [(h, row, a, b) for task in sorted(rows) for h, row, a, b in rows[task]]
    save(OUT/'sample.json', dict(source_totals=dict(totals), selected=[dict(**r, sample_rank=h) for h,r,_,_ in sample],
                               plan_sha256=digest((OUT/'plan.json').read_bytes())))
    result = [dict(**row, sample_rank=h, **inspect_pair(a,b)) for h,row,a,b in sample]
    counts = dict(tasks=len(rows), selected_pairs=len(result), parsed=sum(r['parse']=='PASS' for r in result),
        unique_common_supported=sum(bool(r['eligible_unique_common_classes']) for r in result),
        numeric_changed=sum(bool(r['numeric_changes']) for r in result),
        joint_model_feature_numeric_changed=sum(r.get('joint_model_feature_numeric_change',False) for r in result),
        numeric_and_inventory_changed=sum(bool(r['numeric_changes']) and r.get('inventory_changed',False) for r in result))
    save(OUT/'structure.json', dict(counts=counts, rows=result, elapsed_seconds=time.monotonic()-start,
        plan_sha256=digest((OUT/'plan.json').read_bytes()), sample_sha256=digest((OUT/'sample.json').read_bytes()),
        outcome_fields_accessed=False, source_executed=False))
    print(json.dumps(dict(root=str(OUT), counts=counts, structure_sha256=digest((OUT/'structure.json').read_bytes()))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--commit'); p.add_argument('--tests', action='store_true'); a = p.parse_args()
    if a.tests: print(json.dumps(tests()))
    else: main(a.commit)
