import pytest

from phase1.g_reuse_spectral_midpoint import ResistanceState, TaskGraph, select
from phase1.verify_g_reuse_spectral_midpoint import GroundedState


def test_resistance_update_matches_triangle_kirchhoff():
    state = ResistanceState({'a', 'b', 'c'}, [('a', 'b'), ('b', 'c')])
    assert state.kirchhoff() == pytest.approx(4.0)
    gain = state.add(('a', 'c'))
    assert gain == pytest.approx(__import__('math').log(3.0))
    assert state.kirchhoff() == pytest.approx(2.0)


def test_task_graph_clone_is_independent():
    graph = TaskGraph([('a', 'b'), ('c', 'd')], [('b', 'c'), ('a', 'd')], [('b', 'c')])
    clone = graph.clone()
    before = graph.kirchhoff()
    clone.add(('a', 'd'))
    assert clone.kirchhoff() < before
    assert graph.kirchhoff() == pytest.approx(before)


def test_spectral_selector_respects_budget_and_prefers_more_information_per_token():
    state = TaskGraph([('a', 'b'), ('b', 'c'), ('c', 'd')],
                      [('a', 'c'), ('a', 'd')], [])
    result = select(state, [('a', 'c'), ('a', 'd')],
                    {('a', 'c'): 2, ('a', 'd'): 2}, 2, 'spectral')
    assert result['additional_tokens'] == 2
    assert result['additional_edges'] == 1
    assert result['logdet_gain'] > 0


def test_unknown_selector_fails():
    state = TaskGraph([('a', 'b')], [('a', 'b')], [])
    with pytest.raises(ValueError, match='unknown_selector'):
        select(state, [], {}, 0, 'unknown')


def test_grounded_state_matches_shifted_state_on_path_and_update():
    shifted = ResistanceState({'a', 'b', 'c'}, [('a', 'b'), ('b', 'c')])
    grounded = GroundedState({'a', 'b', 'c'}, [('a', 'b'), ('b', 'c')])
    assert grounded.kirchhoff() == pytest.approx(shifted.kirchhoff())
    assert grounded.resistance(('a', 'c')) == pytest.approx(shifted.resistance(('a', 'c')))
    assert grounded.add(('a', 'c')) == pytest.approx(shifted.add(('a', 'c')))
    assert grounded.kirchhoff() == pytest.approx(shifted.kirchhoff())
