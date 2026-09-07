"""Known small-table fixtures only; no registry/dataset/model reader."""
import importlib
import json
import math
import os
from pathlib import Path


TASKS = ('dog-breed-identification', 'google-quest-challenge', 'histopathologic-cancer-detection',
         'kuzushiji-recognition', 'tabular-playground-series-dec-2021', 'tabular-playground-series-may-2022')


def fixtures(task, module, pd):
    if task == 'dog-breed-identification':
        classes = list(module.DOGS_LIST); n = len(classes)
        answers = pd.DataFrame({c: [int(i == j) for i in range(n)] for j, c in enumerate(classes)})
        submission = pd.DataFrame({c: [1/n] * n for c in classes})
        for f in (answers, submission): f.insert(0, 'id', ['fixture-'+str(i) for i in range(n)])
        return submission, answers, 'id', classes[0], math.log(n)
    if task == 'google-quest-challenge':
        answers = pd.DataFrame({c: [0.0, 0.25, 0.5, 1.0] for c in module.CLASSES})
        answers.insert(0, 'qa_id', [3, 1, 4, 2])
        return answers.copy(deep=True), answers, 'qa_id', module.CLASSES[0], 1.0
    if task in ('histopathologic-cancer-detection', 'tabular-playground-series-may-2022'):
        target = 'label' if task.startswith('histopathologic') else 'target'
        answers = pd.DataFrame({'id': ['a','b','c','d'], target: [0,1,0,1]})
        submission = pd.DataFrame({'id': ['a','b','c','d'], target: [0.1,0.9,0.2,0.8]})
        return submission, answers, 'id', target, 1.0
    if task == 'kuzushiji-recognition':
        answers = pd.DataFrame({'image_id': ['synthetic-img'], 'labels': ['U+003F 0 0 10 10']})
        submission = pd.DataFrame({'image_id': ['synthetic-img'], 'labels': ['U+003F 3 3']})
        return submission, answers, 'image_id', 'labels', 1.0
    assert task == 'tabular-playground-series-dec-2021'
    answers = pd.DataFrame({'Id': [1,2,3], 'Cover_Type': [1,2,1]})
    submission = pd.DataFrame({'Id': [1,2,3], 'Cover_Type': [1,2,2]})
    return submission, answers, 'Id', 'Cover_Type', 2/3


def run():
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    import pandas as pd
    from mlebench.grade_helpers import InvalidSubmissionError
    from phase1.fresh_grade_boundary import score_new_submission
    rows = []
    for task in TASKS:
        mod = importlib.import_module('mlebench.competitions.'+task+'.grade')
        sub, ans, id_col, target, expected = fixtures(task, mod, pd)
        def evaluate(s, a):
            return score_new_submission(s, a, id_column=id_col, grade_fn=mod.grade,
                                        invalid_error=InvalidSubmissionError)
        for name, frame in (('ordered', sub), ('permuted', sub.iloc[::-1])):
            got = evaluate(frame, ans)
            assert got['status'] == 'VALID' and math.isclose(got['score_raw'], expected, abs_tol=1e-12, rel_tol=1e-12)
            assert got['score_rounded'] == round(expected, 5)
            rows.append({'task':task, 'case':name, 'result':got, 'independent_expected':expected})
        wrong = sub.copy(deep=True)
        wrong[id_col] = ['wrong-'+str(i) for i in range(len(wrong))]
        got = evaluate(wrong, ans)
        assert got['status'] == 'INVALID_ID_CONTRACT' and got['score_raw'] is None
        rows.append({'task':task, 'case':'wrong_ids', 'result':got})
        dup = pd.concat([sub, sub.iloc[:1]], ignore_index=True)
        got = evaluate(dup, ans)
        assert got['status'] == 'INVALID_ID_CONTRACT'
        rows.append({'task':task, 'case':'duplicate_ids', 'result':got})
        got = evaluate(sub.drop(columns=[target]), ans)
        assert got['status'] == 'INVALID_SUBMISSION' and got['score_raw'] is None
        rows.append({'task':task, 'case':'missing_target', 'result':got})
        if task == 'google-quest-challenge':
            constant = sub.copy(deep=True)
            for col in mod.CLASSES: constant[col] = 0.5
            got = evaluate(constant, ans)
            assert got['status'] == 'NONFINITE_SCORE' and got['score_raw'] is None
            rows.append({'task':task, 'case':'constant_spearman', 'result':got})
    assert len(rows) == 31
    return {'classification':'FRESH_GRADER_KNOWN_FIXTURES_NOT_REAL_LABELS_OR_MODEL_GAIN',
            'rows':rows, 'tasks':len(TASKS), 'real_submission_reads':0, 'real_answer_reads':0,
            'source_admitted':False, 'model_effect_measured':False}


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(); p.add_argument('--output', required=True, type=Path); a = p.parse_args()
    result = run()
    with a.output.open('x') as f: json.dump(result, f, sort_keys=True, indent=2, allow_nan=False)
    print(json.dumps({'status':result['classification'], 'tasks':result['tasks'], 'cases':len(result['rows'])}))
