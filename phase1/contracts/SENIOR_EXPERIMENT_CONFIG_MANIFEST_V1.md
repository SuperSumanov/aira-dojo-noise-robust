# Senior experiment-config manifest v1

This future-only overlay binds each already identified physical run to the public execution
configuration needed for exact-stratum and generator-support audits. It composes with
`SENIOR_SOURCE_PROVENANCE_MANIFEST_V1.md`; it does not repeat archive paths, archive hashes, batch
identity, or producer commits, and it never contains code, stdout, grades, predictions, pair
orientation, API endpoints, or credentials.

## Canonical JSONL row

Rows are sorted bytewise by `run_id`; every row has exactly these fields:

```json
{"client":"deepseek-v4-flash","execution_timeout":600,"experiment_stratum_sha256":"<64 lowercase hex>","generator_release":"ds-flash-v2","hardware":"RTX 3090","run_id":"family_seed_7_id_abcd1234__2026-08-08","task":"task-a","time_limit":1200}
```

- `client` is the exact public `solver.operators.draft.llm.client.model_id` copied into Cards. It is
  not a family inferred after outcomes are seen.
- `generator_release` is a producer-declared public release/deployment label frozen before
  outcomes. Literal `unknown` is accepted for provenance completeness but makes
  `interaction_metadata_complete=false`; such rows cannot support a release interaction claim.
- `hardware`, `time_limit`, and `execution_timeout` are copied without coercion from the same
  producer config used to build Cards.
- `experiment_stratum_sha256` is SHA-256 of UTF-8 compact JSON for
  `[task,client,hardware,time_limit,execution_timeout]`. This is byte-compatible with the existing
  exact-stratum pair producer/verifier.
- Every expected run must occur exactly once. `task` must agree with the frozen expected-run and
  source-provenance manifests.

Public string values use a narrow printable allowlist and the whole file is credential-scanned
before JSON parsing. A model identifier that embeds a URL query, secret, or private endpoint is
invalid; use a public model/release label instead.

## Independent composition command

First obtain a verified source-provenance receipt with the existing validator. Then run:

```bash
python phase1/validate_senior_experiment_config_manifest.py \
  --expected-runs <frozen-run-manifest.jsonl> \
  --expect-runs-sha256 <sha256> \
  --source-provenance <producer-source-provenance.jsonl> \
  --expect-source-provenance-sha256 <sha256> \
  --source-receipt <verified-source-receipt.json> \
  --expect-source-receipt-sha256 <sha256> \
  --config-provenance <producer-config-provenance.jsonl> \
  --expect-config-provenance-sha256 <sha256> \
  --output <new-config-receipt.json>
```

The validator independently recomputes the source-manifest mapping hash, verifies that the supplied
source receipt binds the same frozen inputs, checks exact run coverage and every stratum hash, and
emits a joined mapping hash plus outcome-blind support counts.

`CONFIG_PROVENANCE_VERIFIED` proves only the identity/config join. It does not prove balanced
cross-generator support, authorize model fitting, or validate a scientific effect. A separate
outcome-blind support gate must pass before freezing any capability-by-generator matrix.

## Migration boundary

This overlay is not added to the active 33/300 score-channel cohort and cannot be backfilled after
its truth is opened. It is for a separately frozen future critic-capability cohort (or another
future-only producer contract) whose manifest exists before model outcomes are inspected.
