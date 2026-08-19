# Related work：FML-Bench 与 stratified search 防 scoop 裁决

日期：2026-08-19。检索范围为 2025--2026 的 ML research-agent benchmark、tree-search critic/PRM、
compute/hardware-aware predictor 与 stratified preference/RL。此轮结论是范围裁决，不是“检索到零结果”的完备性证明。

## 直接威胁：FML-Bench

[FML-Bench（arXiv:2605.17373）](https://arxiv.org/abs/2605.17373) 于 2026-05 提出 18 个 ML research
tasks / 10 domains 的统一框架，显式把 agent strategy 与 code editor、execution、metric display、val/test separation
等 infrastructure 分开；比较 greedy、tree search、evolutionary 等六类 agent，并定义 12 个 process metrics。其
AdaptiveSearch 用 validation stagnation 作为在线信号，从 greedy 不可逆切换到 multi-branch，报告优于固定策略。
[官方仓库](https://github.com/qrzou/FML-bench) 已公开七个 agent、任务配置、统一 runner 与逐步结果/代码快照评分工具。

因此以下主张已被直接覆盖，本项目禁止再写：

1. 首个把 research-agent strategy 与 execution infrastructure 解耦的 benchmark；
2. 首次发现复杂 tree strategy 不一定优于 greedy；
3. 首次用 process-level search dynamics 解释最终表现；
4. 以“validation 停滞后切宽搜索”为核心 novelty 的自适应控制器。

FML-Bench 也使旧 AIRA-dojo “策略不重要”负结论更难单独成文：它已有更广 agent 对照和一个正的 adaptive switch。

## 未被直接覆盖、必须守住的边界

FML-Bench 的论文/公开仓库定位是在线跨 agent 策略 benchmark 与 process metrics，不是以下对象：

- 可重复查询的 NAS-Bench-style **MLE-agent 搜索树节点数据集**；
- 在固定 physical-run split 上训练/比较 critic、code predictor、embedding、LLM judge 的统一 predictor suite；
- 真实 sibling decision 的 parent-matched 选择协议，而非最终 agent 排名；
- predictor initialization/query cost、coverage/selective observability、label noise ceiling、run leakage 与撤回审计；
- pair 两端 exact execution configuration 与 immutable provenance receipt。

这些才是本项目可守的 D&B 容器。与 FML-Bench 的关系应写成互补：它控制在线 agent/harness 比较；我们把已经执行过
的大规模树转成可复用、可审计的 predictor benchmark，研究“在执行候选前能否可靠选择值得执行的节点”。

## 其他相邻工作

- [How Powerful are Performance Predictors in NAS?](https://proceedings.neurips.cc/paper/2021/hash/ef575e8837d065a1683c022d2077d342-Abstract.html)
  已系统强调 predictor 的 ranking/search utility 与 initialization/query time；我们的成本核算和 search-utility 必须
  对齐它，不能只报 pair accuracy。
- [QLASS](https://openreview.net/forum?id=fPXDrhI9d6) 已用自动 Q-value annotation 和 PRM 引导 language-agent
  stepwise search；“给树节点学 value”不是新颖点。本项目差异必须落在真实 ML code execution 树、成本、run-clean
  数据协议与系统比较。
- [Challenges in Inference-Time Scaling with Uncertainty-Aware Tree Search](https://openreview.net/forum?id=t64dINhGri)
  报告 PRM/uncertainty 在 search-induced distribution shift 下不能转化为下游收益；它强化“离线 accuracy 不等于
  search utility”的必要性，也削弱仅做 uncertainty head 的正方法路线。
- [Stratified GRPO](https://openreview.net/forum?id=hqnGfzQQfa) 已把 heterogeneous search trajectories 的
  apples-to-oranges 比较称为 cross-stratum bias。我们的 exact execution-stratum contract 是不同层次的数据生产
  完整性修复，但不能宣称首次提出 stratification 或 cross-stratum bias。

## 裁决与正方向

1. 不恢复 stagnation-triggered adaptive search、跨 agent 策略大横评或泛化的“tree critic 首创”叙事。
2. 当前最可信正路线仍是：future exact-stratum cohort → train-only dev checkpoint selection → frozen test 一次性
   evaluation → 在 pair accuracy 之外报告 initialization/query cost 与真实 sibling selection utility。
3. 若模型 scaling 仍约 0.55，论文正贡献转为 benchmark capability boundary：哪些 gap/coverage/config regimes 可学、
   哪些不可学；但必须用新 cohort 和多 predictor 一致证据，不能靠旧 test-touched checkpoint。
4. D&B novelty 重点放在规模、真实执行树、run-clean/versioned corpus、decision-faithful protocol、noise/coverage/
   provenance 审计，而非再造一个 agent harness。
