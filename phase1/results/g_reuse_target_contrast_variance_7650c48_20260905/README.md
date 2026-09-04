# G-reuse target-local contrast variance

The frozen result is **not supported**. At the same task-wise 50% additional G-token budget,
spectral50 lowers pair-weighted target-local contrast variance by only
`0.014864494581139476` versus cheapest50 and `0.01539058095759116` versus hash50. Both are
below the pre-registered 3% minimum. The pooled p90 is `1.0` for all arms, so spectral50 does
not improve the fixed tail statistic. Its positive task contribution against cheapest50 is
also too concentrated (`0.23784625440737536` versus the 0.20 maximum).

There is descriptive, non-headline breadth: spectral50 is nonworse/strictly better on
`23/22` of 28 tasks versus cheapest50 and `25/24` versus hash50, and its task-macro mean is
lower than both. Full G lowers pair-weighted variance by `0.1412770683302651` and task-macro
variance by `0.17854197512242564` relative to the minimum-token basis. These facts do not
rescue the failed frozen gates.

The exact scientific commit is `7650c48adfaa184a32b0c615ccd106abc586e0be`; canonical
protocol SHA-256 is `203f7bc0a29a9d26fda82759f8bc5c7357d17c09e10729a03db62050baf336ab`.
Producer A/B and independent grounded-Laplacian verifier A/B are each byte-identical; 531
numeric values agree to maximum absolute difference `3.3306690738754696e-16`, with no
non-numeric mismatch or stderr. The 42-entry downloaded integrity reconstruction is exact.

This is an analytic structural mechanism test under unit independent edge noise. It is not
critic accuracy, calibration, scaling, or search utility, and it does not use real pair
orientation or any protected cohort. The 3%, task-breadth, concentration, p90, budget, or
arm rules must not be changed after this result.
