import copy
import json
import pytest
from phase1.historical_program_projection import project
from phase1.historical_journal_role_diagnostic import diagnose


def p(*nodes):
    return project(b'\n'.join(json.dumps(n).encode() for n in nodes))


def n(step, code='print(1)', parents=None, **kwargs):
    return dict(step=step, code=code, parents=[] if parents is None else parents, **kwargs)


def test_roles_are_not_interchangeable_and_input_unchanged():
    value = {'checkpoint': p(n(1, parents=[0])), 'live': p(n(1, code='print(2)', parents=[0]))}
    original = copy.deepcopy(value)
    r = diagnose(value)
    assert value == original
    assert r['cross_role']['unequal_projected_steps'] == 1
    assert r['cross_role']['field_difference_steps']['code_sha256'] == 1
    assert r['roles']['checkpoint']['conflicting_steps'] == 0
    assert r['nodes_selected'] == 0 and not r['source_admitted']


def test_within_role_conflict_is_retained_not_last_write_wins():
    r = diagnose({'checkpoint': p(n(1), n(1, code='x=3')), 'live': p(n(1))})
    assert r['roles']['checkpoint']['rows'] == 2
    assert r['roles']['checkpoint']['conflicting_steps'] == 1
    assert r['cross_role']['unequal_projected_steps'] == 1


def test_event_repeat_does_not_inflate_disagreement():
    r = diagnose({'checkpoint': p(n(1)), 'live': p(n(1), n(1))})
    assert r['roles']['live']['identical_repeated_rows'] == 1
    assert r['cross_role']['unequal_projected_steps'] == 0


def test_role_specific_steps_and_unknown_lines():
    r = diagnose({'checkpoint': p(n(0), {'data': {'event': 'ignored'}}), 'live': p(n(1))})
    assert r['roles']['checkpoint']['unsupported_lines'] == 1
    assert r['cross_role']['shared_steps'] == 0
    assert r['cross_role']['checkpoint_only_steps'] == r['cross_role']['live_only_steps'] == 1


def test_id_only_difference_is_separate_from_program_difference():
    r = diagnose({'checkpoint': p(n(1, id='abc')), 'live': p(n(1))})
    assert r['cross_role']['field_difference_steps']['node_id_sha256'] == 1
    assert r['cross_role']['field_difference_steps']['code_sha256'] == 0


@pytest.mark.parametrize('roles', [{}, {'live': p(n(0))}, {'checkpoint': p(n(0))},
                                  {'checkpoint': p(n(0)), 'live': p(n(0)), 'other': p(n(0))}])
def test_missing_unknown_roles_fail(roles):
    with pytest.raises(ValueError, match='exact_journal_roles'): diagnose(roles)


def test_row_order_does_not_change_diagnostic():
    a = {'checkpoint': p(n(0), n(1)), 'live': p(n(1), n(0), n(1, code='z'))}
    b = {'checkpoint': p(n(1), n(0)), 'live': p(n(1, code='z'), n(0), n(1))}
    assert diagnose(a) == diagnose(b)


def test_outcome_permutation_invariance():
    a = {'checkpoint': p(n(0, metric=123)), 'live': p(n(0, metric=-2))}
    b = {'checkpoint': p(n(0, metric=-900)), 'live': p(n(0, metric=4))}
    assert diagnose(a) == diagnose(b)
