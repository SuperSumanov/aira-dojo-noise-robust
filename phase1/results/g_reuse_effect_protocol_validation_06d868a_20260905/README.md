# G-reuse effect protocol: independent Linux validation

The exact scientific commit `06d868a1a43b2f1b86254790c4de21fafefb4903` was
exported as an explicit dependency-closed, data-free archive. The valid archive SHA-256 is
`00f2a417127d413ac4226b068f6533a713660e3077fb1f193daae16cbeedfd78`; it contains no
Git LFS pointer. On the independent Linux environment (Python 3.11.15, pytest 7.4.3), the
four targeted protocol/execution/G0 regression files produced `118 passed, 1 skipped` in
0.99 seconds. The skipped test is the existing explicit opt-in CPU torch autograd check.

Two broader archive attempts stopped on already documented unavailable historical Git LFS
objects before tests. A first narrow dependency closure then produced `117 passed, 1 skipped,
1 failed`; its only failure was a missing exported source module. The final archive added that
single source dependency without changing the scientific commit or tests. All attempts are
recorded in `validation_receipt.json`.

This result validates software and the frozen protocol only. It does not authorize training,
does not read protected cohorts, and is not evidence for model effect, accuracy, scaling, or
search utility.
