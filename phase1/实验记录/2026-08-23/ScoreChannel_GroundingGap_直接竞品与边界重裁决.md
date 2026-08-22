# Score-channel：grounding-gap 直接竞品与边界重裁决

日期：2026-08-23。审计对象：Park & Choi, *When Do Agent Loops Mistake Stagnation for Progress? Self-Evaluation
Bias and Externally Grounded Verification in Long-Running Autonomous LLM Agent Loops*, arXiv:2607.25152v1，
2026-07-27（[arXiv abstract](https://arxiv.org/abs/2607.25152)，
[PDF](https://arxiv.org/pdf/2607.25152)）。本文是一份 23 页 preliminary draft / preregistered pilot；即使尚未正式录用，
也必须按公开时间戳视为已有工作。

## 1. 直接重叠

该文已经操纵 evaluator 的 information channel，并把 generator/agent 与 evaluator 分开：

- `in-band-self` 只信 agent 自报；54 个 T1 cycles 中 agent 100% 声称改进，但 56% 的 oracle delta≤0；
- `in-band-judge` 让更强模型读取完整 artifact、diff、历史 verdict，却不允许访问 oracle；
- `out-of-band` 独立读取隔离的 world-state oracle，只在真实 delta>0 时接受；
- 另有 sign-only out-of-band 变体，只反馈 accept/reject、不反馈 oracle 数值；
- 主 pilot 为一个 open-ended T1 task family、每臂 3 independent repetitions、每次 6 cycles；另有 boundary B1
  control。不同臂产生独立 candidate rollouts，并非对同一候选逐一重判。

其 broad conclusion 是：success signal 在 transcript 外时，扩大 in-band judge 不足，out-of-band grounding 是结构性
要求。这直接覆盖“自报进步不可靠”“外部分优于自报”“更强 judge 不能弥补不可见 ground truth”“把 evaluator 放到
agent 外部”四类宽泛主张。

还要如实指出，它的 out-of-band mirage=0 是 gate 定义的代数结果：该臂只接受 positive oracle delta；论文自身也明确
承认这一点。真正的经验内容是三臂在相似 regression-candidate base rate 下，gate discrimination 和最终高度不同。

## 2. 与我们 estimand 的逐轴差异

| 轴 | arXiv:2607.25152 | 我们冻结的 score-channel |
| --- | --- | --- |
| 领域 | synthetic-user conversion / open-ended loop | 真实 MLE/Kaggle tasks 与 aira-dojo search tree |
| 单位 | sequential cycle 的 candidate-vs-deployed delta | 同一 logged parent 的真实 sibling candidates |
| 通道 | binary self claim、artifact-reading judge、world oracle | keyed numeric stdout self-report 与 pristine `submission.csv` numeric score |
| 候选控制 | 三臂是 independent rollouts | 两通道在同一 120 秒执行、同一共同候选池上比较 |
| grounding 可用性 | 每 cycle 都有 oracle delta | 很多短时执行没有 scoreable artifact；missingness/execution cliff 是 estimand 的一部分 |
| 决策问题 | 是否部署本轮修改 | 在固定搜索预算内如何排序/选择 siblings |
| 统计单位 | T1 每臂 3 repetitions×6 cycles，另有 B1 | 冻结 177 physical runs、17 tasks、158 parents、320 candidates；run/task-cluster inference |
| 时间协议 | preregistered pilot | mechanism-commit 后的 temporal cohort、outcome-blind parent lottery、one-shot analysis |

所以它没有直接回答：在真实 MLE 搜索中，当 grounded score 只能选择性出现时，**同一候选**的 external numeric score 是否
比 agent numeric self-report 更能排序最终质量；也没有给出 artifact availability、silent candidates、run dependence、
task dependence、query/init cost 与时间前瞻审计的联合 benchmark。

## 3. 撤回与保留

立即关闭以下说法：

1. 首次发现 self-report 与外部真实结果脱节；
2. 首次证明 out-of-band evaluator 优于 in-band evaluator；
3. 首次证明更强 LLM judge 不能跨越 grounding gap；
4. 首次把独立 external evaluator 放入 agent loop；
5. 仅凭“pristine 分高于 stdout”就申方法或概念 novelty。

仍可防守、但必须按窄口径写的主张：

1. 可审计的 MLE-specific benchmark 组合：真实 sibling topology、numeric in-band/out-of-band channels、短预算
   artifact availability、failure/missing registry、run-clean/temporal split 与 query/init cost；是否“首次”必须继续按组件核查，
   当前不作首创断言；
2. 同一候选池、同一执行预算、run/task-clustered 的 domain-specific external-validity measurement；
3. **grounding availability frontier**：grounded evaluator 不只是“好不好”，还存在“何时可用、对哪些候选可用、条件化后
   剩多少选择价值”的 systems 问题。该轴是对方 always-observed oracle 设计没有覆盖的；
4. 正结果若通过，只能表述为“在选择性可观测的 MLE search 中，pristine channel 在共同覆盖候选上提供额外 ranking
   value”，不能泛化为 grounded evaluation 的首次验证。

## 4. 对当前实验的裁决

冻结 score-channel replay 不撤销：它仍是当前资产中最有价值的前瞻机制确认，因为其严格同池、真实 sibling、跨任务和
selective-observation 设计能补直接竞品的外部有效性缺口。但它不再能单独承担方法/概念首创，必须嵌入 D&B 容器，并把
headline 从“external evaluator beats self-report”改为：

> Grounded feedback is valuable but selectively available; the benchmark measures the joint frontier of short-budget
> availability and conditional sibling-selection value under real MLE search dependencies.

正式叙述必须同时报告：（a）短预算 artifact/stdout 的联合覆盖；（b）共同覆盖集的原预注册 ranking estimand；（c）
silent candidate 的 post-hoc regret 分解；（d）run/task clustered uncertainty。只报共同覆盖准确率会把 execution cliff
藏掉，不能支撑该收窄主张。由于旧 320-replay 的 aggregate KILL 在该分解协议冻结前已经写入仓库，新增分解只能是
post-hoc descriptive，不是第二个 confirmatory test，也不改 primary KILL。

本轮只做一手论文审计与主张修正；GPU/API/model fit=0。协议冻结时没有打开 raw result shards 或 label vault，但已知
仓库报告中的 aggregate primary outcome，不能写作 outcome-blind。
