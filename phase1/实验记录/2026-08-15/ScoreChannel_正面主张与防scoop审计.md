# Score Channel 正面主张与防 scoop 审计

日期：2026-08-15。状态：当前方向解释文件；不改写 `CURRENT_DIRECTION.md` 的唯一主实验、资格门或预算门。
本轮只检索公开一手论文页、正式论文和官方代码仓库，没有读取前瞻 cohort 的 label、score 或 replay outcome，
没有调用 API，也没有提交 GPU。

## 1. 当前最强、且不过界的正面主张

论文不应把结果写成“critic 普遍无效”，也不能把已有的 external evaluator 重新命名成新方法。可防守的核心是：

> MLE-agent 搜索中的评估反馈不是一个总能观察到的标量。它同时包含“候选是否及时产生可由可信外部评估器
> 评分的 artifact”和“在已评分候选中该分数能否选对”两个部分。真实 sibling 决策上，pristine 外部分数的
> 条件排序价值很强，但 artifact 可观测性具有明显选择性；只在成功候选内报告 predictor accuracy 会改变部署
> estimand。我们发布 physical-run-clean、choice-set-faithful、failure-censored 的数据与审计协议，并用机制冻结后
> 的新 physical runs 前瞻复现评分通道效应。

这是一条正面的 benchmark/mechanism 主张：可信分数值确实有用；数据贡献解释它何时可用、何时不可见，以及
为什么“只在可评分行上比较模型”不能代表真实搜索。它不是端到端加速主张，也不是“首个 external evaluator”。

## 2. 现有证据链必须整体报告

定义三个不同 estimand；不得只选其中最好看的一个：

- `C(tau)`：候选在时间 `tau` 前产生 schema-valid、finite pristine score 的概率；
- `V(tau)`：同一 parent、同一共同覆盖候选上，trusted external score 相对 self-report 的 tie-aware top-1 差；
- `U(tau)`：把 coverage/missingness 一并计入后，完整部署策略相对基线的效用差。

冻结发现集给出：

| 层次 | 已验证事实 | 当前解释 |
|---|---|---|
| 条件通道值 `V(120)` | external=0.9167、stdout=0.7083、差 +0.2083；24 sets / 15 runs / 9 tasks；run/task CI 均高于 0，但 run sign p=0.0625 | 强正向机制候选，尚未确认 |
| score value vs presence | score cascade − presence cascade=+0.1447；run-CI [+0.0717,+0.2241]，task-CI [+0.0541,+0.2510] | artifact 的数值而非“存在”携带稳定价值 |
| observability selection | presence cascade − stdout=−0.0747；run-CI [−0.1385,−0.0182]，task-CI [−0.1604,−0.0059] | 及时产物不是质量的无偏代理 |
| coverage-complete utility `U(120)` | naive cascade − stdout=+0.0700，但未过预注册 +0.08、双聚类 CI 与 sign 三门 | 不能声称现有策略已加速 |
| source failure status | 902 个可回填 missing sibling 中 893 个为 execution error；9 个 exit-0 但无 official grade | 缺失主要由执行失败驱动，不是任意抽样 |
| 前瞻 accrual | 47 个 post-mechanism physical runs / 8 tasks；dominant=8/47；距 150 差 103 | `RUN_GATE_WAIT`，不得提前 replay |

这些结果组成同一机制：`V` 的正效应不能抵消 `C` 的选择性缺失；failure-censored source opportunity 是
解释边界，不是另起一条 hurdle-model 主线。主论文应把 `C/V/U` 并列成 feedback frontier，而不是把共同覆盖
子集的 0.9167 外推到全部候选。

## 3. 直接竞品封闭了哪些宽主张

| 一手工作 | 已覆盖 | 我方不得声称 | 仍可防守的窄边界 |
|---|---|---|---|
| [AIRA_2, arXiv:2603.26499](https://arxiv.org/abs/2603.26499) | 80/10/10 Hidden Consistent Evaluation；外部固定 `D_search` 指导搜索、隐藏 `D_val` 最终选择；报告 24h/72h 的整体收益 | 首个可信/隐藏/一致 evaluator，或首次证明 self-report 有害 | 对同一真实 sibling 候选的通道级配对识别、artifact MNAR 与 failure-censored benchmark |
| [RewardHackingAgents, arXiv:2603.11337](https://arxiv.org/abs/2603.11337) | evaluator locking、文件访问记录、tampering/leakage 完整性标签 | 首次 evaluator 隔离、访问审计或可信 reference | 把完整性与真实搜索 choice set、评分可观测性和 predictor estimand 绑定 |
| [FOREAGENT, ACL 2026 / arXiv:2601.05930](https://arxiv.org/abs/2601.05930) | 18,438 global solution pairs、execution-free preference、Predict-then-Verify、端到端 6× claim | 首次执行前比较 MLE 解或首次预测代替执行 | 官方近全连接 pair graph 与真实 sibling graph 的 estimand transport；同一 endpoint scorer 在两种图上的差异 |
| [ArchPilot, arXiv:2511.03985](https://arxiv.org/abs/2511.03985) | 1 epoch/10% 数据、多个 proxy、在线权重拟合、proxy/full 切换 | 首次低保真候选评分或 proxy-guided MLE search | 自由形态 sibling 在固定时间可能完全没有 scoreable observation，以及真实成本/覆盖审计 |
| [KompeteAI, arXiv:2508.10177](https://arxiv.org/abs/2508.10177) | early-stage metric、预测评分与加速 debugging | 首次 early metric、提前终止或执行加速 | external score 与 self-report 的同候选通道差和选择性缺失机制 |
| [SandMLE, arXiv:2604.04872](https://arxiv.org/abs/2604.04872) | micro synthetic MLE、valid-output 与 performance milestone reward | 首次 valid artifact/schema milestone | 不微调底座、真实 MLE search、host/pristine provenance 和 prospective channel replication |
| [Delayed Bandits, ICML 2023](https://proceedings.mlr.press/v202/esposito23a.html)、[Impatient Bandits, arXiv:2501.07761](https://arxiv.org/abs/2501.07761) | delayed reward、intermediate/progressive observations 及其信息价值 | 首次 delayed/intermediate feedback 形式化 | MLE program execution 中 artifact availability 与 score value 的实证数据契约 |
| [AgentExecutor, arXiv:2608.05959](https://arxiv.org/abs/2608.05959) | 通用 partial-code execution 与 context generation | 首次让部分代码可执行 | 完整 MLE 候选产出可由真实任务 grader 比较的预测 artifact，不是一般代码覆盖 |

未发现一篇直接同时覆盖“真实 sibling choice set + physical-run split + 同候选 trusted/self-report 通道配对 +
artifact MNAR/failure status + post-mechanism prospective replication”的论文。这只能表述为截至本次检索的可见边界，
不能写成绝对的“无人做过”。

## 4. 最有希望的正面突破顺序

### A. 前瞻确认 `V(120)`：唯一主实验

保持现有预注册：至少 150 个机制后 physical runs、dominant task <=0.25、每 run 最多两个合格 parent、约 690
个 120 秒 replay。它只确认同候选评分通道，不确认 `C` 或端到端 speedup。47-run 正式 registry 已双跑逐字节
一致并由不导入 producer 的实现复核；当前不允许 replay 或读取 vault。

### B. Score-Channel Audit Card：零 GPU 的 D&B 资产化

把 release validator 固定输出为一张 machine-readable card：physical run、parent choice-set completeness、
`C(tau)`、`V(tau)`、`U(tau)`、execution/failure censor status、gap/noise ceiling、query/init cost、
operator/evaluator hashes 和 prospective boundary。统计原语不申新；贡献是第三方可以在自己的 MLE-agent 数据上
运行同一协议，避免把 global pairs、可评分子集或 fragment split 冒充部署决策。

### C. 方法扩展只在 A 成立后重开

若 `V(120)` 前瞻成立，下一因果问题才是提高 `C(120)` 且不伤害 full quality。schema-first prompt、低保真 rewrite、
runtime-owned probe API 都已有强邻近工作；必须在全新任务/seed 上和 AIRA_2-style external evaluator、ArchPilot-style
proxy、FOREAGENT-style predictor 作固定预算比较。当前不恢复旧 Probe-First/HCE/多保真实验，也不在旧发现集继续
调阈值。

## 5. 当前执行裁决

1. metadata monitor 继续 outcome-blind 累积新归档；每次新 transaction 后重建 run registry，但 150 前不读 vault；
2. 学长锁定的 Qwen3-4B/8B checkpoint 只有在绝对路径、训练配置与 selection receipt 齐全后，才对 frozen
   b0/b1/b2 各一次评分；不得猜路径或看 frozen 选 checkpoint；
3. 不再启动独立的 critic/hurdle/schema-first 付费实验来“寻找正数”；它们会稀释当前可确认主张并增加
   data-dependent research debt；
4. 下一个昂贵动作仍需提交 exact matrix、run/replay 数和 GPU-hour 预算给用户批准。
