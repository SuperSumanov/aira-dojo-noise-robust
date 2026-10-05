"""Posthoc positive-control ablation; concatenate after the pinned old program.

Only vocabulary capacity/representation changes. The old grid, split, solver,
selection and full-train refit remain identical. No generator or new method.
"""

def vectors(arm, p):
    assert arm in ('word', 'word_25k', 'word_char')
    word = TfidfVectorizer(ngram_range=(1, p['ngram']), min_df=p['min_df'],
        max_features=50000 if arm == 'word' else 25000,
        sublinear_tf=True, dtype=np.float64)
    if arm in ('word', 'word_25k'):
        return [word]
    return [word, TfidfVectorizer(analyzer='char', ngram_range=(3, 5),
        min_df=p['min_df'], max_features=25000,
        sublinear_tf=True, dtype=np.float64)]


def capacity_tests():
    p = dict(ngram=2, min_df=1)
    expected = {'word': [50000], 'word_25k': [25000], 'word_char': [25000, 25000]}
    for arm, caps in expected.items():
        vs = vectors(arm, p)
        assert [v.max_features for v in vs] == caps
        x, z = design(vs, ['alpha beta', 'beta gamma', 'alpha delta'], ['unknownqq alpha'])
        assert all('unknownqq' not in v.vocabulary_ for v in vs)
        assert np.allclose(np.asarray(x.multiply(x).sum(1)).ravel(), 1)
    assert vectors('word_25k', p)[0].get_params() == vectors('word_char', p)[0].get_params()
    return dict(status='PASS', arms=3, fixed_grid=len(GRID), matched_word_block=True,
                query_not_fitted=True, normalization_checked=True)
