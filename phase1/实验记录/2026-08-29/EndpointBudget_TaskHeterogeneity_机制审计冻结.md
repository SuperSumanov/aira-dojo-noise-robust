# Endpoint-budget task heterogeneity 机制审计冻结

日期：2026-08-29
状态：`FROZEN_BEFORE_TASK_LEVEL_READOUT`

## 动机

single-fold smoke 的两个预算点都给出同向 accuracy、log-loss 与 Brier 描述性变化，而且两臂诱导 pair 数几乎一致；但 terminal
drop-dominant-task delta 为负，严格触发“不晋级”。这说明现在不能扩大原规则，也不能凭总体均值声称成功。下一步先回答一个更窄、
可证伪的问题：coverage 的改变是否与 task-level 收益系统性同向，还是总增益只是少数任务偶然贡献。

## 结果前已知与未知

冻结时已经公开：outer eval=`138 pairs / 20 tasks`；budget 96/192 的 overall accuracy delta 分别为
`+0.021739130434782608` / `+0.036231884057971016`；terminal drop-dominant-task delta=
`-0.038461538461538464`，最大任务占 `34/138`。

冻结时尚未读取：每 task 正/零/负数量、每 task acquisition coverage、每 task accuracy/log-loss/Brier delta、九个 coverage-metric
Spearman、完整 LOTO 分布、正贡献集中度。协议 SHA-256=
`f3aea61901210b17acf2632c0c5a91541dae0fb2b9435ea231d0822657e0a99e`，冻结时间=
`2026-08-29T06:56:13Z`。

## 固定计算

- 只用原 smoke 的 train-only topology、private selection 与 private pair probability witness；不读取 raw decision、labels、senior test
  或任何 first-960/Target-300/Target-522 值。
- 固定 budget=`96,192`；task accuracy delta 是 task 内整数净正确贡献除以该 task eval pairs；log-loss 与 Brier 依原定义。
- train coverage 固定为每 task selected endpoints、selected physical runs、induced canonical sibling pairs；全部取
  `yield_guarded_breadth - exact_b_uniform_edge`。
- 九个相关性固定为三类 coverage delta × 三类 metric delta 的 Spearman；ties 用确定性 average rank，所有 20 个 eval tasks 都保留，
  train 缺失计 0。
- LOTO 对每个 task 各移除一次并公开 min/median/max 与符号数；正贡献集中度公开 top-1/top-2 share 与 HHI，不公开 task 身份。
- 每臂另报 induced-pair task distribution 到 outer-train availability distribution 的 L1 距离。

## 隐私、验证与解释边界

public output 不含 raw/hash task/run/pair identity 或逐对概率；task SHA 的逐 task 行只在 mode-0600 private witness。producer A/B 必须
逐字节一致；独立 verifier 不导入 producer、0 model refit，从六个 SHA-bound 输入重建 task rows 和全部 aggregate。strace 中网络、
prospective/raw-decision/label 路径必须为空。

固定分类是 `EXPLORATORY_TASK_HETEROGENEITY_AUDIT_COMPLETE_NOT_CONFIRMATORY`，没有 promotion gate。本审计不能救回失败 smoke，不能
事后删除/重加权任务，也不能把 fold0 当确认集。它只允许支持或反对“另行结果前冻结 task-quota + yield-floor acquisition rule”这个
机制设计选择。资源=`CPU single-thread, <5 min; GPU/API/model-fit/base-update=0/0/0/0`。

首次 deployment 在创建 formal root、fetch commit 或读取任一输入之前，由 `env_setup.sh` 对未定义 `LD_LIBRARY_PATH` 的访问返回非零；
原因是 launcher 错把 `set -u` 放在 environment source 之前。该次只有 scp 传输，无科学 readout、无 fit、无 API/GPU，按 pre-run
engineering failure 留痕。修复仅把顺序改为 `set -Eeo pipefail -> source env -> set -u`，不改 protocol、input binding、计算或输出。
