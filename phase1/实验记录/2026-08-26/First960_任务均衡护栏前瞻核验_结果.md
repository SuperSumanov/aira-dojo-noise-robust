# First-960 任务均衡护栏：首次前瞻核验结果

> **2026-08-26 provenance 撤回：** 本文 v1 forward 绑定了 tainted v1 guard 与 value-reading current coverage matrix，
> 所以旧“未读取 prediction values”attestation 不成立。相同 657→645、delta −12 算术已由 structural-only v2 独立恢复；
> 新证据见 `phase1/results/task_balance_structural_only_v2_8579_20260826_1b9b836/README.md`。本文仅保留历史过程。

**日期：** 2026-08-26

**确认人口状态：** 366/960，closure 未成立

**formal source：** `76bdaad398da675aa62614260d63a019594f172c`

## 1. 问题与确认边界

`7cda` 快照时，OSIC 占 2,635 个 canonical sibling pairs 中的 823 个，share=`0.31233396584440226`，未通过
预先存在的 25% task-balance gate。结果前冻结的 guard 把这一差额写成整数债务：若之后增加 `y` 个 OSIC pairs 和 `x`
个非 OSIC pairs，则清零条件为 `x >= 657 + 3y`。

本次用后续稳定 `8579` 快照做第一次 forward accounting audit。confirmatory 内容只有旧 guard 已冻结的 cap、debt
envelope、all-task constraint、observed-pair allocation unit 与 immediate action。HHI/TV 的概要方向在运维检查中已经见过，
因此只作 descriptive secondary，不伪称新预注册 gate。

## 2. Chronology 与输入完整性

当前 ledger 有 366 runs，旧 ledger 有 339 runs。第一版错误要求新文件 bytes 以旧文件为前缀，因两个新 runs 按冻结时间
全序插入旧 provisional tail 前而失败。进一步 identity audit 证明：

- 339 个旧 run_id 全部仍在新 ledger；
- 旧 run_id 序列是新序列的 subsequence；
- 按 run_id join 后，所有旧行逐字段不变；
- 没有旧 run 缺失；新增恰为 27 runs；其中 2 个位于旧 tail 之前。

因此 first-960 的正确 append-only invariant 是 old-set containment、old-order subsequence 和 row identity，不是原始文件
byte prefix。失败 attempt 与修正规则均已封存。

绑定输入：

- baseline guard SHA-256：`fd87246bb3656befba27de5a98c88f808ca39e178e7322d27ae9536fe4a751b0`；
- baseline run ledger SHA-256：`43b1f16d5326fad5de490a5b63bd8a6f3c454ad303c031cd1fb54e607919cf83`；
- current run ledger SHA-256：`09e3f63b2ae274e6a769ff26fdbcd400a55cacbf6719c3b71063c0c84664bcd1`；
- current coverage matrix SHA-256：`457419804cd00f0579f7f9fef5f512f28fbc7c8759b44493dea50ca7f509b323`。

## 3. Frozen debt accounting

`8579` 相对 `7cda` 新增 120 pairs：

- OSIC：27；
- non-OSIC：93。

冻结 envelope 给出的当前 debt 为：

```text
657 + 3 × 27 − 93 = 645
```

独立 verifier 直接按 current per-task counts 计算 `4×850−2755=645`。两者精确相同，debt delta=`645−657=-12`。
这是正向但有限的结构结果：新增量中 non-OSIC pairs 足以抵消 27 个 OSIC pairs 的三倍成本并再减少 12 单位债务。

## 4. 必须并列的失败边界

- 当前 OSIC pairs=`850/2755`，share=`0.308529945553539`；
- 25% cap 仍失败，当前唯一违反任务仍是 OSIC；
- `future_dominant_pairs=27` 且在此 snapshot 之前 non-OSIC 增量只有 93，远小于旧 clearance requirement 657；
- 因此“debt 清零前暂避 OSIC”的 immediate action 明确未遵守；
- 没有随机化或遵从性设计，不能把 debt 改善归因于 guard，也不能声称 producer compliance。

## 5. Descriptive secondary

| 指标 | 7cda | 8579 | Delta |
|---|---:|---:|---:|
| Run HHI | 0.048877054672340124 | 0.04868762877362716 | -0.00018942589871296517 |
| Pair HHI | 0.1357471491993994 | 0.13322920543739974 | -0.0025179437619996525 |
| Run→pair TV | 0.337082500713674 | 0.32785794333204404 | -0.009224557381629972 |

三项都向更均衡方向移动，但它们不是本次新预注册 gate，不能挽救 cap failure，也不是 predictor accuracy、effect 或 search
utility。

## 6. 复现与失败记录

accepted formal：

- focused：`15 passed in 0.22s`；
- full：`1080 passed, 47 warnings in 73.13s`；
- producer 两个 hash seed 逐字节相同，且等于 committed result；
- independent verifier 两个 hash seed 逐字节相同，且等于 committed receipt；
- result package 6/6 hashes OK；
- formal `SHA256SUMS` hash：`688f8b4fa5a8a463ff6fbd20ff6402bce42e63a984750cb24789a0d87eb45721`。

未接纳尝试：

1. byte-prefix invariant 过强，已按 total-order membership 修正；
2. formal runner 同时启用 `grep` 两种互斥 matcher，测试前失败；
3. Python 3.11 与 3.13 普通 float `sum` 的末 1–2 位不同，未放宽比较，而是将 producer/verifier 改为
   `math.fsum` 后重新提交和复现。

## 7. 论文含义

这一结果强化的是 Decision Corpus 的 acquisition-integrity 故事：结构权重问题不仅可被事后描述，也能在 outcome 前写成
可执行债务、在下一稳定快照逐项核账，并诚实区分“账本改善”“gate 是否通过”“采集动作是否遵从”。它不是 critic 方法
提升，但与 opportunity-yield 发现合在一起，形成了一个较完整的 benchmark data-generating-process 与 audit protocol 贡献。

直接证据：

- `phase1/results/task_balance_guard_forward_8579_20260826/`；
- `phase1/results/task_balance_guard_forward_8579_formal_20260826/`。
