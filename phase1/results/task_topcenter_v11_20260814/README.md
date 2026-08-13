# Task-conditioned parent objective：v11 train-only discovery 裁决

## 裁决

`VERIFIED_DISCOVERY_NO_UNLOCK`。冻结评测文件未读（`frozen_read=false`），不得启动 frozen look。

主模型 `nested_task_topcenter` 在固定的 5-fold physical-run OOF 上得到：

- pair accuracy：`0.5066854327938072`；
- complete-parent top-1：`0.45108455068614434`；
- parent-equal gap utility：`0.5125829562017966`；
- 20 个有足够样本的任务中，pair accuracy 高于随机的任务占比：`0.55`。

相对历史固定 global all-pair head，top-1 微平均增量为 `0.00398406374501992`，run/task
clustered 95% CI 分别为 `[-0.01717246054159702, 0.02644857206952395]` 和
`[-0.010422655560196711, 0.02148915771321664]`；utility 微平均增量为
`0.002076308434788266`，run/task CI 分别为
`[-0.017060791108872136, 0.025849640614815577]` 和
`[-0.008503888655465223, 0.019741606156476296]`。效果小且双聚类区间均跨零。

## 2×2 机制消融

| arm | pair | parent top-1 | gap utility |
|---|---:|---:|---:|
| fixed global all-pair | 0.5038705 | 0.4471005 | 0.5105066 |
| nested global all-pair | 0.5034014 | 0.4471005 | 0.5091879 |
| nested global top-centered | 0.5073892 | 0.4519699 | 0.5132187 |
| nested task all-pair | 0.5069200 | 0.4519699 | 0.5148433 |
| nested task top-centered | 0.5066854 | 0.4510846 | 0.5125830 |

task residual 在 all-pair 下只有小幅微平均增益、run/task CI 跨零；在 top-centered 下近乎零。
top-centered 在 global 头下的 utility run-CI 下界略高于零，但 task-CI 仍跨零，且绝对 top-1 仍只有
`0.45196989818503763`。因此不能把任一机制写成已成立的正方法结果。

## 完整性与复现

- producer commit：`c84d6c6c5f1a937d51755564ba9af2f9dde3ed73`；
- 输入：4,263 train pairs / 333 physical runs / 23 tasks / 2,293 parents / 5,499 endpoints；
- 5 个 outer folds 的 physical-run overlap 均为 0；所有 optimizer fits 均被接受；
- 独立 verifier 不导入 producer，重建所有 outer score、inner grid selection、指标和 gates；
- 正方向 oracle 为 1.0；随机 pair control 为 `0.5036359371334741`；
- formal fold runtime：`164.57034304365516` 秒；总 invocation runtime：
  `211.5831421171315` 秒；
- producer `summary.json` SHA-256（由 verifier 记录）：
  `e3264cf4f479f1766948cfdbd33beb0fa55aecc38e588870fac67a30a4488d2c`；
- OOF predictions SHA-256：
  `1673455c95666ae0d9d50e2b1043de8b5636bca5cbe76a3886d624dc6b5b3439`；
- 完整归档 SHA-256：
  `d27971c40dcf074b92b2caf10c3f1f4ef59b7a91dfeab858eab42d3ab1bdbb3e`，
  11,300,743 bytes。

launcher 原始 `artifact_manifest.sha256` 在写入后又由 `tee` 追加了最后两行日志，导致唯一 mismatch
为 `preflight.log`（70 项通过、1 项失败）。没有把它伪装成全绿；进程结束后另建不可覆盖的
`artifact_manifest_final.sha256`，重新覆盖当前 root 的 72 个文件，72/72 通过。归档同时包含原始
manifest、最终 manifest 和完整 checkpoint，便于复核这一 provenance 细节。

原始远端 root：
`/research/d7/spc/yzyang4/experiments/task_topcenter_v11_20260814_c84d6c6c5f1a`。

## 文件

- `summary.json`：producer 的完整指标、fold、inner-grid 与 gate；
- `independent_verify.json`：独立重建结果；
- `metrics_compact.csv`、`comparisons_compact.csv`：便于查看的固定数字；
- `full_artifacts.tar.gz`：完整 5-fold checkpoint、OOF predictions、预检、代码快照和审计。
