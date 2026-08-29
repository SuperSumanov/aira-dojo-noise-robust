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

第二次 deployment 在 fresh detached worktree checkout 的 Git-LFS smudge 阶段遇到仓库旧对象
`phase1/results/pairgraph_v11_20260814/full_artifacts.tar.gz` 的远端 404；同样发生在测试与输入读取前。失败 root 原样保留。该 tarball
不属于本审计的代码或六个输入，因此 launcher 只对代码 checkout 增加 `GIT_LFS_SKIP_SMUDGE=1`，后续仍逐 SHA 读取独立 formal root
里的输入；不改变 protocol、scientific computation 或结果门。

第三次 deployment 的新增 focused tests=`7 passed`，但 full-suite 命令误写成 `pytest phase1`，把
`amplifier_test.py`、`premise_test.py` 两个带命令行参数的 standalone analysis scripts 当作 pytest module 收集，得到固定的
`JSONDecodeError/FileNotFoundError('-q')`。既有 formal 的全套回归范围一直是 `phase1/tests`；因此修复为该确切范围。错误仍发生在
producer 与六个私有输入读取前，失败 root 和原始日志均保留，不改变协议或任何计算。

## Formal 结果

正式 commit=`d2fb68c38b75eabd0f3520775da9aa16ea0e6ad6`，formal manifest=
`6928273091f64ce9aa304a05909364e5df40a6d9b55c93d28f5fd612e52651d8`。focused/full=
`7 passed in 0.13s` / `1645 passed, 48 warnings in 97.24s`。producer A/B、private A/B、verifier A/B 均逐字节一致；独立 verifier
从六个 bound inputs 重建 40 个 task-budget rows 与全部 aggregate，0 model refit、未导入 producer。网络、禁读路径、凭据文件名、
凭据内容四类 scanner 全空；private witness 在写入时 mode-0600，formal seal 后为 owner-only mode-0400。

| Budget | Pooled acc Δ | Task-macro acc Δ | Task +/-/0 | LOTO negative | Top-1 / Top-2 positive contribution | Train-task L1 uniform → yield |
|---:|---:|---:|---:|---:|---:|---:|
| 96 | +0.021739130434782608 | -0.03829778065072183 | 6 / 7 / 7 | 2/20 | 0.35714285714285715 / 0.6428571428571429 | 0.5776184538653364 → 0.8042139549086468 |
| 192 | +0.036231884057971016 | -0.1040206851971558 | 6 / 8 / 6 | 1/20 | 0.5294117647058824 / 0.7058823529411765 | 0.3624937655860349 → 0.37869971535806946 |

注：表中 task `+/-/0` 依次为 positive / negative / zero；不公开任何 task identity/hash。

三个 coverage delta 对 task accuracy delta 的 Spearman 在 budget 96 为 `0.3023/0.1594/0.2969`（endpoint/run/pair），budget 192
为 `0.2705/0.2968/0.1504`；同三种 coverage 对 log-loss/Brier 的相关性除 budget-96 run 外均为弱负，方向上与 calibration 改善
一致，但绝不能解释成因果或显著性。结合 pooled 与 macro 反号、gain concentration 和 task-distribution L1 恶化，最简洁机制是：
pure breadth 确实提高了跨 run/task 的触达，却把有限 labels 分散得过薄；少数大任务获益足以抬高 micro average，多数小任务并未
稳定受益。

因此旧 `yield_guarded_breadth` 继续保持 **不晋级、不扩跑**。审计支持的新设计假设是：保留 exact endpoint budget 与 pair-yield
floor，但把任务目标从“尽可能多 unique tasks”改成“induced-label distribution 匹配 outer-train task availability，并加最大任务
占比约束”，同时保留 run anti-dominance。任何新规则必须另行结果前冻结；由于设计已经看过 fold0 task-level audit，历史五折全部
只能标为 development，真正 confirmation 仍只能来自规则冻结后新产生的 physical runs。
