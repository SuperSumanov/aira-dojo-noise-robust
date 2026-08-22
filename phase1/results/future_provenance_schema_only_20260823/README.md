# Future provenance schema-only audit

This audit is outcome-blind. It reads only the 11 accepted `0821-*` intake
`source_provenance.json` sidecars already allowlisted by the future identity protocol. It does not
open archive payloads, journals, code, labels, scores, stdout, submissions, replay outcomes, or
the truth vault, and it prints field names/types rather than field values.

- bound cohort summary SHA-256:
  `780126c257ceae38a830c9d8215fbf7a7ce6776987ba683a967d774d13488600`;
- audit script SHA-256:
  `e293209b7a10002d47d16fee6dfcf2a80b0053e492924f3094d49931f22ff003`;
- two executions were byte-identical;
- output SHA-256:
  `caa59456c864f07770e73fcb4a7fe5565c93bb7519b44b2faa873aafa1905589`;
- inventory: 11 files / 33 run records / 0 parse errors / one schema;
- `client`, `model`, `generator`, `hardware`, `time_limit`, and `execution_timeout` fields: 0/11
  files for every field family.

Decision: the current 33-run score-channel cohort remains valid for its frozen purpose, but it
cannot identify a critic-capability × candidate-generator interaction from its present safe
sidecars. That question needs a separately frozen, credential-safe config-provenance sidecar and
must not be retrofitted into or used to alter the current cohort.

Status: `SCHEMA_ONLY_COMPLETE_CAPABILITY_INTERACTION_UNIDENTIFIABLE`.
