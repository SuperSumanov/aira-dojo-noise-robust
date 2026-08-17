# Score-channel / selective observability：近期防 scoop 更新

检索截止：2026-08-18。范围聚焦 2025--2026 年 MLE-agent、agent critic、execution failure、
selective execution 与 external evaluator。本文档只做主张边界更新，不授权新 GPU/API 实验。

## 裁决

没有发现已经完成以下同一组合的工作：**MLE-agent 真实 sibling 决策点 + 同一 120 秒共同候选 + pristine
外部 submission score 对 keyed self-report 的严格配对 + physical-run/task 聚类推断 + 机制冻结后的时间前瞻
复现**。因此当前 score-channel 主线没有被直接 scoop；但“critic/经验记忆”“早期失败”“隐藏一致评估”和
“选择性/延迟 objective”各自都已有强邻近工作，novelty 必须落在上述组合与数据资产，不能泛称首次研究
execution feedback、failure process、external evaluation 或 missing feedback。

## 最近且最需要正面区分的工作

1. **AIRA_2**（arXiv:2603.26499）最接近。它用 Hidden Consistent Evaluation 证明稳定评估对长程搜索重要，
   并把既有退化主要归因于评估噪声。我们的增量不是再发明 HCE，而是对搜索树节点的两个同时可见评分通道做
   decision-local、run-clean、cost-aware 的系统比较，并以前瞻 physical runs 确认信息质量差异。
2. **Critic Experience Bank**（arXiv:2607.12397）用完整轨迹后的 LLM 多数票产生 step-productivity
   pseudo-label，再检索经验改善执行前 critic 的 calibration/ranking，并做 selective execution。它不使用 MLE
   pristine evaluator，不研究 submission artifact 的选择性可见性，也没有同一候选上的 external-vs-self-report
   配对。它会压缩“经验库 critic”方法 novelty，但不覆盖当前数据/评测主张。
3. **Failure as a Process**（arXiv:2607.09510）在 Terminal-Bench 的 1,794 条完整 CLI trajectories、
   63k+ steps 上研究 failure onset/evolution/recovery，并指出错误常很早发生但很晚才可观察。它是 failure-memory
   与 time-to-observability 的强相关实证邻居；但任务、标签、决策单位和外部 submission score 都不同。
4. **MLEvolve**（arXiv:2606.06473）、**Gome**（arXiv:2603.01692）和 AgentGA（arXiv:2604.14655）
   分别改变 graph search/memory、reasoning update 或 agent seed。它们强化了“只做另一个 search policy 不够”
   的判断，也支持把论文容器放在 NAS-Bench-style corpus 与 predictor/evaluation study，而非声称新 SOTA agent。

## 应当坚持的论文主张

- 外部评分的价值必须在**共同覆盖候选**上比较，缺失本身不能当低质量；
- headline 单位是 physical-run-clean 的真实 sibling choice，不是全局 solution 笛卡尔积；
- 初始化成本、单次 query 成本、coverage、标签噪声上界和 task/run 聚类不确定性同时报告；
- 前瞻确认只证明 scoring-channel mechanism，不自动等于全候选 search speedup；
- failure taxonomy/494-pair benchmark 是 evaluator-verified 的数据资产，不冒充已成功的 learned controller。

## 近期正面突破优先级

1. 完成固定 150-run gate 后的 parent/replay 冻结，并按原矩阵确认 `sub_score - stdout_val`；
2. 若前瞻确认通过，把主叙事定为 **Evaluation channels are not interchangeable under selectively observable
   execution feedback**，AIRA_2 作为动机与底座而非竞争性重做；
3. 若只是 BORDERLINE，仍保留 run-clean corpus、noise/coverage/cost 分解和 failure-censor benchmark 为
   D&B 主资产，不用结果后 selector 或 task 子集“救显著”；
4. 暂不恢复 CEB-like memory critic、统一晚等、TaskHazard 或旧 HCE 多臂；它们要么已关闭，要么容易被近作覆盖。
