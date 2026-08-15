# Score-channel parent 与 replay 冻结基础设施验收

日期：2026-08-15。裁决：`VERIFIED_INFRASTRUCTURE_ONLY_REPLAY_NOT_AUTHORIZED`。

## 为什么现在补这一步

评分通道前瞻复现已经固定为机制 commit 后至少 150 个 physical runs、dominant task 不超过 25%、
每 run 最多 2 个具有至少两个 finite graded siblings 的 parent。此前只有 outcome-blind run registry；
若门通过后临时手工读 vault、挑 parent 或拼 replay manifest，会留下按 gap/代码/任务成绩挑样本的空间，
也无法证明同一 run 没跨 shard。因此在真实门仍为 47/150 时，先用纯合成 fixture 固定执行边界。

## 实现边界

- trusted selector 只有在完整重算 run gate 后才可打开 vault，只把 `graded is finite` 当布尔资格；
  不读 code，不输出 grade、gap、winner、方向或任何 metric。
- parent lottery 固定为 `SHA-256(20260813|run_id|parent_id)`，每 run 取前 2 个；finite siblings
  全部进入冻结 child identity set，tie 不排除。
- independent parent verifier 不导入 selector，重新读取 vault 并重建完整 sibling clique、finite support、
  lottery 和逐行输出。
- code materializer 与 vault 进程分离，只从 intake summary 已锁定的 blind view 取 selected code；
  code SHA 必须一致，高置信 credential shape 立即拒绝。
- shard 固定为 `SHA-256(score-channel-shard-v1|run_id) mod 4`，保证物理 run 单 shard；独立 replay
  verifier 重建所有行、四个 shard 和理论 cap 上界。
- 所有 producer/verifier 均拒绝覆盖已有输出；manifest 生成也不等于实验批准，authorization 始终 false。

## 验收与失败记录

本地合成测试 `11 passed`。本地完整套件第一次在 collection 阶段因系统 Python 缺 scikit-learn 执行
0 项；排除该既有依赖测试后为 321 passed、2 failed、5 skipped，两项失败均为缺 SciPy。远端改用项目
已有 exp venv，在精确 commit `5f56b3b64594c6128adfed57fcb9981caf4951b6` 的 fresh detached
worktree 得到 focused `11 passed in 1.97s`、full `335 passed in 27.81s`。

远端 a1 被既有 LFS 404 卡在 checkout，a2 使用了无 pytest 的解释器，a3 第一次 47-run probe 少写
registry 的 `/producer`。三项均保留；a3 成功测试不重跑，另补正确路径调用。正确 probe 故意给不存在的
intake root，selector 仍先以 run gate 未过退出 2，证明当前 47-run cohort 的 intake/vault 未被触碰。

## 结论与下一门

本轮只确认**冻结机制可复现且默认拒绝**，不确认评分通道效应，不增加真实样本，不产生真实 parent 数或
replay 数。真实状态继续保持 47/150、shortfall 103、GPU/API 均为 0。达到 run gate 后才执行 trusted
selection；真实 manifest 冻结并经双 verifier 通过后，按它打印的确切 replay 数重新计算 cap 上界预算并
向用户请求一次明确批准。批准前不得新增 authorization receipt 或提交 GPU。

直接证据：`phase1/results/score_channel_freeze_gate_20260815_5f56b3b/README.md`。

