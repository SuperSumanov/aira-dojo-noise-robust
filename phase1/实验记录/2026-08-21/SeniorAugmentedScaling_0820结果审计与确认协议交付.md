# Senior augmented scaling：0820 结果审计与确认协议交付

日期：2026-08-21。作用域：学长 `dojo-reproduce@baf6bdd`、其
`src/mle_critic/docs/outcomes/0820/AUGMENTED_PAIRWISE_REWARD_EXPERIMENTS.md`，以及基于该精确 commit 的
detached 协议补丁。未启动 GPU、未调用 API、未读取 prospective outcome vault。

## 1. 新结果相对之前的真实进展

Value-pair 两 seed final mean accuracy 随模型规模单调上升：

| Qwen3 Base | 0.6B | 1.7B | 4B | 8B |
| --- | ---: | ---: | ---: | ---: |
| Final mean accuracy | 58.64% | 60.67% | 62.01% | 64.68% |
| Final mean loss | 0.7096 | 0.6954 | 0.6770 | 0.6607 |

TF-IDF 为 61.18%；8B 两 seed 分别为 66.01% 与 63.34%，都高于该基线，均值领先 3.50 pp。与此前多个规模在
约 0.55 波动相比，这是明确的正向容量信号。Decision zero-shot transfer 则较弱：单 seed 的 0.6B/1.7B/4B/8B
为 56.25%/56.25%/59.06%/59.38%，8B 仍略低于 TF-IDF 59.90%。因此最准确表述是“experiment 内 value 排序
出现探索性 scaling；真实局部 decision 的 scaling 尚未确认”。

## 2. 为什么仍不能作为确认性 headline

1. outer test 被 Trainer 每 10 optimizer steps 用作 validation，已不是一次性 frozen test；
2. 产生主要 checkpoint 的旧代码曾设 `greater_is_better=false`，保留的 decision-transfer checkpoint 可能沿错误
   方向选择；final 日志曲线仍有信息，但不能据此洗白 checkpoint；
3. 4B 两 seed与 8B seed 6 没有正常训练结束标记；
4. 旧 full-train 中已有 708/9,001 跨 exact execution config pair 的独立审计证据；
5. test pairs 大量共享 endpoint，逐 pair 二项式不确定性会过窄；现报告没有 task/run clustered CI；
6. decision transfer 只有一个 seed，且不是直接用 decision-train objective 拟合。

这些限定不会抹去正信号，但把它的证据级别固定为 exploratory。

## 3. 本次补丁闭合的协议漏洞

补丁 `0001-Harden-critic-confirmation-protocol.patch` 在 `baf6bdd` 上同时实现：

- exact `(task, client, hardware, time_limit, execution_timeout)` stratum 内配对和 batch-content SHA receipt；
- canonical raw sibling、synthetic cross-run draft、error-contracted improve 三种语义显式分栏；
- combined legacy 文件由 curator 一次性物化 dedicated frozen test，并验证 outer train/test 的 Card 与 physical-run
  overlap 都为 0；
- outer-train physical runs 内确定性产生 train/dev，跨 dev 边界 pair 丢弃并记录；独立 verifier 不 import producer；
- Trainer 只能读取 dedicated train/dev，任何 test row、未知 Card、重复 unordered pair、train/dev Card/run overlap
  都 fail closed；
- checkpoint 只按 dev pair accuracy 正向选择，并写入 data SHA、seed、预处理与选择指标 metadata；
- frozen test 禁止 `eval_cap`，必须校验 pairs/Cards/model 及存在的 head/meta/config SHA，排他 ledger 在解析 pair 前
  写 `STARTED`；完成后输出逐 pair margin、task、endpoint runs、parent 和 semantics。

旧 subtree tests 的 5 个失败来自学长在 `d193e0f` 为 `budget_steps=-1` direct-quality estimand 主动允许 leaves 后
没有同步测试；本次只把测试/文档对齐该已生效语义，没有把标签偷偷改回旧 lookahead 定义。

## 4. 验证与下一步裁决

本地无 torch 的 producer/verifier 测试 24/24。远端精确 base apply 后，在 Python 3.11.15、PyTorch 2.11.0、
Transformers 4.57.1 下 TrainingArguments 契约通过，聚焦测试 33/33，worktree clean。机器回执见
`phase1/results/senior_critic_confirmation_protocol_20260821/verification_receipt.json`。

下一步不是立即重跑完整 0.6B—8B 矩阵。先在不重训前提下，对已锁定 4B/8B checkpoint 和预冻结的 b0/b1/b2
canonical test 定义精确 one-shot 评分矩阵与聚类推断；它只作防守性复核，不能升级旧 checkpoint 为 clean
confirmation。若结果保留正信号，再给 future exact-stratum 重训的模型×seed、总 runs 与 GPU·时预算，获批后启动。
