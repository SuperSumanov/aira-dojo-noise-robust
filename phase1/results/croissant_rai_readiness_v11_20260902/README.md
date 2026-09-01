# Croissant/RAI v11 release-readiness receipt

Status: `INDEPENDENTLY_VERIFIED_CROISSANT_RAI_READINESS_BLOCKED`.

This is a value-free engineering receipt, not a dataset release or legal clearance. The builder consumes only the
existing schema inventory. It verifies ten immutable JSONL resources containing 24,119 rows in total and can derive
their Croissant distributions, record sets, field sources, byte counts, and SHA-256 digests without opening payloads.

The final JSON-LD is intentionally not present. The strict builder refuses to emit it until five publication-time
fields are supplied with non-placeholder values: `license`, `url`, `creator`, `datePublished`, and `contentBaseUrl`.
Competition, provider, content-safety, and institutional/legal gates remain independent blockers.

Machine artifacts:

- `readiness.json`: deterministic producer receipt.
- `verification.json`: independent implementation and hash check.
- producer SHA-256: `5a38dbaf80485c77fa2e034aa55aaafdedfaf03f631a7dfe0793ae690573854a`.
- verifier SHA-256: `780de48f858a055eaa0bc6175e753e5051c51367d22ccfb847a629316c1feb7b`.

Specifications:

- Croissant 1.1: <https://docs.mlcommons.org/croissant/docs/croissant-spec-1.1.html>
- Croissant RAI 1.0: <https://docs.mlcommons.org/croissant/docs/croissant-rai-spec.html>

No prospective resources, labels, outcomes, predictions, candidate identities, GPU, paid API, or model fitting were
used. This receipt does not count as distinct scientific-claim evidence.
