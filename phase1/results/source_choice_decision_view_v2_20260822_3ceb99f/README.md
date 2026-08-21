# Source Choice Decision View v2 formal receipt

Status: `SOURCE_CHOICE_DECISION_VIEW_V2_READY`.

Control commit: `3ceb99f8030fb196d2abc388e277b11dbd1bc571`. Completed at
`2026-08-21T16:00:32Z`. Read-only formal directory:
`/research/d7/spc/yzyang4/source-choice-decision-view/3ceb99f-v2`.

## Exact result

- 3,000 groups / 8,027 unique candidates / 23 tasks.
- train/frozen/extension groups: 2,109 / 778 / 113; candidate slots: 5,739 / 2,041 / 247.
- operator canonicalizations: 697 / 192 / 10; output enum counts are train 93 `Draft` + 5,646
  `Improve`, frozen 29 + 2,012, extension 12 + 235; lowercase/unknown outputs=0.
- `provenance` and `source_journal_sha256` removed 8,027 times each; blocked model fields=0.
- train winner fields=2,109; frozen/extension winner fields=0/0; sealed vault not read.
- group/candidate identities, labels, order, complete code bytes, step/depth, roles, and cluster metadata are
  unchanged from the SHA-pinned S1v2 source.

## Output identities

- train model: `e5ca6dc94f59d54fe31d4b1c4e796deef0006f489fd76a05663410d4911aa6e1`
  (106,476,372 bytes; 2,109 rows).
- frozen model: `2e8371c1890bee9c7a33cb04238f94aa130e5114b307a233e21ca5d1af2152df`
  (33,559,335 bytes; 778 rows).
- extension model: `2a6d7c4bf5157e00e5fe59dd6100db23bb7771bfce32f55b93573d1b5d4fdd0b`
  (4,668,637 bytes; 113 rows).
- cluster manifest: `a8f328a3972708e52126157774204647698d2f8b00cc5f7ad06fd8b1d38b4035`
  (1,116,480 bytes; 3,000 rows).
- summary: `3471868051397de128f1a02d43b9762c7ca0034f3753b230aeff0bbaf1bbea1d`;
  view manifest: `6ad5a5625e728830e1db6be1aa82580030c48a5baf38f2f213e7c43929521c03`;
  independent verification: `49bf4333844faa9f9fa6a3dcef591102acce082b8509d1d4b838fa69721cca6a`;
  formal SHA manifest: `c1d2a79ae6366f6eb21e9da664c2834768397a710937ea3f3df991dbf89b4a48`.

## Verification

Producer A/B and independent verifier A/B were byte-identical. Focused tests: `20 passed in 0.23s`.
Full phase1 suite: `706 passed, 25 warnings in 54.92s`. Reproducibility diffs, stderr files, forbidden
scientific/vault path hits, credential filename hits, credential content hits, before/after worktree drift,
and writable formal files were all zero.

This receipt proves input integrity only. It contains no predictor performance, frozen score, prospective
effect, search utility, or algorithmic novelty claim. S2 v1 remains blocked.
