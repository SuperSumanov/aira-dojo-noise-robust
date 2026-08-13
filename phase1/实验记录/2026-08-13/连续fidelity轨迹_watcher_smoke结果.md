# 连续 fidelity trajectory watcher：基础设施 smoke 结果（2026-08-13）

状态：**PASS（仅基础设施）**。本结果不评价模型、selector 或搜索收益，也不把两个路径覆盖样本的
coverage/score 当作论文证据。

## 冻结对象与资源

- 代码 commit：`4630a36a7e5cb989cf8872f03912b21b686d51c6`；validator 在任何 GPU outcome
  产生前已经独立提交并冻结。
- manifest：2 cards，SHA-256
  `e03af45e351ab552fbea311e6af2b30a84cb9e24d2f0e3d875a833c6958cb725`。
- 容器 SHA-256：
  `801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda`。
- pristine grader executable SHA-256：
  `2464182bedf7a3e2bddb3f94b30ff8434e5cd5f64eb84f795308a2e667629002`。
- 矩阵：2 cards × 一次连续执行；30/60/120 秒三个 checkpoints；1×RTX3090；候选执行上限
  240 GPU·秒（0.0667 GPU·h）；0 次 LLM/API 调用。
- Slurm job `10591`：`COMPLETED (0:0)`，节点 `gpu27`，墙钟 00:04:25。

## 冻结 validator 输出

`smoke_validation.json` 给出：

- `decision=PASS`；2 个原子 card transactions、6 条 checkpoint records；物化 JSONL 与事务真源一致；
- 1 个 stable copied snapshot、0 个 racy copied snapshots、1 个 finite pristine grade；
- 第一个 card 在 30/60/120 秒都没有 artifact，120 秒后由 watcher 终止，`final_rc=-9`；
- 第二个 card 在 83.510392 秒自然退出并产生 stable regular snapshot，149,199 bytes，grader
  `rc=0`、分数 0.00662。该分数只验证 grader 路径，不作科学解释；
- 存活进程的五个定时 checkpoint 相对目标时刻的最大偏差为 0.000156 秒，capture-completion
  最大 lag 为 0.000506 秒；自然退出后的 120 秒档按协议记录真实 83.510392 秒，capture lag
  0.017423 秒；
- worker、validator 与 job 均 `rc=0`，process-group 清理门通过；Slurm 结束后没有候选/worker
  残留进程。
- 在新的临时目录中仅复制两个原子 transaction 与物化 JSONL、删除既有判定后重跑冻结 validator，
  输出与原结果逐字节一致（SHA-256
  `adf3fc5aae8438f58ba01a1c0bac67f67a233fb3feec840bec8626f43ec9c6bf`）。

因此 smoke 覆盖了 silent、被 watcher kill、自然退出、stable artifact copy、host-side pristine grade、
原子事务物化和时间门。它只授权在新 physical runs 上把 watcher 当作被动测量仪器；不授权立即扩大
GPU 采集，更不授权基于两个 card 调 selector。

## 失败与废弃尝试（保留审计）

1. 首次预检在登录节点检查 compute-only NVIDIA/OpenCL 文件，因节点语义错误而在提交前停止；未产生
   job、未运行候选。修正为由已分配 GPU 节点 fail-closed 检查，容器 size/mtime/SHA 未改变。
2. job `10590` 使用登录节点本地 `/tmp/codex_trajectory_prereg_20260813` 作工作树；compute 节点不可见，
   在 `cd` 处 1 秒内失败，`FAILED (1:0)`，候选未启动、无结果目录。随后先审计目标 shared worktree
   不存在且未注册，再在 `/research/d7/spc/yzyang4/worktrees/codex_trajectory_20260813` 创建固定 commit
   工作树，才提交 `10591`。
3. 第一次创建 shared worktree 因非交互环境 `git-lfs` 不在 PATH 而在目标创建前失败；确认目标缺失后，
   固定 PATH 再创建。未删除或覆盖任何已有工作树。

这些失败不并入科学样本，也不隐去；它们只说明集群路径与登录/计算节点检查必须区分。

## 下一步边界

- watcher 仅附着到机制冻结后产生的新 discovery runs，记录 `T_art` 的右删失轨迹；旧 fresh-cap
  30/120 秒结果保留为不同 estimand，不能混作同一 headline。
- 先冻结 physical-run/task 分区，再开发低容量 `TaskHazard × ScoreValue`；未见或 support 不足任务
  abstain。最终成功候选 recall 必须在独立 certification runs 上用 exact lower bound 认证。
- 唯一确认性实验仍是至少 150 个合格前瞻 physical runs 的评分通道复现。当前合格 run 数仍为 0，
  17—23 GPU·h 主实验仍 **NOT SUBMITTED**。
