"""Fixed train-only TF-IDF scalar baseline; no file reader or dev tuning.

This carries the established char_wb baseline's exact fitting/prediction recipe
into a train-only interface. The caller must separately bind which qualified
TRAIN pair pool it supplies. A dictionary is not a source-qualification proof.
"""
from dataclasses import dataclass
import hashlib
import json
import time


def require(ok, reason):
    if not ok: raise ValueError(reason)


def validate_codes(codes):
    require(type(codes) is dict and bool(codes), 'tfidf_codes_required')
    require(all(type(k) is str and bool(k) and type(v) is str for k, v in codes.items()), 'tfidf_codes_schema')


def fingerprint(vectorizer, model):
    h = hashlib.sha256()
    # sklearn may store vocabulary indices as numpy.int64 after pruning.
    h.update(json.dumps(sorted((k, int(v)) for k, v in vectorizer.vocabulary_.items()), separators=(',', ':')).encode())
    for x in (vectorizer.idf_, model.coef_, model.intercept_, model.n_iter_):
        h.update(str(x.dtype).encode()); h.update(str(x.shape).encode()); h.update(x.tobytes())
    h.update(json.dumps(vectorizer.get_params(), sort_keys=True, default=str).encode())
    h.update(json.dumps(model.get_params(), sort_keys=True, default=str).encode())
    return h.hexdigest()


@dataclass(frozen=True)
class FittedFixedTfidf:
    vectorizer: object
    model: object
    state_sha256: str
    fit_receipt: dict

    def score(self, codes):
        """One scalar per supplied endpoint, without labels, refit or intercept."""
        import numpy as np
        validate_codes(codes)
        require(fingerprint(self.vectorizer, self.model) == self.state_sha256, 'tfidf_model_mutated')
        ids = sorted(codes); start = time.monotonic()
        x = self.vectorizer.transform([codes[k][:20000] for k in ids]).tocsr()
        scores = np.asarray(x.dot(self.model.coef_.reshape(-1)), dtype=np.float64).reshape(-1)
        elapsed = time.monotonic()-start
        require(scores.shape == (len(ids),) and np.isfinite(scores).all(), 'tfidf_nonfinite_score')
        require(fingerprint(self.vectorizer, self.model) == self.state_sha256, 'tfidf_query_changed_model')
        return dict(zip(ids, (float(x) for x in scores))), {
            'endpoints': len(ids), 'query_seconds': elapsed, 'state_sha256': self.state_sha256,
            'query_includes_transform': True, 'includes_state_verification_time': False,
            'labels_received': False, 'model_refitted': False}


def fit_fixed_tfidf(train_codes, better_worse_train):
    """Fit precisely once on unique train endpoints and symmetric train pairs."""
    import numpy as np
    import scipy
    from scipy import sparse
    import sklearn
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    validate_codes(train_codes)
    require(type(better_worse_train) in (list, tuple) and bool(better_worse_train), 'tfidf_train_pairs_required')
    used = set(); seen = set()
    for pair in better_worse_train:
        require(type(pair) in (tuple, list) and len(pair) == 2
                and all(type(x) is str and x in train_codes for x in pair) and pair[0] != pair[1], 'tfidf_pair_schema')
        key = tuple(sorted(pair))
        require(key not in seen, 'tfidf_duplicate_unordered_train_pair')
        seen.add(key); used.update(pair)
    require(used == set(train_codes), 'tfidf_extra_nontraining_endpoints')
    ids = sorted(used); positions = {k: i for i, k in enumerate(ids)}
    # Caller order is not a hyperparameter: canonical pair order for all fits.
    pairs = sorted((tuple(pair) for pair in better_worse_train), key=lambda p: tuple(sorted(p)))
    start = time.monotonic()
    vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5), max_features=30000,
        min_df=3, sublinear_tf=True, dtype=np.float64)
    vectorizer.fit([train_codes[k][:20000] for k in ids])
    x = vectorizer.transform([train_codes[k][:20000] for k in ids]).tocsr()
    d = x[[positions[a] for a, b in pairs]]-x[[positions[b] for a, b in pairs]]
    fit_x = sparse.vstack((d, -d), format='csr')
    fit_y = np.concatenate((np.ones(len(pairs), dtype=np.int8), np.zeros(len(pairs), dtype=np.int8)))
    model = LogisticRegression(C=.5, max_iter=1500, solver='lbfgs', random_state=0).fit(fit_x, fit_y)
    elapsed = time.monotonic()-start
    require(int(model.n_iter_[0]) < 1500 and np.isfinite(model.coef_).all()
            and np.isfinite(model.intercept_).all(), 'tfidf_convergence_or_finite_failure')
    state = fingerprint(vectorizer, model)
    receipt = {'baseline': 'fixed-char-wb-3-5-tfidf-lr', 'train_endpoints': len(ids), 'train_pairs': len(pairs),
        'fit_rows_with_sign_symmetry': 2*len(pairs), 'features': len(vectorizer.vocabulary_),
        'initialization_seconds': elapsed, 'iterations': int(model.n_iter_[0]),
        'runtime': {'numpy': np.__version__, 'scipy': scipy.__version__, 'sklearn': sklearn.__version__},
        'state_sha256': state, 'dev_or_test_fit_inputs': False, 'state_hash_seconds_included': False,
        'pair_order': 'unordered-endpoint-lexicographic', 'source_qualification_verified_here': False}
    return FittedFixedTfidf(vectorizer, model, state, receipt)
