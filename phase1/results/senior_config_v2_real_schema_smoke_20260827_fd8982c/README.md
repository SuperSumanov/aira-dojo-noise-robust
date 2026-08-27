# Real dojo-config schema compatibility smoke

Historical schema-only compatibility check for the verified config-v2 producer hook. The 20 inputs
were frozen by file metadata before contents were read. Every raw config was credential-scanned
before JSON parsing; no adjacent environment, archive, journal, grade, outcome, prediction or pair
file was opened.

- configs: 20;
- candidate/reference row and canonical-byte equality: 20/20;
- distinct tasks/clients/solver fingerprints/strata: 7/2/2/9;
- forbidden open/openat hits: 0;
- sidecars before/after/written: 0/0/0;
- canonical rows SHA-256: `fd8982cf75099f71b73d1d5b2ad3e955a89d81efbae941e94705981216ed9e5e`;
- remote formal root: `/research/d7/spc/yzyang4/config-v2-producer-hook/real_config_smoke_65896b6_v1`;
- remote `SHA256SUMS` hash: `80c8ab4b9ef5c23693aad00c7db75e81d81fd18f7339f65d6dff67e86003c47e`.

Status is `REAL_CONFIG_SCHEMA_COMPAT_PASS_HISTORICAL_ONLY_NOT_PROVENANCE`.
