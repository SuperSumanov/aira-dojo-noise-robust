import pytest

from phase1.g_reuse_cycle_information import components, kirchhoff, task_spectral_row
from phase1.scripts.run_g_reuse_cycle_information_20260905 import close


def test_components_include_isolates_deterministically():
    assert components({'a', 'b', 'c'}, [('a', 'b')]) == [{'a', 'b'}, {'c'}]


def test_triangle_has_half_the_path_average_resistance():
    path = [('a', 'b'), ('b', 'c')]
    triangle = path + [('a', 'c')]
    assert kirchhoff({'a', 'b', 'c'}, path) == pytest.approx(4.0)
    assert kirchhoff({'a', 'b', 'c'}, triangle) == pytest.approx(2.0)


def test_task_row_uses_same_final_partition_and_detects_cycle_information():
    local = [('a', 'b'), ('c', 'd')]
    basis = [('b', 'c')]
    full = basis + [('a', 'd')]
    row = task_spectral_row(local, full, basis)
    assert row['pair_count'] == 6
    assert row['resistance_reduction_fraction'] > 0


def test_partition_mismatch_fails_closed():
    with pytest.raises(ValueError, match='partition_mismatch'):
        task_spectral_row([('a', 'b'), ('c', 'd')], [('b', 'c')], [])


def test_runner_close_accepts_roundoff_but_rejects_structural_change():
    assert close({'x': [1.0]}, {'x': [1.0 + 1e-12]})
    assert not close({'x': [1.0]}, {'x': [1.1]})
    assert not close({'x': [1.0]}, {'y': [1.0]})
