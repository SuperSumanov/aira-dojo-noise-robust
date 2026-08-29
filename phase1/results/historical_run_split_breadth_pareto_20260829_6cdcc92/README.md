# Historical Run-Split Breadth Pareto Falsification

This package records the authoritative fresh formal run from control commit
`6cdcc928b3b654a8c7df31999cc3e332bccb0269`.

- Classification: `POSTREADOUT_RUN_SPLIT_BREADTH_PARETO_DOES_NOT_SURVIVE`
- Result SHA-256: `f1d8054ccc3e0d50f77a3ff4be29480f99ab0dbc51a6e1e510853da63c06e042`
- Independent verification SHA-256: `9025f2e5f3254421a6e1015ef4218fb60cec6ce6c5723307863c505c403f991b`
- Remote formal manifest: `223549d32214ab32993d314e9b1d7b63b16ea42bbcb51f532047f04e42df5d77`
- Focused/full tests: `37/1588 passed` (`47 warnings`)

Producer A/B were byte-identical under different Python hash seeds. Two runs of the
non-importing verifier independently reconstructed every aggregate field exactly.
Both folds passed support, but fold0 missed the frozen integrated and pointwise yield
noninferiority gates; fold1 passed every Pareto gate. This is post-readout internal
falsification, not external confirmation.

The four zero-length scanner receipts certify no forbidden prospective opens, network
calls, credential-bearing filenames, or credential values. No GPU, API, model fit, or
base-model update was used.
