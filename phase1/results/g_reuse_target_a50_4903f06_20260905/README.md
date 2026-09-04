# G-reuse target-A50 development result

The frozen post-0L28 development gate is **not supported**. TargetA50 uses 99.16% of its
task-wise token budget and improves the directly optimized pair-weighted target variance on
28/28 tasks relative to spectral50 (25 strict), without task concentration. However, its
relative reductions are only `0.007764850748195218` versus spectral50 and
`0.02251392474746483/0.023035926141722785` versus cheapest50/hash50. These miss the frozen
1% and 3% minimum effect sizes. No threshold or objective may be changed to rescue it.

All other gates pass: task-macro mean is lower than all three controls, pooled p90 is no
higher, task breadth and concentration pass, and full-versus-basis remains a valid analytic
positive control. This is useful route selection rather than a positive headline: selector
choice is a modest second-order factor, while the full G-reuse supervision organization
remains the primary effect hypothesis.

Formal v2 is bound to commit `4903f068fce66ea6b70a8dbb75c68fc8f37706a2` and canonical
protocol SHA `ffd04c96b0433cdf917798e6169d79b0341c19a9846025311c1d3038b237f448`.
Producer A/B and independent grounded verifier A/B are byte-exact; 654 numeric values agree
within `2.1316282072803006e-14`; all 28 focused tests and 46 manifest entries pass, with zero
stderr. The first formal root stopped in pytest before data readout because one protocol JSON
was omitted from the export and is retained.

This is deterministic historical structural development. It uses no real orientation,
protected cohort, GPU, paid API, neural model, or model fit, and is not evidence of critic
accuracy, scaling, calibration, or search utility.
