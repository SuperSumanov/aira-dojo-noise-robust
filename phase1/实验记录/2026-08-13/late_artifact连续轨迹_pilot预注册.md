# 昂贵 silent 候选的 late-artifact 连续轨迹 pilot（2026-08-13）

状态：路线裁决 pilot；manifest、代码、验收与输入 SHA 在 GPU outcome 前冻结。它不估计论文效果量，
不替代新语料 discovery/validation/certification 或 150-run 确认集。

## 目标

Selective Feedback Racing 保留最终 winner 0.9800，却只得到 2.62% optimistic tail 空间：被安全淘汰的
observed losers 很便宜，昂贵 silent 候选占主要成本。下一必要问题是：**此前 fresh 120 秒无 finite
pristine score 的昂贵候选，若在同一进程继续执行，是否会在 full completion 前变为可评分？**

- 若至少两个不同任务稳定出现 late conversion，后续新数据可开发 task-conditional `TaskHazard ×
  ScoreValue`；
- 若没有 late conversion，延长 selector 等待不能创造信息，应优先验证 `schema-first operator`；
- 本 pilot 不训练模型、不改 agent 代码、不选择分数漂亮的 card。

## 冻结抽样

锁定输入：

- `fidelity_manifest.jsonl` SHA-256
  `77f696828010e2d6ae10a9b9de2d9ec05d44975b1285ea763d9850a7f30ca4ef`；
- `fidelity_results.jsonl` SHA-256
  `b1266d04912596b1e37e13f79ce2387a962f5510cfa264aa1a97b7a1c443180d`；
- `fidelity_runtime_v9.jsonl` SHA-256
  `dff8eb88a1db8d63bab17851c1dce2c1bd389a4744a811d65a5ce1fe5a1f55e7`；
- `card_run_map.json` SHA-256
  `3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30`。

资格：fresh cap=120 的 `sub_score` 非 finite，且历史 full runtime ≥600 秒。按
`SHA256("late-artifact-v1|" + card_id)` 升序贪心取前 6 个，同时要求 task 与 physical run 均不重复；
不足 6 个则 fail closed。选择完全不读取 final grade、stdout、gap 或代码内容。manifest 只保留执行所需
task/card/code/parent/stratum，不写 final grade。

## 冻结矩阵与预算

| 项 | 固定值 |
|---|---|
| cards | 6 个 prior-fresh-120 silent，6 tasks，6 physical runs |
| execution | 每 card 单一 continuous process，不 restart |
| checkpoints | 30 / 60 / 120 / 240 / 360 / 480 / 600 秒 |
| GPU | 1×RTX3090，排除 projgpu7/8/33、gpu36/38 |
| max candidate execution | 6×600=3600 GPU·秒=1.00 GPU·h |
| wall request | 01:30:00；预期含 grader/容器启动 1.0–1.3 小时占卡 |
| API | 0 |

容器、public-data bind、online cache、NVIDIA fix、pristine grader 及其 SHA 与 job 10591 的 PASS smoke
完全相同。candidate 只读 public data，看不到 manifest、snapshots、grade 或标签。

## 冻结验收与路线门

必须先通过基础设施门：6 个原子 transactions、每个恰好 7 records；物化 JSONL 一致；存活 checkpoint
定时误差在 [0,0.5] 秒、capture lag≤1 秒；stable copy 的 size/hash 一致；racy/copy-error 不评分；
process-group 无残留；job/worker/validator rc=0；grader/container/manifest SHA 一致。

每 card 的 `first_finite_checkpoint` 取当前 continuous run 首个 finite pristine score 的冻结 checkpoint：

- `continuous_by_120`：≤120 秒已 finite；它只说明 fresh replay 不稳定，不算 late；
- `late_conversion`：≤120 秒均不 finite，且在 240/360/480/600 首次 finite 的 stable artifact hash
  未曾在 ≤120 秒 stable snapshots 中出现；
- `grader_recovery_not_conversion`：>120 秒 finite 的 hash 在 ≤120 秒已经 stable 存在，只是早期 grader
  未返回 finite；它不算 artifact conversion，并令路线裁决为 `INCONCLUSIVE`；
- `never_finite_by_600`：所有 checkpoint 均不 finite。

若进程在 checkpoint 前自然/异常退出，watcher 立即复制当时 artifact；只要它是新的 stable regular
file、经 pristine grader 得到 finite score，仍属于该退出时刻前可部署的反馈。路线问题是“信息何时可见”，
不是“进程在名义 checkpoint 是否仍存活”；因此不因 `process_alive=false` 排除，但逐卡记录 snapshot
elapsed、liveness 与 final rc。相同旧 hash 的 grader retry 不得伪装成 late conversion。

路线裁决：

- `TASKHAZARD-CANDIDATE`：late conversion ≥2 cards 且覆盖 ≥2 tasks；
- `SCHEMA-FIRST-CANDIDATE`：late conversion=0 且 grader-recovery ambiguous=0；
- `INCONCLUSIVE`：late conversion=1，或存在 grader-recovery ambiguous card；
- 任一完整性门失败：`INVALID`，不得按科学结果解释。

不根据 score 高低、最终 quality、任务名称或 continuous-120 是否“好看”改路线门。pilot 后不在同一 6 cards
增加 checkpoint 或换样本补结论；下一实验必须使用新语料和新的冻结分区。

## outcome 前对抗审稿处置

DeepSeek-v4-flash 在 GPU 提交前完成一次固定审稿（13,493 prompt / 3,088 completion tokens）。采纳其
“相同 pre-120 artifact hash 的后续 grader 成功不得算 late conversion”，新增 hash-aware ambiguous 状态、
snapshot elapsed/liveness/final rc 记录、symlink 与 grader timing 门、result-grid 完整性 self-test。

未采纳以下误报并固定理由：valid stable artifact 即使伴随进程退出仍是部署时可见反馈，不要求在名义
checkpoint 存活；checkpoint snapshot 本来就应与进程继续运行后的 post-kill source 不同，不能据此判 stale；
parent/stratum 所在 manifest 从未 bind 给 candidate，candidate workspace 只有 `solution.py` 与 public data；
stdout 是 agent 自己输出的观测记录，不是 pristine label，且路线函数不读取；主 worker 在 resume 和无 todo
时都会从原子 transactions 重新 materialize JSONL；`grade_rc="TIMEOUT"` 已显式区分 grader timeout。
