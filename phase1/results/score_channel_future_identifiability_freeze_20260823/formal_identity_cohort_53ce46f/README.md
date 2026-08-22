# Formal future identity-cohort receipt

这是 commit `53ce46f0be18f725987e6d0ce4d72df54ca8c0a9` 从 GitHub fresh no-smudge worktree 产生的完整 formal
回执。机器状态为 `FUTURE_COHORT_COLLECTING`：12 个 future archives 已观察，0 个成为 transaction，settled prefix=0，
selected physical runs=0/300，pending head=ranzcr。它只说明预先固定的 6 小时稳定门尚未跨过，不是 effect 结果。

- focused：`11 passed in 0.56s`；
- 完整 phase1：`758 passed, 33 warnings in 55.55s`；
- producer×2 与 independent verifier×2：逐字节一致；
- raw archive / label vault / blind code sidecar / score directory forbidden open：0；
- 文件名密钥扫描：0；高置信内容密钥扫描：0；
- `SHA256SUMS` 文件自身 SHA-256：
  `fefb6a767ebe77ce9232c1423212d8fe062340b6753ad4493f97301d62e3febe`。

`producer_a/summary.json` 是主机器状态，`verification_a.json` 是不导入 producer 的独立重建；所有 strace 与两次重复
产物一并保留，使 `SHA256SUMS` 可完整复验。GPU=0、API=0、model fit=0、base-LLM update=0、replay 未授权。
