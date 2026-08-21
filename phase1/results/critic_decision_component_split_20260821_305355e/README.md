# Critic decision pair-component split

Formal outcome-free support result for the clean direct-decision scaling input.

- Status: `COMPONENT_SPLIT_ELIGIBLE_FOR_G0_PROPOSAL`.
- Source: `305355efacadbfbad493929cba3ff9e27bd6b5a3`; senior data: `baf6bddefe62b769b2fab699ff5805dd627dc69f`.
- Fixed outer train/test: 5,240 / 931 pairs.
- Component split train/dev/test: 4,689 / 551 / 931; dropped train pairs: 0.
- Dev Draft/Improve: 294 / 257; 25 tasks; dominant share: `0.147005444646098`.
- Pair graph: 168 components; 41 dev components; train/dev runs: 430 / 81.
- Train/dev/test pair, Card, and physical-run overlap: all 0.
- Producer ×2, independent verifier ×2, gate ×2: byte-identical; focused tests 10/10.
- GPU/API/model fit/model download/prospective-vault reads: all 0.
- Remote immutable bundle SHA-256: `880dbe92607818fbeefd326ed2b0e48607523faec3ccd3722a167388062551b9`.

This result fixes a split-integrity problem caused by cross-run Draft edges. It contains no model accuracy and only makes the
pre-registered G0 engineering calibration eligible for an approval proposal.
