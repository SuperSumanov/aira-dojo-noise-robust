# Heterogeneous run-OOF v11 result

Protocol `heterogeneous_oof_v11_discovery_v1` ran at commit
`385a5e59e40125e75fab01176f23387c0b5ec53f`. The producer and an independent implementation agree on
`VERIFIED_DISCOVERY_NO_UNLOCK_NO_ENSEMBLE`; `frozen_read=false`.

The strongest arm was `char_tfidf_lr`: pair accuracy 0.5219329110954727, complete-parent top-1
0.4674634794156706, and parent-equal gap utility 0.5310468507329235. Its pair run/task macro 95% CIs were
[0.5531680059666031, 0.6197497050943016] and [0.5100268056827233, 0.6007455714540130], respectively,
showing weak pre-execution signal. It nevertheless failed the frozen primary gate and the nested-ensemble
authorization gate because its decision utility was not task-robust and task consistency was only 11/20.

Files:

- `summary.json`: producer summary, SHA-256
  `2b804642e420b1313e10bc10f653db7b32bce25bbd8419e9918f78527e740859`;
- `independent_verify.json`: independently refitted verification;
- `oof_predictions.csv`: all same-pool OOF predictions, SHA-256
  `fc57c03a1c96ce7be19a4db764a539082258fe4c69a2ec8653b41ff85626cb45`;
- `full_artifacts.tar.gz`: preregistration, preflight, smoke, checkpoints, predictions, producer and verifier,
  SHA-256 `a96e41b9f72c56c49b9af60ed1eead0d1b6daf21efe365a0f1a732590fc5eae4`, 1,119,807 bytes.

The remote artifact manifest verified all 30 payload files; high-confidence secret matches and suspicious
artifact filenames were both zero before transport.
