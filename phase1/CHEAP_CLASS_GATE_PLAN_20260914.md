# Fixed classifier gate instead of continuous-proxy maximization

2026-09-14, before this gate's evaluation and before current46/47 outcomes. Motivated by the three observed both-valid quality losses, this is an explicitly **post-hoc new hypothesis**, not a rewrite of earlier results.

Keep the previously frozen model unchanged. Map its two probabilities to positive-class flags using the canonical binary classifier decision `p > 0.5`. Uniformly select among the positives when any are present; if both flags equal (including neither positive), select uniformly among both candidates. Exactly one rule; no threshold sweep, calibration fit, source selection, model refit, task-specific override, or new features. Uniform tie expectation offline; common-priority randomization if later deployed.

Question: does treating predicted feasibility as an admissibility category retain initial-validity gains while avoiding continuous-proxy overoptimization among alternatives? Threshold0.5 is a classifier decision, not a claim that probabilities are calibrated or that selected programs are safe.

CPU assay uses exactly the same four closed-source candidate populations and hashes as the completed transfer/missingness diagnostics, including all unknown pairs. Report every task/protocol: known discordant validity, run-equal sharp missing-label bounds against uniform/short/full/size-only, and the already independently graded three both-valid pairs' quality deltas. Unknown remains unknown. Do not access current46/47 outcomes or change its gate.

For consideration of a separate future E2E development experiment, require (a) no lower complete-case expected validity than short-code overall and strict improvement over uniform, (b) no worse aggregate both-valid quality than continuous ranking, and (c) at least one actual choice-distribution change. These are post-hoc resource-prioritization criteria only, not confirmation or sufficient paper evidence. If it fails, do not tune the threshold on these observations. Any online test requires an explicitly new matrix, complete current closure, unchanged original budget cap/unknown reserves, ordinary preflight and frozen whole-matrix readout; do not call it automatic expansion of the current continuous-ranking recipe.

0GPU/0API/0fits for this assay. Binary gating, selective prediction and constrained search are established ideas; novelty, if any, would need a demonstrated MLE mechanism and actual equal-budget quality benefit, not the threshold operation itself.
