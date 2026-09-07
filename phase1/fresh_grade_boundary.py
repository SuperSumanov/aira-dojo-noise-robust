"""A proposed boundary for NEW reexecution labels, never a historical repair.

No file/data reader or CLI. Caller supplies a trusted, pinned external function.
Unknown exceptions fail closed instead of being converted to low-quality labels.
The immutable source function is not patched. IDs are aligned before scoring.
"""
import hashlib
import math


class SubmissionContractError(ValueError):
    pass


def aligned_copies(submission, answers, id_column):
    if not isinstance(id_column, str) or not id_column:
        raise SubmissionContractError('id_column_required')
    for frame in (submission, answers):
        if not frame.columns.is_unique or id_column not in frame.columns:
            raise SubmissionContractError('duplicate_columns_or_missing_id')
        ids = frame[id_column].tolist()
        if not ids or any(type(x) not in (int, str) for x in ids):
            raise SubmissionContractError('empty_or_unsupported_ids')
        if len({type(x) for x in ids}) != 1 or len(ids) != len(set(ids)):
            raise SubmissionContractError('mixed_or_duplicate_ids')
    left, right = submission[id_column].tolist(), answers[id_column].tolist()
    if type(left[0]) is not type(right[0]) or set(left) != set(right):
        raise SubmissionContractError('id_set_or_type_mismatch')
    # Never mutate the supplied frames; official graders may modify their copies.
    return tuple(frame.sort_values(id_column).reset_index(drop=True).copy(deep=True)
                 for frame in (submission, answers))


def score_new_submission(submission, answers, *, id_column, grade_fn, invalid_error):
    if not callable(grade_fn) or not isinstance(invalid_error, type) or not issubclass(invalid_error, Exception):
        raise ValueError('trusted_grader_and_error_type_required')
    try:
        sub, ans = aligned_copies(submission, answers, id_column)
    except SubmissionContractError as e:
        return {'status': 'INVALID_ID_CONTRACT', 'reason': str(e), 'score_raw': None, 'score_rounded': None}
    try:
        value = grade_fn(sub, ans)
    except invalid_error as e:
        return {'status': 'INVALID_SUBMISSION', 'reason_sha256': hashlib.sha256(str(e).encode()).hexdigest(),
                'score_raw': None, 'score_rounded': None}
    # Unknown runtime exceptions propagate: an infrastructure bug is not a label.
    if value is None or isinstance(value, bool):
        raise ValueError('grader_non_numeric_result')
    value = float(value)
    if not math.isfinite(value):
        return {'status': 'NONFINITE_SCORE', 'score_raw': None, 'score_rounded': None}
    return {'status': 'VALID', 'score_raw': value, 'score_rounded': round(value, 5)}
