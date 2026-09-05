import pytest
np = pytest.importorskip('numpy')
pytest.importorskip('sklearn')
from phase1.g_reuse_fixed_tfidf import fit_fixed_tfidf


def fixture():
    codes = {f'a{i}': f'import numpy as np\n# common label {i}\nx = np.arange(20)\n' for i in range(6)}
    codes.update({f'b{i}': f'import numpy as np\n# common label {i}\nx = np.zeros(20)\n' for i in range(6)})
    return codes, [(f'a{i}', f'b{i}') for i in range(6)]


def test_transform_never_fits_query_vocabulary_and_scores_antisymmetrically():
    codes, pairs = fixture(); model = fit_fixed_tfidf(codes, pairs)
    before = dict(model.vectorizer.vocabulary_)
    scores, receipt = model.score({'new_a': 'ZZZZZZZ never seen token', 'new_b': codes['a0']})
    assert model.vectorizer.vocabulary_ == before and 'ZZZ' not in before and 'zzz' not in before
    margin = scores['new_a']-scores['new_b']
    assert margin == -(scores['new_b']-scores['new_a'])
    assert receipt['state_sha256'] == model.state_sha256 and not receipt['model_refitted']


def test_exact_reference_recipe_parity():
    from scipy import sparse
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    codes, pairs = fixture(); model = fit_fixed_tfidf(codes, pairs)
    ids = sorted(codes); pos = {k: i for i, k in enumerate(ids)}
    v = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5), max_features=30000, min_df=3, sublinear_tf=True, dtype=np.float64)
    v.fit([codes[k][:20000] for k in ids]); x = v.transform([codes[k][:20000] for k in ids]).tocsr()
    d = x[[pos[a] for a,b in pairs]]-x[[pos[b] for a,b in pairs]]
    old = LogisticRegression(C=.5, max_iter=1500, solver='lbfgs', random_state=0).fit(
        sparse.vstack((d,-d), format='csr'), np.r_[np.ones(len(pairs), dtype=np.int8), np.zeros(len(pairs), dtype=np.int8)])
    assert v.vocabulary_ == model.vectorizer.vocabulary_
    np.testing.assert_array_equal(old.coef_, model.model.coef_)
    actual, _ = model.score(codes)
    np.testing.assert_allclose([actual[a]-actual[b] for a,b in pairs], d.dot(old.coef_.reshape(-1)), atol=1e-14, rtol=1e-12)


def test_input_order_invariant_and_both_label_orientations_supported():
    codes, pairs = fixture()
    first = fit_fixed_tfidf(codes, pairs)
    second = fit_fixed_tfidf(dict(reversed(list(codes.items()))), pairs[::-1])
    assert first.state_sha256 == second.state_sha256
    flipped = fit_fixed_tfidf(codes, [(b,a) for a,b in pairs])
    one, _ = first.score(codes); two, _ = flipped.score(codes)
    np.testing.assert_allclose(list(one.values()), -np.array(list(two.values())), atol=1e-12)


@pytest.mark.parametrize('failure', ['duplicate', 'extra', 'missing', 'mutated'])
def test_bad_support_or_modified_model_rejected(failure):
    codes, pairs = fixture()
    if failure == 'duplicate': pairs.append(pairs[0][::-1])
    if failure == 'extra': codes['heldout_extra'] = 'print(0)'
    if failure == 'missing': codes.pop('a0')
    if failure == 'mutated':
        model = fit_fixed_tfidf(codes, pairs); model.model.coef_[0,0] += .5
        with pytest.raises(ValueError, match='mutated'): model.score(codes)
    else:
        with pytest.raises(ValueError): fit_fixed_tfidf(codes, pairs)
