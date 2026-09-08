"""Known tiny fixtures ONLY. Separate capture and independent archive-regrade passes."""
import argparse
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import sys


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def guard(output):
    counts = {'network_attempts': 0, 'real_data_attempts': 0}
    def audit(event, args):
        if event in ('socket.connect', 'socket.getaddrinfo', 'subprocess.Popen', 'os.system'):
            counts['network_attempts'] += 1
            raise RuntimeError('fixture_external_operation_denied')
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            p = Path(os.fsdecode(args[0])).absolute()
            lower = str(p).lower()
            data_suffixes = ('.csv', '.parquet', '.jsonl', '.tar', '.tar.gz', '.pt', '.safetensors')
            if (any(x in lower for x in ('prospective_decision_v1', 'target-300', 'target-522', 'first-960'))
                or (lower.endswith(data_suffixes) and not p.is_relative_to(output))):
                counts['real_data_attempts'] += 1
                raise RuntimeError('fixture_real_data_denied')
    sys.addaudithook(audit)
    return counts


def cases(sub, mod, pd, task, id_col, target):
    yield 'ordered', sub, 'VALID'
    yield 'permuted', sub.iloc[::-1], 'VALID'
    wrong = sub.copy(deep=True); wrong[id_col] = ['wrong-'+str(i) for i in range(len(wrong))]
    yield 'wrong_ids', wrong, 'INVALID_ID_CONTRACT'
    yield 'duplicate_ids', pd.concat([sub, sub.iloc[:1]], ignore_index=True), 'INVALID_ID_CONTRACT'
    yield 'missing_target', sub.drop(columns=[target]), 'INVALID_SUBMISSION'
    if task == 'google-quest-challenge':
        constant = sub.copy(deep=True)
        for col in mod.CLASSES: constant[col] = 0.5
        yield 'constant_spearman', constant, 'NONFINITE_SCORE'


def independent_read(root):
    # Deliberately does not import/call the capture module or its verifier.
    assert not (root/'FAILED.json').exists()
    receipt_raw = (root/'receipt.json').read_bytes()
    assert (root/'COMPLETE').read_bytes() == sha(receipt_raw).encode()
    r = json.loads(receipt_raw)
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    assert actual == set(r['files']) | {'receipt.json', 'COMPLETE'}
    assert not any(p.is_symlink() for p in root.rglob('*'))
    for name, info in r['files'].items():
        assert name in ('intent.json', 'result.json', 'code.py', 'submission.csv') or (
            name.startswith('sources/') and name.endswith('.txt') and '..' not in name)
        data = (root/name).read_bytes()
        assert info == {'sha256':sha(data), 'bytes':len(data)}
    intent = json.loads((root/'intent.json').read_bytes())
    assert intent['submission_sha256'] == sha((root/'submission.csv').read_bytes())
    assert intent['code_sha256'] == sha((root/'code.py').read_bytes())
    assert r['intent_sha256'] == sha((root/'intent.json').read_bytes())
    assert r['result_sha256'] == sha((root/'result.json').read_bytes())
    assert r['grading_calls'] == 1 and r['source_admission'] is False
    assert intent['execution_receipt_authenticated'] is False
    return json.loads((root/'result.json').read_bytes()), sha(receipt_raw)


def run(output, mode):
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    output = output.absolute()
    if mode == 'capture': output.mkdir(mode=0o700)
    else: assert output.is_dir()
    counts = guard(output)
    import pandas as pd
    from mlebench.grade_helpers import InvalidSubmissionError
    from phase1.fresh_grade_boundary import score_new_submission
    from phase1.scripts.validate_fresh_grader_boundary_fixtures_20260907 import TASKS, fixtures
    if mode == 'capture':
        from phase1.fresh_grade_capture import capture_grade, verify_capture
        (output/'workspaces').mkdir(); (output/'vaults').mkdir()
    rows = []
    for task in TASKS:
        mod = importlib.import_module('mlebench.competitions.'+task+'.grade')
        sub, ans, id_col, target, known_expected = fixtures(task, mod, pd)
        for name, frame, status in cases(sub, mod, pd, task, id_col, target):
            case_id = task+'__'+name; vault = output/'vaults'/case_id
            def evaluate(path):
                return score_new_submission(pd.read_csv(path), ans.copy(deep=True), id_column=id_col,
                    grade_fn=mod.grade, invalid_error=InvalidSubmissionError)
            if mode == 'capture':
                work = output/'workspaces'/case_id; work.mkdir()
                submission = work/'submission.csv'; frame.to_csv(submission, index=False)
                direct = evaluate(submission); returned = []; calls = []
                def once():
                    calls.append(1); value = evaluate(submission); returned.append(value); return value
                got = capture_grade(output=vault, submission_path=submission,
                    code=b'# synthetic fixture only; no candidate execution\n',
                    binding=dict(run_id='fixture-'+case_id, step=0, task=task,
                                 execution_receipt_sha256=sha(b'UNAUTHENTICATED_SYNTHETIC_FIXTURE_REFERENCE')),
                    sources=dict(grader=Path(mod.__file__).absolute(),
                                 boundary=Path(sys.modules[score_new_submission.__module__].__file__).absolute()),
                    evaluate=once)
                assert calls == [1] and got is returned[0] and got == direct
                assert submission.read_bytes() == (vault/'submission.csv').read_bytes()
                digest = verify_capture(vault)['receipt_sha256']
            else:
                got, digest = independent_read(vault)
                assert got == evaluate(vault/'submission.csv')
            assert got['status'] == status
            if status == 'VALID':
                assert math.isclose(got['score_raw'], known_expected, abs_tol=1e-12, rel_tol=1e-12)
                assert got['score_rounded'] == round(known_expected, 5)
            else: assert got['score_raw'] is None and got['score_rounded'] is None
            rows.append(dict(fixture=case_id, receipt_sha256=digest, compatibility_pass=True))
    assert len(rows) == 31 and not any(counts.values())
    summary = dict(classification='CAPTURE_COMPATIBILITY_FIXTURES_NOT_PRODUCTION_OR_MODEL_GAIN',
        tasks=len(TASKS), cases=len(rows), rows=rows, model_effect_measured=False, source_admission=False,
        **counts)
    with (output/(mode+'.json')).open('x') as f: json.dump(summary, f, sort_keys=True, indent=2)
    print(json.dumps({k:v for k,v in summary.items() if k != 'rows'}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=('capture','verify'), required=True)
    args = parser.parse_args(); run(args.output, args.mode)
