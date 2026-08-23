# Upstream patches

这里保存针对其他现有分支、但不直接改写对方分支的可审计补丁。补丁必须注明精确 base commit、测试结果与
迁移边界；只有维护者审阅后才 cherry-pick。

## Critic clean-confirmation overlay（2026-08-23）

以下四份补丁按顺序应用于学长 `dojo-reproduce@ac008af8b907d319b694f26b0ba9cf4053b3bf69`：

1. `0001-Harden-critic-confirmation-protocol.patch`，SHA-256
   `2fd5ca7b38e4277b68c2eb90b42c0f0ce85b8ab0ef687802e68ceeb8f0fc1fe2`；
2. `0002-Allow-fixed-step-critic-budget-calibration.patch`，SHA-256
   `89d7af494e436c4d5a7ed5c4a06e43c4d012cb26c3efd3c1e9f52bf00b3bd641`；
3. `0003-Record-critic-wall-clock-receipts.patch`，SHA-256
   `a4146bdc6ef3123e3b88a3b909352dd40db3cff992503919d4207c1756313f67`；
4. `0004-Emit-endpoint-score-receipts.patch`，SHA-256
   `237bbffe1130af74527d1a3febcfdcc3330b49a13b785c31039a79a1ac091242`。

集群 fresh no-smudge worktree 中四份补丁均通过 `git apply --check`，Python compile、launcher shell syntax、
`git diff --check` 以及 8 个聚焦测试文件；打印结果为 `36 passed in 46.79s`。第 4 份只把 evaluator 已经计算的
better/worse scalar scores 连同 margin 写入 one-shot receipt，并检查三者一致，不改变模型、输入或预测。该通过只证明工程 overlay 与精确
base commit 兼容，不证明模型效果，也不解除 source-batch provenance、全新 experiment-closed dev/frozen、Cards
LFS 和单旋钮门禁。当前不得直接运行 mixed launcher。
