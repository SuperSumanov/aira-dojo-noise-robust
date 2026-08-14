# Label repeatability attestation v2

Protocol `label_repeatability_attestation_v2` ran from the frozen source commit
`4e3bebe21fb96e356fdc1656bbfe8d5ba748e027`. The clean Linux worktree passed 4 focused tests and all
256 `phase1/tests`. The producer and a verifier that does not import it agree on
`VERIFIED_LABEL_REPEATABILITY_ATTESTATION_V2` and
`INDEPENDENTLY_VERIFIED_LABEL_REPEATABILITY_ATTESTATION_V2`.

This attestation replaces the old unconditional use of `noise_ceiling.py`: that script's node bootstrap did
not use its resampled nodes, and its single-vs-repeat-mean inversion compared non-exchangeable measurements.
The old raw agreement remains a historical descriptive value, but its printed bootstrap interval and the
unqualified `0.9578` ceiling must not be used as release-grade evidence.

## Primary measured quantity

The append-only inputs contain 1,217 rows, 638 finite successful physical regrades, 207 usable cards and 10
tasks. Nine `(card_id, rep)` groups contain multiple successful executions with differing scores; the primary
keeps physical records and the two fixed sensitivity modes retain only the first or last success per metadata
replicate.

The primary comparison uses the original grade and the first successful independent regrade, both single
measurements. Its stratification gap is computed from the remaining regrades, excluding both primary label
measurements. Across 3,017 comparable same-task node pairs:

- raw ordering agreement: `0.9658601259529334`;
- task-macro agreement: `0.9801808283872976`;
- 2,000-draw task-cluster 95% interval: `[0.9438143714671886, 0.9913402891372938]`.

Secondary checks are consistent: original versus repeat mean is `0.9649006622516556` on 3,020 pairs, and first
repeat versus second repeat is `0.9891089108910891` on 3,030 pairs. The original-versus-mean quantity is not
inverted because a single measurement and a mean are not exchangeable.

## Transport to the verified v11 frozen pair sets

| target | pairs | measured-task pair share | transported repeat agreement (task CI) | model-inferred single-label accuracy (task CI) |
|---|---:|---:|---:|---:|
| frozen:b0 | 1,498 | `0.732977303070761` | `0.9134305309964227` (`[0.8353851659068688, 0.9494041168867747]`) | `0.9488254145489123` (`[0.8571329199113228, 0.9682215874512448]`) |
| frozen:b1 | 323 | `0.628482972136223` | `0.8916941736230527` (`[0.7924580822980414, 0.9382365626506495]`) | `0.9361851433192768` (`[0.8211034446900434, 0.9611155025210438]`) |
| frozen:b2 | 265 | `0.6566037735849056` | `0.8824732483674982` (`[0.7674114569612687, 0.9392978659043105]`) | `0.9314651721448394` (`[0.7981120604636813, 0.9611414516818688]`) |

For frozen b0's 1,098 pairs belonging to measured tasks only, transported repeat agreement is
`0.9053834921625754` and model-inferred single-label accuracy is `0.9436065940641354`, with task-cluster
intervals `[0.8222626085748247, 0.9416119061941004]` and
`[0.8425068726562862, 0.9635159677149602]`, respectively.

The model-inferred field is not an empirical predictor ceiling. It requires independent, exchangeable,
symmetric label errors conditional on gap, and the all-pair transport extrapolates a ten-task reference-gap
curve to target tasks without regrades. The direct conclusion is narrower: on measured tasks, label ordering
is highly repeatable and task-cluster uncertainty remains far above the observed run-clean critic accuracy;
label noise alone is therefore not a plausible explanation of the full performance gap. It is not evidence
that all target tasks have the same noise process.

The first/last-per-`(card,rep)` sensitivity changes frozen:b0 transported agreement only from
`0.9134305309964227` to `0.9131214229466382` / `0.9132652862633839`; the primary raw agreement is unchanged.

## Integrity and failure record

- GPU=0 and API calls=0; endpoint code, observations, pair winner orientation and task orientation were not
  read.
- The first launch never found its `/tmp` runner, the second used a nonexistent Git remote, and the third
  selected `/usr/bin/python` without pytest. All stopped before scientific output. The fourth used the project
  `exp` interpreter and completed the frozen run.
- The fourth run completed producer and independent verifier, then its postflight shell stopped because
  `grep` returns 1 on zero matches under `pipefail`. The repair did not rerun either scientific program; it
  scanned the existing output and created the manifest.
- Final suspicious-filename and high-confidence credential-file counts are both zero. The downloaded seven
  payload hashes match `artifact_manifest.sha256` exactly.
- Exact scientific replay is environment-pinned to the recorded Python `3.12.3`. A later Windows Python
  `3.13.4` diagnostic passed every normalized input hash but did not claim verification: Python's changed float
  summation made one `original_vs_repeat_mean` secondary tie differ (3,020 versus 3,019 pairs), while the 3,017
  pair primary count and raw agreement were unchanged; remaining primary transport differences were at roughly
  `1e-16`. No tolerance or post-outcome producer edit was used to turn that run into a pass.
