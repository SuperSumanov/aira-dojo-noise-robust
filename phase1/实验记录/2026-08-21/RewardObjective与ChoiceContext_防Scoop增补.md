# Reward objective 与 choice context：防 scoop 增补

日期：2026-08-21。状态：`OBJECTIVE_NOVELTY_CLOSED_RESOURCE_BOUNDARY_RETAINED`。本记录形成时尚未读取
`decision-semantic-mixture-discovery-v2-exact-config` 的任何效果结果；不改变其模型、门槛或停止规则。

## 1. 新核对的一手先例

1. [APLOT（EMNLP 2025）](https://aclanthology.org/2025.emnlp-main.281/) 已针对 Bradley--Terry reward model
   难以区分相似 preference pairs 的问题，按语义相似度和模型 reward difference 构造 adaptive margin，并以
   optimal transport 优化。故“利用 hard pair / margin 改善 RM”“按相似度或预测差动态加权”不是可申首创方向。
2. [PaTaRM（ACL 2026）](https://aclanthology.org/2026.acl-long.927/) 已明确把 pairwise supervision 转成
   pointwise generative reward training，并用 task-adaptive rubric 做实例化评估。故“pairwise→pointwise”或
   “任务条件 rubric”本身不能成为本项目的方法 novelty。
3. [Learning Correlated Reward Models（ICLR 2026）](https://openreview.net/forum?id=TbEyl6krsY) 已从随机效用
   模型出发说明纯 pairwise data 对 correlated preferences 的统计不足，并用 best-of-three data 绕过 IIA
   局限。故“使用多候选 choice context”“指出 pair 展开丢失 setwise correlation”也已有直接理论先例。
4. [Themis（2026）](https://arxiv.org/abs/2605.00754) 已发布多语言、多准则 code-RM benchmark 与 600M--32B
   reward models，并报告规模趋势。故“首个 code reward benchmark”“首次展示 code RM scaling”均不可写。

## 2. 对当前正方向的强制边界

- 不把 gap-weighted BT、pointwise regression、task rubric、setwise/correlated RM 或模型 scaling 单独包装成方法
  突破；它们若运行，只能是已知方法在我方 benchmark 上的 comparator/diagnostic。
- 仍可守住的不是通用 RM objective，而是其 **MLE-agent deployment estimand**：真实 physical run 中同 parent
  产生的 labeled sibling fragment、Draft/Improve construction semantics、连续 pristine execution score、
  source missing/failure、gap/regrade、endpoint reuse、query/init/execution cost，以及结果盲的时间外 cohort。
- direct-decision Qwen scaling 若以后按 clean dev/frozen 协议完成，只能加强“该资源可学习、capacity matters”的
  benchmark 结论；不能声称新 RM 架构。
- 多候选 top-1、NDCG/MRR 与 parent-equal utility 应保留为 deployment-facing metrics，但现有 source choice set
  不完整性必须同时报告，不能恢复已撤回的“完整 choice-set dataset”主张。

## 3. 最值得追的正面命题

在上述边界下，最强的可确认命题仍是数据/评估而非新 loss：**在全局或合成 pair 上得到的模型排序，不能自动外推
到 agent 实际 sibling comparison distribution；一个可部署 critic 必须在 run-clean、exact-config、时间外的新
决策上同时通过 accuracy、parent utility、成本和缺失性审计。** 当前 PairGraph 的模型排序反转是回顾性证据，
first-960 + closure 与已经托管的 frozen scorers 才能把它升级为时间外结果。

这是一条与 CPRD 的 margin/connectivity 理论一致、但落在 MLE-agent 实际搜索决策上的实证资源主张；不得写成
通用理论首创，也不得用尚未闭合的 prospective prefix 提前确认。
