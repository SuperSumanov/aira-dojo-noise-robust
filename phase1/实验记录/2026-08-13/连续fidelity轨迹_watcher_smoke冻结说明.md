# 连续 fidelity trajectory watcher：基础设施 smoke 冻结说明（2026-08-13）

状态：代码、输入选择、预算与验收门冻结；尚未提交 GPU smoke。

## 目的与非目的

现有 `fidelity_worker.py` 为每个 30/120 秒 cap 启动独立 fresh process，适合估计 fresh-cap 剂量响应，
但不能给出部署时“同一执行继续运行”的 time-to-artifact 轨迹。新 watcher 每个 candidate 只执行一次，
由容器外进程在 30/60/120 秒固定 checkpoint 复制当时已存在的 regular `submission.csv` 字节前缀，
最后 kill 全进程组，再用 host-side pristine grader 评分稳定副本。

本 smoke 只验证采集器，不检验策略、模型或搜索收益。任何分数、coverage 或两个 card 的差异都不能写成
科学结论。

## 冻结矩阵与预算

- 2 个 path-coverage cards：在锁定 230-card manifest 顺序中，分别取第一个旧 fresh-cap 120 秒有 finite
  `sub_score` 与第一个无 finite `sub_score` 的 card；只为覆盖代码路径，不据结果挑任务或结论。
- checkpoints：30 / 60 / 120 秒；continuous execution；online cache 设置与旧 replay 相同。
- 资源：1×RTX3090，1 个 Slurm job，执行上限 2×120=240 GPU·秒≈0.067 GPU·h；wall request 20 分钟，
  额外时间只用于容器启动、snapshot hash 与 pristine grading。
- 排除节点：`projgpu7,projgpu8,projgpu33,gpu36,gpu38`；QOS 1 job / 1 GPU。
- 0 LLM/API 调用；不改 agent/operator，不访问 frozen test 标签。

输入选择脚本固定检查：

- `fidelity_manifest.jsonl` SHA `77f696828010e2d6ae10a9b9de2d9ec05d44975b1285ea763d9850a7f30ca4ef`；
- `fidelity_results.jsonl` SHA `b1266d04912596b1e37e13f79ce2387a962f5510cfa264aa1a97b7a1c443180d`。

容器 19.7 GB image 必须在提交前完整 SHA-256 固化；grader executable SHA 为
`2464182bedf7a3e2bddb3f94b30ff8434e5cd5f64eb84f795308a2e667629002`。

## 完整性设计

- candidate workspace 只 bind `solution.py`、公开数据只读与模型 cache；host snapshots 位于未 bind 的
  transaction staging directory，candidate 不能读取或修改；
- 对 `submission.csv` 使用 `O_NOFOLLOW` 打开并要求 regular file；以 opened fd 的初始 size 固定
  checkpoint 字节边界，记录 inode/mtime/size 是否在复制期间变化；变化或复制错误的 snapshot 不评分；
- stdout/stderr 同样按 opened fd 的初始 size 读前缀，允许其随后 append，并记录 changed flag；
- 最后 checkpoint 后无论 leader 是否已退出都向原 process group 发 SIGKILL、wait/reap，并确认组消失；
- grading 只读 host-side regular copy，候选 symlink 永不传给 grader；grader 在 candidate 停止后运行；
- 每 card 的全部 checkpoints、snapshot files 与 `records.json` 在同一 hidden staging directory 完成，
  再原子 rename 为正式 card transaction；JSONL 只是从事务目录确定性物化，不是恢复真源；
- 任一半成品 staging、旧 workdir、SHA 不符、缺 public data/NVIDIA fix、字段/文件 hash 不一致均 fail closed。

## smoke 验收门

必须全部满足：

1. CPU self-test、`py_compile` 与 locked manifest builder 通过；
2. 两个 card 各有且仅有 3 个 checkpoint records，事务目录与物化 JSONL 一致；
3. `snapshot_elapsed_s - cap_s` 每条在 [0,0.5] 秒内；capture completion lag 每条≤1.0 秒；
4. 所有 `sub_copied=true` 的 snapshot 文件 size/hash 与 record 一致；racy/symlink/copy-error snapshot 的
   `sub_score` 必须为 null；
5. 至少一个 stable snapshot 成功经过 pristine grader，得到 finite score；若旧 usable card 因随机性未
   复现，只判 **SMOKE-INCONCLUSIVE**，不改代码后反复挑 card；
6. job rc=0、worker completion marker 存在、进程组无残留、wall 不超过 20 分钟；
7. 输出不含 env dump/API key，失败与 retry 如实保留。

通过后只允许把 watcher 作为新语料的被动仪器；扩大采集仍需单独预注册数据分区和总 GPU·h。

## outcome 前代码审稿处置

单次 DeepSeek 温度 0 审稿使用 5,284 prompt / 2,498 completion tokens。接受并在 smoke 前修正：
leader 提前退出时仍 kill/reap 原进程组；opened-fd/regular-file/symlink/race 完整性；racy snapshot 不评分；
snapshot 移出 candidate bind；每 card 原子事务与字段/hash resume 验证；public-data/NVIDIA fix fail closed。
不采纳：把 append-only stdout 的固定长度前缀称为无效 torn read；要求对普通候选错误重试；以及声称
host grader 会直接读取 candidate symlink（grader 实际只接收 watcher 创建的 regular copy）。
