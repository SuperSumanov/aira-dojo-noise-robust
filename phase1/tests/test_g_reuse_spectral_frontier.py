from phase1.g_reuse_spectral_frontier import FRACTIONS, summarize_point


def test_fractions_are_exactly_quarter_half_three_quarters():
    assert FRACTIONS == (('25', 1, 4), ('50', 1, 2), ('75', 3, 4))


def test_summarize_point_uses_same_budget_and_reports_nonworse():
    arms = {
        'spectral': {'additional_tokens': 9, 'logdet_gain': 8.0, 'final_kirchhoff': 2.0,
                     'd_capture': 0.8, 'a_capture': 0.8},
        'cheapest': {'additional_tokens': 8, 'logdet_gain': 6.0, 'final_kirchhoff': 4.0,
                     'd_capture': 0.6, 'a_capture': 0.6},
        'hash': {'additional_tokens': 7, 'logdet_gain': 5.0, 'final_kirchhoff': 5.0,
                 'd_capture': 0.5, 'a_capture': 0.5},
    }
    row = {'additional_token_budget': 10, 'full_logdet_headroom': 10.0,
           'basis_kirchhoff': 10.0, 'full_kirchhoff': 0.0, 'arms': arms}
    result = summarize_point([row])
    assert result['aggregates']['spectral']['d_capture'] == 0.8
    assert result['aggregates']['spectral']['a_capture'] == 0.8
    assert result['spectral_not_worse_tasks'] == 1
