# Strict-future continuous intake monitor activation

Status: `ACTIVE_OUTCOME_BLIND`. Control commit
`c06222fc00a3af898c5637fdb74cff85505a6505` adds only the continuous launcher; the fixed scientific intake remains
`90842c49dbd73d41d405a5ecdad2224ee447b375`. The launcher is bound to every existing structural-rejection registry
through 0819, including the Plant registry SHA-256
`0dc58a4f2b2770f615b4ebf6d077c25ec7866d0f0ad72a2cc2f312d8d4f1d503`.

The committed launcher and the cluster checkout have identical SHA-256
`79f7f40ab5a2a030e103bc374f368efe64498fb1b96dd0a790dc66c6d9c34138`; bash syntax and 19 focused runner/registry
tests pass. It polls every 300 seconds for at most 145 polls. An archive must have age at least 21,600 seconds, at
least three observations, at least 300 seconds between observations, and at least 600 seconds of stable span. Intake
remains credential-first and append-only; env/live-event members, labels, scores, and outcomes are not read. Any
unknown structural or identity condition stops the monitor fail-closed.

The activation smoke and the first two live polls are identical:
`archives=183, baseline=128, ready=0, rejected=6, transactions=49, outcomes_read=false`. The copied smoke receipt has
local/remote SHA-256 `ce26053b619e46a9c3f85fca02a15a5051cc7eb14b92694735aa5d018c06f4ff`.

The live process started as PID `1271112`; its log is
`/research/d7/spc/yzyang4/prospective_decision_v1/logs/continuous_intake_monitor_20260821.log`. CPU-only,
GPU/API/base-LLM update=0. A committed intake advances the append-only `LATEST` pointer only after the unchanged
transaction checks; the already active transition-future monitor then appends frozen predictions without opening
outcomes.
