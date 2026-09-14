# Cheap code feasibility → equal-budget final quality (2026-09-14)

Question: can a frozen, execution-free predictor learned from historical *failed and successful* programs improve final MLE search quality, not merely node AUC, versus uniform and short-code selection?

This is a new development experiment, not the blocked EScope preservation expansion. All EScope seeds/results remain unchanged. Model eligibility was frozen in TASK_CONDITIONED_VALIDITY_PLAN before the two fits: code-only passed, code-plus-task failed. The 157 development nodes were repeatedly used and are not a held-out confirmation set. Three discordant historical pools are only a tiny supporting diagnostic. Static HGB / failure prediction is not itself novel.

## Fixed matrix and contract

- Leaf / Space × new seeds 46,47 × uniform / short_code / learned_validity = 12 searches, four paired triples. Two blocks (one seed each), arm order rotates by task/block. No failed-seed replacement.
- 600 seconds from actual search start, including fixed RF execution and selector loading/inference; 300 seconds per program, 64 steps, existing 100 adapter-attempt ceiling per run. Two generated candidates, exactly one selected for execution (one-candidate bootstrap executes without scoring). Original UCT/debug/analyzer/action delivery unchanged.
- Qwen3-Coder-Flash, Alibaba-only/no fallback, same full-program prompts and refactored RF100/depth12/seed0 start. Neither task identity nor execution feedback is input to the cheap scorer. Short-code uses negative length of the same 30k-character representation as HGB; ties use common randomized priority, not first-slot preference.
- Only selector differs within triples. All arms use the already qualified opt-in FreshContainerInterpreter, original MLE image and RTX3090 gpu28, six CPUs, same mounts/environment. This is a new common execution backend, not an in-flight EScope change or proof of universal backend reliability. No direct causal comparison with old 8B/Jupyter runs.
- Model: code_only.private.joblib SHA256 05379469122879c798f1d2c571eb733956a067dac314050feeb06d3e09c641d1, trained on 2482 historical nodes /138 physical runs, before these seeds. sklearn1.6.1, 28 static features, no refit, no parameter tuning. Scorer records initialization and query time, code hashes and scores privately before execution.
- Two single-GPU 90-minute allocations, maximum 3 GPU·h. Existing cumulative USD10 liability ceiling (conservative original RMB100 authorization), previous 2619 calls / held 7666052390 nanoUSD / settled 6266052390 / two unresolved carried. No cap reset, reserve reduction, alternate key or borrowing others' allocation. Stop if remaining liability cannot admit requests.

## Outcomes and interpretation fixed before execution

All 12 searches and allocations close before effect readout. Primary: original search-visible action-selected externally regraded final submission; secondary: full-iteration endpoint. No choosing best external prefix/node, no outcome-based exclusion.

Technical completion accepts natural completion, 600s supervisor timeout, exact existing SearchBudgetExpired at API admission, or exact RunBudgetError adapter-attempt exhaustion (both resource limits declared here). Infrastructure/model/artifact/unknown-budget faults remain unknown. This definition is for the new study only; EScope's frozen request-cap exclusion is not changed. Invalid submission after technically complete search remains invalid, not missing.

Compare learned to each baseline on every technical pair: validity-first win/loss if only one valid; correctly oriented final score difference if both valid; two invalid ties; technical missing unknown. Report all 12 rows, per-task wins/ties/losses, median and sample SD of comparable score gains, actual time and API spending. With only two seeds/task, do not claim statistical confirmation. Successful investment gate: all four triples technical-complete; learned has net wins over each baseline, no task net losses, at least one strict final-quality/validity win against each. Otherwise no automatic expansion of this recipe.

Independent checks: source/config hashes, equalized triple configs, actual production batch with fake task calls (no API), fixed model reproduction, tied/strict ranking tests, direct selection replay from pre-execution ledgers, original code extraction hash, external numerical regrade, same within-block hardware/image, full billing carry. Unknown issues fail closed. Protected first960/Target300/Target522 remain sealed; no agent model update.
