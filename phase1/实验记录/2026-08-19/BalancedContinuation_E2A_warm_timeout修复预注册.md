# BalancedContinuation E2-A warm timeout 修复预注册（2026-08-19）

## 观察边界

- source commit：`e86fe8e01ffc4fd16f638a41551f92e4c658641b`。
- warm run root：`/research/d7/spc/yzyang4/balanced-e2a-warm-smoke-e86fe8e-a1`。
- 首个 chunk：Slurm array job `11212`，slots `0,1,2,3`，最多四个 submitted tasks。
- slots 0/2/3 的 capability/producer/verifier/safety rc 均为 0。
- slot 1（TPS-May）在 `600.2500644080574` 秒超时，producer rc=3，artifact 缺失；冻结代码 stdout
  只显示 5-fold LightGBM 已完成前三折并进入第四折。
- monitor 在 score-blind chunk gate 停止；slot 4/5 未提交。`D_search_rows_read=0`、
  `D_val_rows_read=0`、`D_test_rows_read=0`、`labels_opened=false`、`outcomes_read=false`。

以上只构成执行资格门失败，不构成方法或任务效果结论。失败 run 永久保留，不与修复 run 拼接。

## 允许的唯一修复

统一修改六任务执行协议，不做任务特判：

- `execution_timeout_seconds`: 600 → 1200；
- warm Slurm wall：25 → 35 分钟；
- formal Slurm wall：45 → 75 分钟；
- parent、sibling、task、seed、代码、split、scorer、operator、H=1 全部不变；
- warm 仍为 6 candidate executions / 0 API calls，按 4+2 顺序 chunks 提交；
- formal 仍为 60 rollouts / 120 candidate executions / 60 Qwen API calls，engineering 12 项分 3
  chunks，remaining 48 项分 12 chunks；每个 chunk 最多四个 Slurm tasks；
- chunk 之间只检查冻结 assignment identity 与 capability/worker/verifier/safety rc，不读 score 或 sealed value；
- 任一有 job ID 的 chunk 失败，不重试、不替换、不继续后续 chunks。

## 资源矩阵

- warm candidate hard cap：`6 × 1200 / 3600 = 2.0 GPU·h`；
- formal candidate hard cap：`120 × 1200 / 3600 = 40.0 GPU·h`；
- 原计划预计 `10.247889130908273 GPU·h`；按 20 次 TPS 执行各增加最多 600 秒得到保守预计
  `13.581222464241607 GPU·h`；
- 并发最多 4 jobs / 4 GPUs，排除 `projgpu7/8/33`、`gpu36/38`；
- 不改变 API 调用上限 60，不允许 operator retry 或 candidate retry。

## 修复后的解锁门

新的不可变 commit 与 preparation 必须通过：完整 Linux tests、13/13 preflight、assignment 独立重建、
secret filename/content scan=0。随后新的六任务 warm 必须 6/6 身份精确、四类 rc 全零、网络关闭、public
read-only、private mount=0、0 API、0 label/outcome read。只有全部通过才允许启动正式 E2-A；正式结果仍只用于
label-resource / hurdle / quality-only 资格判定，不允许直接声称方法收益。
