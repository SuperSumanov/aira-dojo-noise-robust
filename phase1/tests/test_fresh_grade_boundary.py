import copy
import math
import pytest
pd = pytest.importorskip('pandas')
from phase1.fresh_grade_boundary import aligned_copies, score_new_submission


class Invalid(Exception): pass


def frame(ids=(1, 2), values=(0, 1)):
    return pd.DataFrame({'id': ids, 'value': values})


def call(sub, ans=None, fn=lambda s, a: 1/3):
    return score_new_submission(sub, frame() if ans is None else ans,
                                id_column='id', grade_fn=fn, invalid_error=Invalid)


def test_known_rounding_and_raw_precision():
    result = call(frame())
    assert result == {'status': 'VALID', 'score_raw': 1/3, 'score_rounded': 0.33333}


def test_alignment_without_mutating_either_input():
    sub, ans = frame((2, 1), (1, 0)), frame()
    left, right = copy.deepcopy(sub), copy.deepcopy(ans)
    result = call(sub, ans, lambda s, a: float((s['value'] == a['value']).mean()))
    assert result['score_raw'] == 1
    pd.testing.assert_frame_equal(sub, left); pd.testing.assert_frame_equal(ans, right)


@pytest.mark.parametrize('ids', [(1, 1), (1, 3), ('1', '2'), (True, False), (1.0, 2.0), (1, None), (1, '2')])
def test_bad_ids_are_rejected_before_grader(ids):
    def forbidden(*args): raise AssertionError('grader must not run')
    assert call(frame(ids), fn=forbidden)['status'] == 'INVALID_ID_CONTRACT'


def test_duplicate_columns_refused():
    assert call(pd.DataFrame([[1, 2]], columns=['id', 'id']))['status'] == 'INVALID_ID_CONTRACT'


def test_empty_refused():
    assert call(frame((), ()))['status'] == 'INVALID_ID_CONTRACT'


def test_invalid_submission_is_not_zero_score():
    def invalid(*args): raise Invalid('bad fixed fixture')
    result = call(frame(), fn=invalid)
    assert result['status'] == 'INVALID_SUBMISSION' and result['score_raw'] is None


def test_infrastructure_errors_propagate():
    def crashed(*args): raise RuntimeError('synthetic failure')
    with pytest.raises(RuntimeError): call(frame(), fn=crashed)


@pytest.mark.parametrize('value', [math.nan, math.inf, -math.inf])
def test_nonfinite_refused(value):
    r = call(frame(), fn=lambda s, a: value)
    assert r['status'] == 'NONFINITE_SCORE' and r['score_raw'] is None


@pytest.mark.parametrize('value', [None, True, False])
def test_nonnumeric_fails_closed(value):
    with pytest.raises(ValueError): call(frame(), fn=lambda s, a: value)


def test_string_ids_work_without_coercing_leading_zero():
    a = frame(('01', '1')); b = a.iloc[::-1]
    left, right = aligned_copies(b, a, 'id')
    assert left['id'].tolist() == right['id'].tolist() == ['01', '1']
