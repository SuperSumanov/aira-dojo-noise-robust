# TGCA v11 train-only OOF result

正式状态：`VERIFIED_TGCA_DISCOVERY_NO_UNLOCK`。协议、完整数字和解释边界见
`phase1/实验记录/2026-08-14/TGCA_裁决.md`。

本目录保留 producer summary、独立 verifier、OOF scores、图统计、逐任务结果、fit-run inventory、预检与
完整日志。23 MB 的逐边 manifest 和五个 checkpoint 不重复提交；它们由 `artifact_manifest.sha256` 锁定，
保存在完整远端包：

```text
/research/d7/spc/yzyang4/archives/tgca_v11_20260814_2de878d60175_full.tar.gz
size = 6151411 bytes
sha256 = 6652812fc110f19a87b0e8bdf99b6b9d41079d555110142e139d48142e83f175
```

关键本地文件 SHA-256：

```text
summary.json             fefa9ce86554f0e3bcca9cff03427cbf77611b73654ecc4e3a682dbfd0187c83
independent_verify.json  96c4293e1fa19613a36ab1c4b6aca5ce554c8c35076d69a6cdf453225341c010
oof_predictions.csv      40aa8a8f702c30658de18834becc4beaf7242e4eabdb0da9ede3b73efb9f614c
graph_stats.csv           e638a199c48bee6e506671e844c852ba7d3b7e2a3ee0d465159e50e901b6e264
per_task.csv              6b809e754f97aa2090c474c24ebc1d48a0a5079f023fe5cda23cab7a9de55a76
fit_runs.csv              dab3fdd9b71fd03a37b333b90c3313bd8a1173add37aa980f846102907423ad0
run.txt                   820e7035de7b354436197656974d1097df064da6e2433dcd3325a174c22fee45
```

`failed_preflight_096e875.txt` 是第一次工程预检失败的诚实记录，不含科学结果；正式成功链使用 commit
`2de878d60175f72ea41c31966206ab73245561f7`。
