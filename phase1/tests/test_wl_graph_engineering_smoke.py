import numpy as np
from scipy import sparse

from phase1.wl_graph_engineering_smoke import matrix_digest


def test_matrix_digest_binds_shape_indices_and_values() -> None:
    first = sparse.csr_matrix(np.asarray([[0.0, 1.0], [2.0, 0.0]]))
    same = sparse.csr_matrix(np.asarray([[0.0, 1.0], [2.0, 0.0]]))
    changed = sparse.csr_matrix(np.asarray([[0.0, 1.0], [3.0, 0.0]]))
    assert matrix_digest(first) == matrix_digest(same)
    assert matrix_digest(first) != matrix_digest(changed)
