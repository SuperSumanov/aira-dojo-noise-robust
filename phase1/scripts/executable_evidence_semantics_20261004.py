"""Post-hoc zero-fit checks of diagnostic-target and submission-file semantics.

Only public developer schemas and already reviewed code ASTs are used. This is
not a second ML experiment, a causal explanation of all score differences, or
an alteration of the frozen qualification gate. No candidate program executes.
"""
import ast
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

R = Path('/research/d7/spc/yzyang4/executable-evidence-20261004-v1')
PUBLIC = Path('/research/d7/spc/yzyang4/search-only-dev-pizza-20260927-v1/public')
PLAN = 'f5aba6d06b20a1c4037abc52c373842bae70f6672d3a2ac7b20c8bb3fc82dd3c'
CASES = [(0, 0, ['train_numeric_cols', 'test_numeric_cols', 'all_numeric_cols']),
         (0, 1, ['num_cols']), (10, 1, ['num_cols']),
         (14, 1, ['num_cols']), (14, 2, ['num_cols']),
         (14, 3, ['num_cols', 'all_numeric'])]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_json(path):
    raw = path.read_bytes()
    assert not re.search(rb'(?i)sk-[a-z0-9_.-]{10,}', raw), 'credential shape'
    return json.loads(raw), sha(raw)


def selectors(code, names, train, query):
    env = dict(__builtins__={}, np=np, train_df=train, test_df=query)
    seen = []
    for n in ast.parse(code).body:
        if not isinstance(n, ast.Assign) or len(n.targets) != 1:
            continue
        if not isinstance(n.targets[0], ast.Name) or n.targets[0].id not in names:
            continue
        assert isinstance(n.value, ast.ListComp)
        for z in ast.walk(n.value):
            assert not isinstance(z, (ast.Lambda, ast.NamedExpr, ast.Await, ast.Yield))
            if isinstance(z, ast.Call):
                assert ast.unparse(z.func) in ('train_df.select_dtypes', 'test_df.select_dtypes')
                assert not z.args and len(z.keywords) == 1
                assert z.keywords[0].arg == 'include' and ast.unparse(z.keywords[0].value) == '[np.number]'
            if isinstance(z, ast.Attribute):
                assert z.attr in ('number', 'columns', 'select_dtypes')
        value = eval(compile(ast.Expression(n.value), '<reviewed-selector>', 'eval'), env)
        assert all(isinstance(v, str) for v in value)
        env[n.targets[0].id] = value
        seen.append(dict(name=n.targets[0].id, line=n.lineno, expression=ast.unparse(n.value)))
    assert set(names) <= set(env) and seen
    return env[names[-1]], seen


def main():
    assert sha((R/'plan.json').read_bytes()) == PLAN
    assert safe_json(R/'closed.json')[0]['service_closed']
    # Match the actual parent/candidate loader exactly. pandas.read_json adds
    # dtype inference and was found to turn an object field into numeric; that
    # earlier posthoc-semantics.json is preserved but superseded, not ML data.
    train = pd.DataFrame(json.loads((PUBLIC/'train.json').read_bytes()))
    query = pd.DataFrame(json.loads((PUBLIC/'test.json').read_bytes()))
    rows = []
    for index, step, names in CASES:
        node, source_sha = safe_json(R/f'episode-{index}/action-{step}/node.private.json')
        code = node['code']
        selected, expressions = selectors(code, names, train, query)
        rows.append(dict(index=index, step=step, source_sha256=source_sha,
                         code_sha256=sha(code.encode()), selected_raw_numeric_count=len(selected),
                         unavailable_at_query=sorted(set(selected)-set(query.columns)),
                         expressions=expressions))
    assert not rows[0]['unavailable_at_query'] and not rows[2]['unavailable_at_query']
    assert not rows[5]['unavailable_at_query']
    bad = rows[1]['unavailable_at_query']
    assert bad and bad == rows[3]['unavailable_at_query'] == rows[4]['unavailable_at_query']
    # The generated explanation that a parameter erased fold separation is not
    # supported by its actual Dataset construction: check the exact AST.
    code = safe_json(R/'episode-14/action-2/node.private.json')[0]['code']
    datasets = [ast.unparse(n.args[0]) for n in ast.walk(ast.parse(code))
                if isinstance(n, ast.Call) and ast.unparse(n.func) == 'lgb.Dataset']
    assert datasets == ['X[tr]']
    script = (R/'task_feedback_real_20261001.py').read_text()
    tree = ast.parse(script)
    wrapper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'wrapper')
    namespace = {}
    exec(compile(ast.Module(body=[wrapper], type_ignores=[]), '<frozen-wrapper>', 'exec'), namespace)
    # Only our trivial synthetic code is passed to the frozen string wrapper.
    old_cwd = os.getcwd()
    with tempfile.TemporaryDirectory(prefix='semantic-fixture-', dir=R) as tmp:
        try:
            os.chdir(tmp)
            Path('submission.csv').write_text('synthetic-only\n')
            live = {'sentinel': np.array([2, 3])}
            exec(namespace['wrapper']('observed = int(sentinel.sum())', 42), live)
            fixture = dict(submission_removed=not Path('submission.csv').exists(),
                           successful_state_preserved=live['observed'] == 5)
            assert all(fixture.values())
        finally:
            os.chdir(old_cwd)
    previous = R/'posthoc-semantics.json'
    result = dict(status='PASS', plan_sha256=PLAN, script_sha256=sha(Path(__file__).read_bytes()),
                  supersedes_sha256=sha(previous.read_bytes()),
                  correction='Earlier post-hoc schema check used pandas.read_json, unlike actual code. '
                  'Its feature counts are withdrawn. This version exactly uses DataFrame(json.loads). '
                  'No frozen ML run, score, qualitative mismatch finding, or effect gate changed.',
                  schema_sources={n:sha((PUBLIC/n).read_bytes()) for n in ('train.json','test.json')},
                  selected_cases=rows, lgb_training_data_expression=datasets,
                  wrapper_synthetic_fixture=fixture,
                  limits='Post-hoc selected-case checks, not extra ML runs or a new effect gate. '
                  'Only raw numeric selectors are evaluated; common engineered features are not counted. '
                  'No model fitting, generation, hidden labels, prediction or outcome values. '
                  'Feature-set change is verified; its contribution to the reported AUC gap is not identified. '
                  'Wrapper fixture explains file absence, not the cause of every refit or task failure.')
    raw = (json.dumps(result, indent=2, sort_keys=True) + '\n').encode()
    with (R/'posthoc-semantics-v2.json').open('xb') as f:
        f.write(raw)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
