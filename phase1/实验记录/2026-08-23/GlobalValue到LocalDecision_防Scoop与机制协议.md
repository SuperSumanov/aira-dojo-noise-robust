# Global value → local decision：防 scoop 裁决与可确认机制边界

日期：2026-08-23。状态：`METHOD_NOVELTY_CLOSED_MECHANISM_STUDY_RETAINED`。本记录形成时没有训练新模型、
没有读取 prospective outcome/frozen vault、没有调用 API 或提交 GPU。它不改变严格前瞻 score-channel 主线；只约束
学长 value-scaling 支持线应如何解释和确认。

## 1. 一手先例与裁决

| 候选主张 | 最直接的一手先例 | 裁决 |
| --- | --- | --- |
| 从完整 outcome/response reward 诱导 partial/process reward | [SP-PRM, ACL 2025](https://aclanthology.org/2025.acl-long.946/) 明确提出 outcome/process granularity mismatch，并从 ORM 诱导 PRM；[Free Process Rewards](https://arxiv.org/abs/2412.01981) 从 outcome labels 得到 implicit PRM | “首次 outcome→process/global→local”关闭 |
| 用树的最终结果或 rollout 成功率产生中间 value/process target | [ReST-MCTS*](https://arxiv.org/abs/2406.03816) 用最终正确性和树搜索估计 step value；[AgentRM](https://openreview.net/pdf?id=xCXRs4WtHC) 从 agent search tree 提取 state value | “首次 tree outcome→local value”关闭 |
| 同时使用粗粒度与细粒度监督 | [HAF-RM, ACL 2025](https://aclanthology.org/2025.acl-long.924/) 已做 token/sequence hybrid supervision；SP-PRM 也联合 partial consistency 与完整偏好 reference | 通用 hybrid/multitask 方法 novelty 关闭 |
| agent/data-analysis 专用 process RM | [AgentPRM](https://arxiv.org/abs/2502.10325) 用 Monte Carlo targets 训练 agent PRM；[DataPRM](https://arxiv.org/abs/2604.24198) 面向 agentic data analysis 做环境感知 process RM | “首个 data/agent PRM”关闭 |
| MLE candidate preference 能节省执行成本 | [FOREAGENT](https://arxiv.org/abs/2601.05930) 已做 MLE solution preference 与 Predict-then-Verify；[AI Research Preference Models](https://arxiv.org/abs/2608.13940) 已在 AIRA-dojo 中选择未执行 candidates 并报告端到端收益 | “首次 MLE 执行前选择/加速”关闭 |
| outcome-only 信号细化成长程 agent 的 step advantage | [SALT, Findings EACL 2026](https://aclanthology.org/2026.findings-eacl.247/) 和 [OPRL](https://arxiv.org/abs/2509.19199) 已分别从 trajectory outcome/preference 构造 step-level 信号 | 通用 credit-assignment 首创关闭 |

因此不能把“先在 global value pairs 上预训练，再在 local decision pairs 上校准”包装成独立方法首创。若只报告这种
训练日程和准确率，容易被认为是标准 transfer/multitask ablation，且直接落入 SP-PRM 等工作的 granularity-mismatch
叙事。

## 2. 仍可防守的窄正面命题

当前最强、且与已有工作不等价的命题是一个 **MLE-agent deployment-distribution 机制发现**：

> 在 exact physical-experiment identity 下，global solution/value 排序上的容量 scaling 是否能迁移到 agent 当时
> 实际面对的 logged sibling decision；若不能，固定计算量的 local calibration 能否恢复该 scaling？

这里的贡献不是新 loss，而是同一模型族在两种 estimand 上的受控迁移曲线。必须同时绑定真实 physical run、
same-parent construction semantics、exact config、run/task/parent clustered uncertainty、query/init/execution cost、
missing/failure registry 与全新 one-shot frozen cohort。公开先例通常没有同时满足这组 MLE 数据身份与部署审计条件；
论文仍不写 `first/only`，只逐轴陈述差异。

若确认结果呈现“global value 随模型规模提升、zero-shot local 仍弱、加入少量真实 local supervision 后稳定恢复”，
这会是正面机制结论：**global supervision 有可迁移表征价值，但 deployment calibration 是必要条件**。若校准无效，
则诚实归入 granularity boundary，不据结果后改比例、模型或子集追救。

## 3. 计算量匹配的四臂候选协议（未授权运行）

状态：`FROZEN_CANDIDATE_PROTOCOL_IDENTITY_AND_BUDGET_BLOCKED`。只有 producer provenance、修复 archives、全新
experiment-closed train/dev/frozen 和 Cards LFS 全过，且先完成已批准流程要求的 G0 wall-time 校准并另报精确
GPU·时后，才可申请运行。

固定四臂使用相同 Qwen3 Base checkpoint、序列化 prompt、optimizer、LR、context、有效 batch、最终 optimizer-token
预算和 seeds；唯一科学旋钮是训练 pair 来源及顺序：

1. **A local-only**：只循环 frozen-train 的真实 sibling decision pairs，直到共同 token budget；
2. **B global-only**：只循环 experiment-closed global value pairs，直到共同 token budget；
3. **C staged transfer**：每个 frozen-train global row 恰用一次，再用每个 local row恰一次；
4. **D interleaved control**：与 C 使用逐字节相同的 global/local rows 和次数，但按 seed 固定交错。

共同 token budget 等于 C 的一次 global+local 序列化 token 总数；A/B 以 deterministic cycle + terminal truncation 精确
匹配，不按结果调整配比。所有臂使用 exact final-step checkpoint，dev 只作一次诊断，不用于在不同 step 中挑最优，
从而避免不同 objective 使用不同 checkpoint selector 的混杂。所有 checkpoint 哈希同时锁定后，独立 evaluator 才各
打开一次新的 local frozen test；global held-out 只作 secondary，不能改变 primary 裁决。

模型效果矩阵至少三个事前 seed；具体模型规模和总 GPU·时只能由 G0 实测后报价，当前为 0 runs / 0 GPU·h。
不得使用旧 test-touched checkpoint、现有 1,160-row test、14B/27B extension 或结果后 calibration-fraction sweep。

## 4. 分层成功门与 kill conditions

Primary 是 local frozen sibling accuracy；task-cluster CI 为主、parent/run cluster 为敏感性分析，并完整报告
Draft/Improve、task macro、seed 离散度、LOTO 与 TF-IDF 同池基线。

按固定层级裁决，避免多重比较追故事：

1. **H1 transferable supervision**：C−A 的三-seed mean point delta `>=0.02` 且 task-clustered 95% CI 下界 `>0`；
   C−B 同样 CI 下界 `>0`；三个 seed 的 C−A 符号全为正；C 还须超过同池 char-TFIDF 且 task-CI 下界 `>0`。
2. **H2 staging-specific**：只在 H1 全过后检验 C−D；point delta `>=0.01` 且 task-CI 下界 `>0` 才能写“顺序本身
   有益”。否则只能写“global+local supervision 有益”，不得称 staged 方法有效。
3. **稳健性**：C 相对 TF-IDF 的 Draft/Improve delta 均不低于 `-0.01`；删除任一 task 后 C−A 与 C−TF-IDF
   均不翻转；没有单 task 贡献超过总正确差的 35%。

以下任一触发即停止 effect stage 或 extension：source provenance 未全覆盖；train/dev/frozen experiment overlap 非 0；
dev `<400` pairs、`<8` tasks 或 dominant task `>0.35`；训练 NaN/OOM/receipt 不完整；H1 任一主门失败；或任何旧
test/frozen path 被训练进程打开。失败后不得换 seed、比例、阈值、模型或任务子集追救。

## 5. 论文定位

若 H1 通过，这项结果加强 NAS-Bench-style D&B 论文中的“benchmark construction determines deployment estimand”
主张，并为学长的 value scaling 提供正面、可操作的桥；不升级为通用 RM 方法论文。若 H2 也通过，staging 只作为
一个简单、充分对照过的 correction baseline。严格前瞻 score-channel、first-960/closure 和 benchmark/integrity
资产仍是论文主轴，互不替代。
