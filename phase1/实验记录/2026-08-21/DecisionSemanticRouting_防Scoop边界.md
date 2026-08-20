# Decision semantic routing：防 scoop 边界

日期：2026-08-21。状态：`RELATED_WORK_BOUNDARY_FROZEN_BEFORE_SUPPORT_RESULT_READ`。

本记录冻结时，exact-config support 的正式双实现仍在运行；未读取其 `summary.json`、资格门状态或任何模型结果。
本轮只收紧 novelty，不改 `DecisionSemanticMixture_CPU发现门_v1_预注册与预检.md` 的模型、权重、统计门或停止规则。

## 1. 直接先例

1. [Exploring Domain Robust Lightweight Reward Models based on Router Mechanism](https://aclanthology.org/2024.findings-acl.511/)
   已比较内部 MoE、外部 router 选择多个 domain-specific reward models，以及共享小模型上的 adapter experts。
2. [DMoERM](https://aclanthology.org/2024.findings-acl.418/) 已按 task category 路由到专门 reward experts，并再组合
   capability experts；其动机明确包含多类 preference data 对单一 RM 的干扰。
3. [ArmoRM](https://aclanthology.org/2024.findings-emnlp.620/) 已用 gating network 按 context 混合多个可解释 reward
   objectives。
4. [MiCRo](https://aclanthology.org/2025.emnlp-main.882/) 已从理论上说明异质 preference mixture 下单一 BT model
   可有不可约误差，并用 context-aware routing 动态组合 preference components。
5. 2026 年的 [PrefMoE](https://arxiv.org/abs/2605.00384) 与
   [Sparse MoE Reward Models](https://arxiv.org/abs/2606.04284) 又分别覆盖 trajectory-level soft routing、
   heterogeneous binary preference 与 specialized experts。

因此，即使固定的 `0.5 * pooled + 0.5 * semantic-specialist` 在我方数据上为正，也不得声称：首次用 mixture/expert
处理 reward modeling、首次按 domain/task/context 路由 preference model、首次指出单一 BT/RM 会平均异质偏好，
或首次用 specialist 改善 pairwise preference prediction。当前线性三-head 实现比这些方法更简单，也不是新的 MoE
架构。

## 2. 仍可回答的窄问题

本实验只保留为 benchmark diagnostic / baseline：在 MLE program-search 的固定数据构造中，Draft（跨 physical
runs 的首批方案）和 Improve（局部 sibling/contracted-parent 改进）是已记录、部署时可见的生成语义。我们问，在
exact `(task, client, hardware, time_limit, execution_timeout)` common support 和 run-clean split 下，固定语义
specialist 是否比同一 train-only 表示上的 pooled head 更适合真实 decision pairs。

本轮一手源检索没有发现与上述 MLE Draft/Improve、连续 pristine execution score、physical-run-clean sibling
协议完全等价的公开实验；这只是当前检索边界，不是“无人做过”的证明。若 discovery 通过，它最多提供：

- preference/construction semantics 在 MLE-agent benchmark 中有可测影响的领域证据；
- future exact-stratum frozen confirmation 的候选 baseline；
- 解释 value-pair scaling 与 decision transfer 落差的一项机制线索。

它不能单独成为论文的方法 novelty，也不能替代 first-960 + closure、真实 sibling top-1/utility、成本与噪声资产。
若预固定 discovery 门失败或 exact-config 支持不足，该路线直接关闭，不换权重、router、任务子集或单独追 Improve。
