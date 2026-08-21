# Component-split char-TFIDF baseline

Fixed same-pool CPU baseline for clean direct-decision Qwen scaling.

- Status: `BASELINE_VALID_AND_INDEPENDENTLY_VERIFIED`.
- Source: `a6075d15722a08c76d2d316a19aff19ac91d6dea`; senior data: `baf6bddefe62b769b2fab699ff5805dd627dc69f`.
- Train/dev/test: 4,689 / 551 / 931 pairs, with zero pair/Card/run overlap.
- Test merged: 532/931 = `0.5714285714285714`; task macro `0.5757982662586206`.
- Test task-clustered CI: `[0.5066135214563272,0.6409030224715225]`; parent-clustered CI: `[0.5322425162766734,0.6111639404566828]`.
- Test Draft/Improve: `0.5796178343949044` / `0.5672609400324149`.
- Dev merged: `0.604355716878403`; the 3.29 pp dev--test gap remains an explicit warning.
- Producer ×2 and independent full-refit verifier ×2 are byte-identical; all numeric differences are 0.0; tests 3/3.
- GPU/API/model download/base-agent update/prospective-vault reads: all 0.
- Remote bundle SHA-256: `b3db165f86b44ab2264bf0aa78424ac2d9e05d2222a48c5f9927196824d6514d`.

The first formal attempt failed before emitting scientific outputs because a classifier intercept was incorrectly included in a
pair margin. The corrected margin is `coef·(x_better-x_worse)` and has exact antisymmetry.
