# Senior experiment-config manifest v2

Version 2 is the future-only, prompt-sensitive successor to v1.  Version 1 remains a valid
identity/public-runtime provenance overlay, but its stratum hash covers only task, client,
hardware, and time limits.  It cannot distinguish the 2026-08-24 system/user prompt split or any
other resolved solver change and therefore must not support an exact producer-stratum claim.

## Outcome-before producer export

Run this against the unarchived producer-side `dojo_config.json`, after the run config is resolved
but before archive outcomes are used by any analysis:

```bash
python phase1/senior_experiment_config_v2.py \
  --dojo-config <run-directory>/dojo_config.json \
  --task <exact-task> \
  --generator-release <public-outcome-before-release-label-or-unknown> \
  --hardware <public-hardware-label> \
  --output <fresh-run-sidecar.jsonl>
```

The exporter refuses symlinks, existing output, invalid JSON, credential-shaped bytes, malformed
run identity, mixed operator clients, nonpositive limits, and nonpublic identifiers.  It does not
read `env_variables.json`; hardware is supplied as an explicit public label so raw producer
credentials are never loaded by this tool.  Consumer-side code must never run this exporter by
opening an archive that has not first been independently redacted.

## Atomic multi-seed batch export

For a normal 4/8-seed task archive, prefer the batch wrapper and pass every unarchived config path
explicitly:

```bash
python phase1/senior_experiment_config_batch_v2.py \
  --dojo-config <run-1>/dojo_config.json \
  --dojo-config <run-2>/dojo_config.json \
  --dojo-config <run-N>/dojo_config.json \
  --task <exact-task> \
  --generator-release <public-outcome-before-release-label-or-unknown> \
  --hardware <public-hardware-label> \
  --output <archive-basename>.config_v2.jsonl
```

The wrapper validates all rows in memory before creating the output, rejects duplicate physical
run IDs, sorts rows bytewise by `run_id`, writes with an exclusive temporary file plus `fsync` and
atomic replace, and prints the complete manifest SHA-256.  Any bad config makes the entire command
fail without a partial sidecar.  Argument order cannot change the bytes.

The resulting `.config_v2.jsonl` should be uploaded as an immutable sibling of the corresponding
archive, before anyone uses archive outcomes.  Do not place raw configs, environment dumps, or the
resolved solver projection in this public sidecar.  The batch wrapper does not infer task,
hardware, release, or config paths and does not open tar files.

## Prompt-sensitive solver projection

`resolved_solver_config_sha256` is SHA-256 of canonical compact JSON for the complete resolved
`solver` object after removing exactly two run-specific path fields:

- `exp_name`;
- `checkpoint_path`.

Everything else remains in the projection, including all static system prompts, user prompt
templates, operator settings, client configs, search limits, retry policy, memory policy, and
available packages.  A prompt or solver change must therefore change the hash, while changing
only a run output name/path must not.  The projection bytes are credential-scanned and are never
emitted.  `solver_projection_schema` is fixed to
`resolved-solver-minus-run-paths-v1`; a new projection rule requires a new schema value.

All LLM-bearing operators must expose one identical public model ID.  If clients are intentionally
mixed, this scalar v2 schema is insufficient and export fails rather than silently labeling the run
with the draft client.

## Canonical JSONL row

Rows are sorted bytewise by `run_id`; each has exactly ten fields:

```json
{"client":"qwen3-coder-flash","execution_timeout":600,"experiment_stratum_sha256":"<64 lowercase hex>","generator_release":"qwen-release-2026-08","hardware":"NVIDIA H200","resolved_solver_config_sha256":"<64 lowercase hex>","run_id":"family_seed_7_id_abcd1234__2026-08-25","solver_projection_schema":"resolved-solver-minus-run-paths-v1","task":"task-a","time_limit":1200}
```

`experiment_stratum_sha256` is independently recomputed from UTF-8 compact JSON for:

```text
[task, client, generator_release, hardware, time_limit, execution_timeout,
 solver_projection_schema, resolved_solver_config_sha256]
```

Numeric JSON types are preserved.  Literal `unknown` is allowed for client, release, or hardware
to preserve provenance, but any such row makes `interaction_metadata_complete=false`.

The config-side hash is not, by itself, a complete producer stratum: source code can change while
the resolved config remains byte-identical.  During consumer validation, each row is therefore
joined to the source manifest's outcome-before `producer_commit`; the receipt counts distinct
`producer_stratum_sha256 = SHA256([producer_commit, experiment_stratum_sha256])` values and binds
their complete joined mapping.  Neither half may be omitted from an exact producer-stratum audit.

## Consumer composition

The source-provenance v1 receipt and frozen expected-run manifest remain mandatory:

```bash
python phase1/validate_senior_experiment_config_manifest_v2.py \
  --expected-runs <frozen-run-manifest.jsonl> \
  --expect-runs-sha256 <sha256> \
  --source-provenance <producer-source-provenance.jsonl> \
  --expect-source-provenance-sha256 <sha256> \
  --source-receipt <verified-source-receipt.json> \
  --expect-source-receipt-sha256 <sha256> \
  --config-provenance <sorted-v2-config-sidecar.jsonl> \
  --expect-config-provenance-sha256 <sha256> \
  --output <fresh-v2-config-receipt.json>
```

`PROMPT_SENSITIVE_CONFIG_PROVENANCE_VERIFIED` proves only exact run/source/config composition.  It
does not prove support balance, predictor accuracy, a prompt effect, scaling, or search utility;
does not authorize model fitting; and cannot be backfilled after outcome inspection.  Historical
0823 archives without an outcome-before v2 sidecar remain usable as natural temporal corpus only,
not as prompt A/B or exact-stratum evidence.
