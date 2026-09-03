# Historical Global→Local source applicability, 2026-09-04

Status: `HISTORICAL_SOURCE_APPLICABILITY_ONLY_EFFECT_BLOCKED`.
Exact executed implementation: `7cd5862746e32a4e435fb592c6af2f93158e4f56`.
Remote: `/tmp/gl-source-applicability-20260904-fivm98/results`.
Producer A/B byte-identical; independent, non-importing set-based verifier A/B byte-identical.
All four children rc=0. The six files in the original `manifest.json` matched after download.
Producer receipt SHA-256: `e34d9f1432fe71bc4c9de8e9074dc47eaf84569f94478e06f1070c778146bb07`.

| Readout | L historical train | G identity-only candidate |
| --- | ---: | ---: |
| Pairs | 4689 | 9392 |
| Endpoints | 4095 | 6698 |
| Grouped run identities | 430 | 428 |
| Tasks | 28 | 28 |
| Pair endpoints with equal recorded config | 4689 | 8977 |
| Pair endpoints with unequal recorded config | 0 | 415 |
| Pairs with unresolved source batch | 365 | 676 |
| Unique / ambiguous / missing run-to-batch joins | 405 / 19 / 6 | 403 / 19 / 6 |

All four recorded config fields are present for all L/G endpoints; within each L-train run they are constant.
That does NOT prove the original generator config. Among uniquely joined pairs, both pools have zero cross-batch
pairs; global cross-batch pairs were not defined as an exclusion rule in this check.

Of 109 known batches represented in L-train, 79 also have runs outside the L-train boundary: 296 inside runs and
121 outside runs. Outside runs were NOT classified into dev/test/unused, so this is neither a measured test leak
nor an experiment-closed split certificate. The old full-corpus S0 remains `IDENTITY_UNAVAILABLE`.

The pre-existing 9392-pair candidate was NOT filtered, repaired or materialized. Its token plans remain execution
feasibility artifacts, not approved training inputs. The frozen v2 and historical development v1 are unchanged.
No labels, outcomes, predictions, accuracy, utility or private identities of first960/Target300/Target522 were opened.
The diagnostic parses the old grouped JSON container but only projects the specified identity/config fields; it
does not inspect code, grade, gap or orientation. It opens no dev/test files or archive payloads. GPU/API/model-fit=0.
The Python audit hook is not an OS sandbox. This is a real data applicability finding, not an effect result.

## Additional pointer-only version check

`pointer_check_initial.json` first checked Cards and the separately named hardware/time-filtered value asset.
`pointer_check_with_batch.json` additionally checks the actual G source, **batch_value_pairs_filtered_runsplit.jsonl**;
these are different datasets and are not substituted for one another. Only Git objects <=256 bytes matching the
strict LFS pointer grammar were opened; no LFS payload was downloaded or read. The small helper is in
`phase1/scripts/check_historical_lfs_bindings_20260904.py`.

The current diagnostic combines old Cards at 92a9651 (OID `5fd24c8e…`) with G derived from ac008af batch-value
(OID `8a01dfb9…`). The Cards pointer at ac008af is instead `5e0f3807…`, and at the unchanged latest senior commit
b8d0951 it is `90ffba2c…`. Thus identity coverage does not establish a version-coherent training bundle. We have NOT
proved that version differences caused all 415 config mismatches; doing so requires the appropriate source binding.
This is not a newly uploaded senior commit. Do not silently switch to the latest Cards, which may mix later cohorts.

## Operational notes

At 2026-09-03 19:17 UTC, intake was live (PID3884166), most recent completed poll8 rc0; 589/960 eligible runs,
306 archives, config-v2=0, closure=false. Senior HEAD remained b8d095180415957aa1bab31fa53ead1bba261c03. G0 12288
remained PENDING/Resources with zero elapsed and limit1:57:00; no new GPU job was submitted. One status-format
command lost its pipe quoting across SSH; retry using a comma-separated field list succeeded without changing the job.

The broad local filename-pattern search accidentally included old Cards JSONL and produced excessive old-content
output. No scientific selection was made from it; subsequent searches were limited to explicit source/report paths.
This is documented in the preregistration rather than claiming that the whole turn never encountered old payloads.
