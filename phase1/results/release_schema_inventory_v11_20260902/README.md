# v11 release schema inventory

This package is a value-free inventory of the current historical v11 card JSONL and all nine v11 decision JSONLs.

- resources: 10
- rows inspected: 24,119 (16,012 cards + 8,107 decision rows)
- card JSON paths: 41
- decision JSON paths: 13 for train/extension and 12 for frozen
- producer/verifier agreement: exact
- focused tests: 3 passed
- prospective resources read: false
- source values, candidate identities, labels, or predictions emitted: false

`schema_inventory.json` SHA-256 is `9a48bde7b97a7174c117abff272f9ff9af4f150876c42fc14c87c932786440eb`.
`verification.json` SHA-256 is `d6725443933e4092f99ee55c54c158beb9c797010800a8e77da9651e0657b1f8`.

The human-facing semantics, availability classes, sensitivity levels, and frozen-`run_id` boundary are documented in
`phase1/SCHEMA_DICTIONARY_DECISION_CORPUS_V11_20260902.md`. This package does not constitute dataset release clearance.
