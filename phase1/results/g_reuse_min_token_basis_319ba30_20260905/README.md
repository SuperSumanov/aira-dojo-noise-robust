# Minimum-token G-reuse comparison basis

Date: 2026-09-05 Hong Kong. Result-before source commit:
`319ba302015491a638c0af5bfec3f7ee2a63d442`.

## Frozen construction and gates

Initialize union-find with all L edges. Sort the 2745 record-consistent G-reuse edges
by the sum of their two cached valid-token lengths, using sorted endpoint IDs only as
a deterministic tie-break. Add an edge exactly when it joins two current components.

The three frozen gates were: per-task rank gain exactly matches all 2745 edges; total
rank gain remains exactly 790; G-stage valid tokens fall by at least 60%.

## Exact result

- basis/full G pairs: 790/2745;
- pair reduction: `0.7122040072859745`;
- basis/full rank gain: 790/790;
- tasks with exact rank gain: 28/28;
- basis/full G valid tokens: 5,773,896 / 19,601,875;
- G-token reduction: `0.7054416478015496`;
- basis/full G+L valid tokens: 37,961,638 / 51,789,617;
- all three gates: PASS;
- status: `G_REUSE_MIN_TOKEN_BASIS_STRUCTURAL_COST_SUPPORTED`.

Descriptive exposure statistics, not gates:

- endpoint visits: 1,580 vs 5,490;
- unique G-stage endpoints: 1,258 vs 2,022;
- maximum endpoint degree: 6 vs 14;
- top-decile endpoint-visit share: `0.20822784810126582` vs
  `0.31785063752276865`.

Producer A/B and independent verifier A/B returned zero with empty stderr and exact
aggregate agreement. Durations were 49.42, 41.83, 43.43, and 45.34 seconds. Producer
receipt SHA-256 is `ac92bc10c856ccea6c3cd864fd7941eecc841655d6cd0d18a1dc0dccfd637005`.
Downloaded archive SHA-256 is
`8a4e551186a91b96175588d6d8a6843c99d3c0626c08147288d97cce2cc36523`.
Credential scan passed; GPU jobs, API calls, and model fits were zero.

The first local manifest command contained PowerShell spacing errors and therefore
did not verify the manifest despite later checks continuing. It is not counted as a
pass. A corrected command with terminating errors then verified every manifest entry.

## Claim boundary

Kruskal connectivity preservation is standard graph theory. The empirical contribution
here is the measured token reduction on this candidate, not a novel graph algorithm.
Cycle edges may carry useful robustness or optimization signal, so structural equality
does not imply equal model effect. No selected identities or training pool were emitted.
Historical source/config/experiment closure, actual G0 cost, and explicit GPU approval
remain required before this basis can enter a model comparison.
