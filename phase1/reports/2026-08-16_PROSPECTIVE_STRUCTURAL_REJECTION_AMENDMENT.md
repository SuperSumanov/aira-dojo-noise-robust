# Prospective structural rejection amendment

Date: 2026-08-16 (Asia/Hong_Kong)

Status: outcome-blind post-failure operational amendment; not a preregistered scientific change.

## Trigger

The frozen production runner stopped fail-closed on
`0814/tweet-sentiment-extraction-8seeds.tar.gz` because the archive journals did not
identify exactly one competition. This archive sorted before five later, structurally
valid archives and therefore blocked append-only intake progress.

The same outcome-blind structural precheck later found that
`0815/text-normalization-challenge-russian-language-8seeds.tar.gz` has the identical
failure mode. It would otherwise become a second fail-closed blocker when its fixed
six-hour stability gate elapsed.

## Credential-first diagnosis

Only checkpoint journals selected by the existing credential-first archive reader were
examined. No environment member, score outcome, label vault, or frozen evaluation label
was read. The bound diagnostic receipt records:

- archive SHA-256
  `b63d223a5efacffaf0797a257d2197315292b5433c9c3d05c2ea71cf02c386ec`;
- 8 checkpoint journals and 8 discovered run roots;
- zero competition IDs and zero rows carrying a competition ID in every journal;
- `labels_or_outcomes_read=false`.

The receipt is
`phase1/results/prospective_structural_rejection_20260816/diagnostic_receipt.json`,
SHA-256 `d69cf9922318aa95142c596a15ea95d232f3f05e192e4e2fc5dc1c38bf2cac8f`.

The second bound receipt records archive SHA-256
`1de64423a081a13688f2413938be30b64b64d8ea77b1cf5a0a3b41237180da49`, 8 checkpoint
journals, and zero competition IDs in all 8. It is
`phase1/results/prospective_structural_rejection_20260816/diagnostic_receipt_text_normalization_0815.json`,
SHA-256 `39ab9eebc926059137890ccd22ab5ed62c5809c7a30b46491c6878fef83cfa35`.

## Amendment

The control runner may skip only an archive listed in an immutable rejection registry
whose path, size, mtime, full archive SHA-256, diagnostic receipt SHA-256, and fixed
reason code all match. A rejected archive cannot be baseline or committed. Any source
change, disappearance, registry mutation, content-hash mismatch, or binding conflict
fails closed.

No task is inferred from the filename. The malformed archive creates no intake, score,
accumulator, or scientific transaction. It remains available for a separately declared
schema-repair extension or a corrected export from the data producer.

The initial one-entry registry remains immutable at
`phase1/results/prospective_structural_rejection_20260816/structural_rejections.json`,
SHA-256 `d32cd70b7c755a8ad340cf376fd88f54ca1bea0a50cffbc5fa4cb58bc97ffb01`.
The second rejection is held in a separate immutable append registry at
`phase1/results/prospective_structural_rejection_20260816/structural_rejections_0815.json`,
SHA-256 `64e009d3ff1460101b84ff269e12d437ae95a4b0df27fe5a904dc259e09555c2`.
The control runner verifies and applies both registries in order, preserving the
original registry binding on the first rejected archive instead of mutating it.

## Frozen scientific path

The amendment changes only archive scheduling/control. Valid archives still execute the
unchanged intake, scorer, registry validator, and accumulator from scientific commit
`90842c49dbd73d41d405a5ecdad2224ee447b375`. The control commit and scientific commit
are both verified exact-clean and recorded separately by the recovery monitor.

Resources for recovery: CPU only; GPU 0; API 0. The prospective score-channel run gate,
estimand, parent selector, replay matrix, and outcome-blindness contract are unchanged.
