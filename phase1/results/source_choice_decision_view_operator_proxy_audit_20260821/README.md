# Source Choice Decision View v1 operator-proxy audit

Status: `SOURCE_CHOICE_DECISION_VIEW_V1_MODEL_BLOCKED`.

This was a train-only, pre-model integrity inspection of the immutable S2 v1 release. It was not preregistered
as a predictor experiment and makes no predictive-performance claim. No model was fit; no frozen or extension
winner label, sealed vault, prospective outcome, GPU, or API was used.

## Verified finding

The ostensibly decision-time `operator` field retained a reconstruction artifact:

- train: `Draft` 93 slots / 38 winners; `Improve` 4,949 slots / 2,071 winners; lowercase `improve`
  697 slots / 0 winners;
- frozen: `Draft` 29, `Improve` 1,820, lowercase `improve` 192 slots (winner labels remain unavailable);
- extension: `Draft` 12, `Improve` 225, lowercase `improve` 10 slots (winner labels remain unavailable);
- lowercase `improve` totals 899 candidates across all roles, exactly matching the independently established
  S1v2 census of 899 `journal_recovered` candidates.

Thus v1 removed the explicit `provenance` and `source_journal_sha256` keys but left a lossless case proxy for
the same post-selection provenance. The 697 train proxy-positive candidates are all losers, so any learned or
rule-based score could exploit it. This blocks model use before any benchmark accuracy was computed.

## Other shortcut checks

All candidate arrays are ordered lexicographically by candidate SHA. On 2,109 train groups, exact uniform
expected top-1 is 0.400178014652; first/min-SHA is 0.390232337601 and last/max-SHA is 0.411095305832.
Unique-min-step and unique-max-step accuracies are 0.390232337601 and 0.416311047890. Unique-min/max-code-length
accuracies are 0.397344713134 and 0.401137980085. These are descriptive checks, not multiplicity-adjusted
hypothesis tests, and do not rescue v1.

The 5,739 train slots have 5,739 unique candidate IDs. Seven code hashes repeat, but none crosses a physical
run or task. No candidate ID crosses a group or run.

## Allowed correction

The only permitted v2 change is a schema-level canonicalization of case-insensitive `draft` and `improve` to
the fixed `Draft`/`Improve` enum, with all other values rejected. Group/candidate identities, labels, ordering,
code bytes, step, depth, splits, and cluster metadata must remain unchanged. v2 must be produced twice and
independently verified twice before any train-only OOF is reopened.
