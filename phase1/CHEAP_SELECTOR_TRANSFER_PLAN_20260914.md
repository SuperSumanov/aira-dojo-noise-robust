# Fixed-selector transfer diagnostic on completed EScope whole-program runs

2026-09-14, frozen before loading any model prediction on these programs. Historical development selected one fixed code-only HGB. The new twelve-search prospective matrix is already fixed and will not be changed based on this auxiliary diagnostic.

Question: on independently collected, fully observed two-candidate pools, does this fixed predictor rank initial execution validity better than choosing shorter code? This is a transfer diagnostic, not a counterfactual search experiment or confirmation.

Source is only completed EScope root `forets-wallclock-20260912-88v5m9dr`, summary SHA `8fd3598f99041d7878daec43ef107da68f2e91a340203a726f3c9e8aff1911cd`. Restrict to all eight planned whole_program runs, not model_module: the latter's frozen interface rejected every observed module and would test parser compliance rather than the original code-validity target. Keep every exclusion count. Primary groups retain original whole-run technical eligibility; show ineligible runs separately.

Use only complete width-two pools in which both original candidates returned and are represented in the journal. Match original id/raw-code hash, exact native `extract_code` execution hash and exit metadata. No debug nodes, bootstrap, unexecuted candidate labels or unknown labels filled as zero. Reject drift/unknown duplicates. De-duplicate identical unordered code pairs within a run for primary statistics and report full counts; report exact/AST/30k-prefix training overlap, omit overlapping pools before prediction. No protected cohorts, raw secrets, new execution/API/model fit.

Fixed model SHA `05379469122879c798f1d2c571eb733956a067dac314050feeb06d3e09c641d1`, input first30000 characters and the frozen static AST features. Compare HGB, negative truncated code length and uniform. Average uniformly among exact score ties. Report each task/run, all discordant-pool wins/losses, run-equal differences and descriptive task-specific run bootstrap intervals (2000 draws, seed20260914). Do not pool Leaf/Space metrics into an accuracy-weighted headline. Report both all observed and de-duplicated pools. Small-run intervals are not precise confirmation.

Sequential execution may have workspace interference. Observed pools are selected by the prior search distribution. Validity ranking is neither final-quality ranking nor saved runtime. No deployment decision, model/seed re-selection or re-fitting follows from this diagnostic.
