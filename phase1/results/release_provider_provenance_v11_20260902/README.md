# v11 provider-provenance inventory

Status: `PARTIAL_NOT_RELEASE_CLEARED`.

This package binds the v11 release descriptor, ordered 29-batch registry and
manifest, and the historical `generator_versions.json` annotation. The producer
and an independently implemented verifier agree on all batch metadata and
coverage counts. Neither implementation opens a card payload.

Machine-printed result:

- release: 29 immutable batches / 16,012 rows;
- mapped to a provider family: 24 batches / 9,901 rows;
- exact annotated version or model: 23 batches / 9,794 rows;
- DeepSeek version-boundary ambiguous: 1 batch / 107 rows;
- provider-unmapped: 5 batches / 6,111 rows.

The unmapped batches are `cards_senior_0805seq.jsonl`,
`cards_senior_0808.jsonl`, `cards_senior_0809.jsonl`,
`cards_senior_0810.jsonl`, and `cards_senior_0811.jsonl`. Their names and dates
must not be used to guess a provider. Historical producer/account records are
required.

`inventory.json` SHA-256:
`88df63ed0434ba10f4eaa2c9965735c70b61a750026d290372415321834b550a`.

`verification.json` SHA-256:
`66459ae21415dff9a1728442334b460550604818f9b7831220d33b9f6bf62f5b`.

This is release-governance metadata, not scientific claim evidence. It does not
interpret provider terms, establish copyrightability, or authorize a dataset
license.
