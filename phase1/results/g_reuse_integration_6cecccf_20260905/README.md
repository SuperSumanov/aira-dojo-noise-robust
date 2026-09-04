# Complete G-reuse integration after anonymous join

Classification: `COMPLETE_SOFTWARE_REGRESSION_NOT_MODEL_EFFECT`.

At public head `6cecccfcb5731ff46be560306f5add4e11a76c3a`, the previously verified complete
G-reuse dependency root was copied without caches and overlaid with the four anonymous-join
files from the same head. The resulting root contains the source-package gate, endpoint-score
materializer, prediction-escrow validator, anonymous truth join, effect statistics and their
independent verifiers.

Formal Linux evidence:

- root: `/research/d7/spc/yzyang4/g-reuse-integration/formal-6cecccf-v1`;
- base archive SHA-256: `187adbb476948f4ab97e5668ae441cf7742deac3710dd8c4348781fab0e1de5d`;
- exact four-file overlay SHA-256: `20656f1b5ddcd3150bf0b1493f3a451046a70ccab67f116b4f5193425d27cda3`;
- deterministic 74-file `.py/.json` source archive SHA-256:
  `96b660ebd8eb39f31f7edc102a69f0ea4cb65afe8d89346e5746996575220dd3`;
- source-file manifest SHA-256: `accbd8461482e30f46bb64bad69ded87ea9ce0003e7e2b570131513a37e248c6`;
- A: `134 passed in 20.38s`, stdout SHA-256
  `4dc11d00dfff4d19273e6ec2eaf0c6c7f87caba7c643017b96e90813ae2a71fd`;
- B: `134 passed in 21.48s`, stdout SHA-256
  `86af22e02cfae44c0942f388e4290fe496de94ae832979fa0255a8746cb94d1c`;
- both stderr files are zero bytes.

The initial SSH wait returned before displaying output, but both remote test commands completed
and their finished files were verified afterward. No test was inferred from a running process.

Boundary: this is a synthetic/software regression. It does not authenticate real checkpoints,
authorize a vault, define the still-missing pristine truth-package schema, read prediction/truth
values or establish critic accuracy. GPU jobs, paid API calls, model fits and protected reads are
all zero.
