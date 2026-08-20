# TraceML / MLE-Traj-v1：直接竞品边界与外部复现机会

日期：2026-08-21。性质：公开一手 dataset card 核查；未下载 gated raw code，未读取我方 prospective
outcome，未运行任何效果比较。

## 为什么这是必须纳入的直接竞品

[MLE Trajectory Dataset v1.0](https://huggingface.co/datasets/jerryyan/mle-traj-v1) 明确以 NeurIPS 2026
Datasets & Benchmarks 为目标，公开 7 个 Kaggle competition 上的人类与 LLM-agent 逐版本轨迹：422 条 human
kernel trajectories、11 个 Codex runs、13 个 MLEvolve tree-search runs（被线性化为 189 条 root-to-leaf
branches），共 15,572 个 versioned code snapshots 和 14,944 个 transitions。每个 agent version 绑定
`mlebench grade-sample` 外部分；状态、动作、意图和 predicted score effect 由 GPT-5-mini 标注。

其扩展版 [TraceML](https://huggingface.co/datasets/TraceML-HF/TraceML) 又覆盖 134 个 Kaggle competitions：
公开 paired split 在 7 个共同 competition 上有 13,692 human + 1,514 agent state rows、13,412 human +
1,314 agent action rows；另外 127 个 competition 是 humans-only。它还发布 7 个带 planning-skill prompt 的
Codex experiment runs。公开仓库记录说明这是 NeurIPS 2026 E&D double-blind 产物。

因此以下宽主张立即关闭：

- “首个带逐版本 Kaggle held-out score 的 MLE 轨迹数据集”；
- “首个发布 MLEvolve/AIDE 树节点代码与外部分的数据集”；
- “首个分析 MLE agent 的 state/action/intent 或与人类专家比较”；
- 仅凭 endpoint 数量、逐版本 score 或树结构申数据 novelty。

## 与我方当前对象的可核差异

| 维度 | TraceML / MLE-Traj-v1 公开口径 | 我方当前口径 |
|---|---|---|
| 核心问题 | 人类与 agent 的逐版本 planning/behavior；planning-skill harness | 给定真实 search-time sibling choice set，执行前 critic 能否选出更优候选 |
| agent 支持 | 7 tasks；11 Codex + 13 MLEvolve physical runs，后者线性化为 189 paths | 当前前缀 26 tasks / 249 eligible physical runs；目标 first-960 + closure |
| 比较单位 | 相邻 version transition、human fork/code-sim forest、root-to-leaf branch | 同一 physical run、同一真实 parent 的 canonical sibling pair/choice fragment |
| 标签 | score 直接写入 state/action 表；另有 LLM state/action/intent 标签 | pristine continuous score、source missing/failure registry、pair orientation 与 repeatability 分栏 |
| 评测完整性 | 公开 card 未说明 run-clean predictor split、outcome-blind temporal escrow 或 predictor cost | physical-run-clean、endpoint reuse/gap/noise、query/init/execution cost、activation 后 escrow |
| 复现边界 | v1 card 说明 per-node regrade 缺原 submission CSV 与本地 MLE cache，不能由 release 单独重做 | 原始 archive/intake/scorer receipt、append-only snapshot 和独立 verifier 逐 SHA 绑定 |

表中“未说明”只描述当前公开 dataset card，不能外推为论文一定没有；在正式 related work 中必须以论文终稿
复核。TraceML 的人类广度、语义标注和行为分析明显强于我方，不能用我方 agent run 数反过来贬低其不同
estimand。反之，它的 189 条 branch 不能在未核 physical-run grouping 前当作 189 个独立 agent runs；这只是一项
未来审计要求，不是对其现有统计的泄漏指控。

## 可转化为正贡献的唯一近期动作

把 TraceML/MLE-Traj-v1 作为**外部 replication**，而不是再和它争“MLE trajectory dataset”标题。若 gated
raw MLEvolve code 获得正常访问授权，先做 outcome-independent eligibility audit：

1. 锁定 dataset revision、逐文件 SHA、license 与 score direction；
2. 从 raw tree 恢复 13 个 physical runs，按 `(tree, parent, child)` 去重，禁止把 189 paths 当独立样本；
3. 与我方 train/frozen/prospective 做 exact run/card/code SHA overlap；任何 overlap 均隔离，不能称 external；
4. 要求至少 8 个独立 physical runs、4 个 tasks、150 个 finite non-tie sibling pairs，且任一 task pair share
   `<=0.50`；否则只做结构描述；
5. 资格门通过后，才允许用已冻结且未接触该数据的 scorer 一次性评分；run/task 聚类区间为主，不训练、不挑
   checkpoint、不因结果改 pair construction。

这条外部复现若为正，可以把“只在我方 AIRA 采样机制有效”升级为独立 release 上的 transfer 证据；若不通过，
仍应把 TraceML 写成最直接 related work，并将我方贡献严格限定为 decision/predictor benchmark、failure-censor
契约、成本审计和结果盲时间外确认。当前未获得 gated raw code，因此没有启动该实验，也不把它计作已有资产。
