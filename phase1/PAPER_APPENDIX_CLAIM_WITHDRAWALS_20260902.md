# Appendix: Claim withdrawals and scope corrections

> Paper-ready draft, 2026-09-02. This table is an audit artifact, not an
> additional experiment. It records material claims that were retracted,
> killed, narrowed, or deprived of provenance during benchmark development.
> Immutable historical artifacts remain available for audit but are not
> silently promoted back into the current evidence set.

## A. Status vocabulary

- **Retracted result**: the earlier numerical or directional conclusion is no
  longer admissible.
- **Scope correction**: the observation remains valid only for a narrower
  population or estimand.
- **Hypothesis kill**: a result-valid preregistered test failed its positive
  gate; post-hoc rescue is prohibited.
- **Provenance withdrawal**: the underlying arithmetic may be reproducible,
  but the artifact violated its declared information-access contract.
- **Novelty withdrawal**: prior work closes the broad novelty wording; only a
  narrower, directly checkable distinction remains.
- **Evidence-dedup correction**: a valid reconstruction was initially counted
  as an independent finding despite overlapping prior evidence.

## B. Material claim ledger

| ID | Type | Earlier claim or interpretation | Why it was withdrawn or narrowed | Current admissible statement | Reuse rule |
|---|---|---|---|---|---|
| W01 | Retracted result | Fragment-split L1 accuracy around 0.828 represented generalization to held-out decisions. | The split shared physical runs between train and test; the run-clean rerun was 0.6493. | Run identity is a mandatory split unit, and the earlier number is evidence of leakage sensitivity only. | Never use 0.828 as predictor performance. |
| W02 | Scope correction | The released rows represented complete source choice sets. | A results-blind, preregistered completeness audit found incomplete source retention even though retained rows were valid direct siblings. | The release unit is a provenance-bound **labeled sibling fragment**; source-opportunity identity and missingness registries are separate assets. | Never call the historical resource choice-set-faithful or interpret fragment utility as full-choice-set utility. |
| W03 | Retracted result | K≥1 lookahead was the reward model's unique advantage. | The advantage did not reproduce on the run-clean decision set; the clean comparison tied. | Descendant-budget views are historical sensitivity resources, not evidence that lookahead improves prediction or search. | Do not restore K≥1 as a method line or rescue another failed primary. |
| W04 | Hypothesis kill | A pristine external score would rank short-budget candidates better than keyed self-report. | The complete 320/320 replay had too little strict common support; all preregistered directional and inference gates failed. | The valid finding is a 120-second **observability cliff**: external scores were rarely finite, so channel superiority was not identified. | No parser, cap, subset, or available-case rescue. |
| W05 | Hypothesis kill | A prompt-level progressive artifact contract would improve early submissions. | The frozen independent-verifier contract was invalid as written; the schema-only repair reproduced a quality kill with no coverage gain and worse full validity. | The failed intervention is retained as an audited negative development result. | Do not retune the prompt, tasks, or thresholds on the same cohort. |
| W06 | Retracted result | Critic inference was roughly seven million times cheaper than execution. | The ratio was an arithmetic error; later single-shot timings also lacked repetition and hardware binding. | Cost claims use a dedicated deployment attestation with initialization/query separation, repeated measurements, and an execution reference. | Never cite either old ratio or combine it post hoc with old accuracy. |
| W07 | Provenance withdrawal | A pre-closure coverage matrix satisfied strict zero prediction-value access. | Its code opened prediction-pair files and aggregated prediction-derived fields while attesting that no such aggregation occurred. | Only receipt-certified exact common support, reconstructed without opening pair values, remains admissible. | Old orientation, tie, activation, eligibility, and prediction-distribution aggregates cannot migrate forward. |
| W08 | Provenance withdrawal | The original task-balance guard and forward guard were structure-only evidence. | Both depended on the withdrawn value-reading matrix. | A separately frozen structural-only chain re-established the structural arithmetic but not the old provenance. | Numerical agreement does not retroactively repair W07/W08. |
| W09 | Provenance withdrawal | Source-choice S2 v1 was safe after explicit provenance fields were removed. | Operator capitalization exactly recovered a post-selection journal-recovery proxy. | The v1 model view is blocked; only a newly normalized, independently verified successor could be used. | Never train, score, or release the v1 model view. |
| W10 | Scope correction | Reaching 1,500 structural pairs meant the prospective confirmation set was almost ready to unseal. | The registered stopping population is chronological first-960 eligible physical runs plus an independent accrual-closure receipt; the pair count is only a support gate. | Prediction escrow and structural monitoring continue outcome-blind until both population and closure conditions hold. | No early unsealing based on pairs, tasks, or an intermediate snapshot. |
| W11 | Scope correction | Existing 4B/8B checkpoints could provide a frozen decision result. | The old decision test and descendant-budget files were the same 2,087-row multiset, outer test was repeatedly evaluated, and some runs were incomplete or directionally misconfigured. | Historical size scaling is exploratory; confirmation requires future exact-stratum provenance, dev-only checkpoint selection, and a fresh untouched cohort. | Do not locate or score the old checkpoints, even for inference only. |
| W12 | Evidence-dedup correction | The support-floor audit was a new independent positive result. | Its prior support totals and distribution summaries had already been published by the archive-granularity audit on the same snapshot. | It remains an independent reconstruction plus current-window lineage, and is explicitly non-distinct evidence. | Derived certificates and reconstructions cannot increase the independent-claim count. |
| W13 | Novelty withdrawal | NAS-style agent predictors, graph/multi-view encoders, or execution-saving value guidance were broad method novelties. | Direct and adjacent work already covers workflow predictors, graph/code/prompt models, reward-model benchmarks, and value-guided agent search. | The defensible contribution is the MLE-specific measurement package: physical-run-clean sibling fragments, continuous hidden-score gaps, cost/noise/missingness accounting, and sealed temporal confirmation. | Avoid first/only language; state itemized differences against direct baselines. |
| W14 | Retracted result | A cross-generator collapse had been observed. | The generator configuration was wrong: batches labeled as different generators were actually produced by the same provider. | Cross-generator transport remains insufficiently measured. | Do not cite the old collapse or infer provider robustness from it. |
| W15 | Scope correction | A single high-leverage temporal drop established that pair-weight distortion was robust across arrivals. | The drop was real but one arrival could dominate its magnitude; later trajectories separated run balance from pair balance. | Report the full outcome-blind trajectory and distinguish run-level task balance from sibling-pair weighting. | Do not call one prefix change a general or causal law. |

## C. What remains in the current paper

The current manuscript therefore makes four narrower commitments:

1. historical predictor results are development evidence unless independently
   confirmed on the sealed chronological cohort;
2. the benchmark unit is a labeled sibling fragment, not a complete choice set;
3. every table reports its support population, weighting rule, coverage, and
   information-availability point; and
4. claim provenance is append-only: a corrected successor can replace a result
   for present use, but cannot rewrite the history of the superseded artifact.

## D. Internal evidence routing (remove paths before submission)

- W01, W03, W14: `REVIEW_PACKET.md` section 6 and
  `CURRENT_DIRECTION.md` section 2.
- W02: `CURRENT_DIRECTION.md` sections 0U--0W.
- W04: `CURRENT_DIRECTION.md` section 0AJ.
- W05: `CURRENT_DIRECTION.md` section 0AL.
- W06: `CURRENT_DIRECTION.md` section 0BO.
- W07--W08: `CURRENT_DIRECTION.md` sections 0GF--0GG and
  `results/HISTORICAL_WITHDRAWALS_20260826.md`.
- W09: `CURRENT_DIRECTION.md` section 0DL.
- W10: `CURRENT_DIRECTION.md` section 0BK.
- W11: `CURRENT_DIRECTION.md` section 0BW.
- W12: `CURRENT_DIRECTION.md` section 0KW and the Evidence Index v10
  reconstruction record.
- W13: `CURRENT_DIRECTION.md` sections 0BN, 0BV, and 0BY.
- W15: `CURRENT_DIRECTION.md` section 0GQ and Figure 2's locked receipt.
