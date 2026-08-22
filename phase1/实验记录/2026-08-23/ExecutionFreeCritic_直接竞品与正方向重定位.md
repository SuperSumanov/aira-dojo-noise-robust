# Execution-free critic：直接竞品、未覆盖缺口与正方向重定位

日期：2026-08-23。状态：`GENERIC_TRAINED_CRITIC_NOVELTY_CLOSED_MLE_DB_FRONTIER_RETAINED`。本记录只做一手
文献核查与已有结果边界整理；没有读取 future/prospective truth、没有打开新 archive payload、没有训练模型、没有
提交 GPU，也没有调用付费 API。

## 1. 最直接的新竞品及其真实覆盖范围

[Reward-Free Evolving Agents via Pairwise Validator](https://arxiv.org/abs/2607.14408)（arXiv:2607.14408v1，
2026-07-15）把 frozen LLM pairwise validator 接入 GEPA、ADRS 和 ShinkaEvolve。它既研究 parent-vs-child
accept/reject gate，也用 Soft Elo/Plain Elo 让 pairwise verdict 驱动 parent selection；代码 substrate 使用
Qwen3-8B agent，并在 ADRS/ShinkaEvolve 的四个代码任务上报告结果。因此以下宽主张已经关闭：

- 首次用 pairwise judge/critic 接入 self-evolving agent；
- 首次用 pairwise verdict 做代码候选 gate 或 parent selection；
- 首次证明 pairwise gate 能在代码演化中达到或超过 scalar-reward baseline；
- 把普通 Elo、pairwise gate 或 frozen LLM judge 本身包装成我方方法 novelty。

这篇论文的代码表也不能被误读成“完全 reward-free 方案在所有代码任务都赢”。其 10 个 engine×task×validator
cells 中，主要正结果由 `Direct + full reward` 承担（5/10 cells）；full-reward baseline 仍在 txn_scheduling 与部分
signal_processing cells 领先。论文公开了 prompt-side Soft-Elo 的三 seed 超参 sweep，但主代码表没有给出我方所需的
physical-run/task-cluster uncertainty、噪声上界或一次性 frozen-test contract。这个差异只能用于说明评估协议不同，
不能用来贬低其方法结论。

## 2. 它也部分覆盖 execution-free：真正未覆盖的是 learned execution-grounded critic

不能把这篇工作简单描述成“仍须执行全部候选”。在 prompt substrate 上，validator 明确看到 parent/child 在 train
minibatch 上的 outputs；其 prompt-side 调用分解中，普通 validator-gated 条件约为 full-reward baseline 的 `1.7×`
LLM calls，Elo 条件约为 `2.4×`。但代码 substrate 的纯 `Direct` arm 不使用 reward signal，validator 直接比较
parent/child program candidate；即使 `Direct + easy/full reward` 仍使用 proxy/full evaluator，**通用 execution-free
code pairwise judge/gate 的主张也已经关闭**。论文没有给出足够实现细节让我们断言纯 Direct 在每轮执行了候选；因此
不得以“他们在线执行、我们不执行”作为总区别。

相对这篇 pairwise-validator 竞品仍有一项差异：我方在两个候选尚未执行时读取 task/context/code，使用历史 pristine external evaluator 的
执行结果离线训练一个可摊销 critic；竞品使用 frozen、无需训练的通用 LLM validator，没有研究 execution-grounded
critic 的监督规模、模型容量、校准、时间外迁移与 query/init 成本曲线。因此问题必须改写为：

> 在真实 MLE-agent sibling 决策上，历史 execution-grounded 的 learned critic 何时优于同输入、training-free 的
> source-code LLM validator；这种优势是否随 critic 容量增长，并能否以更好的校准/摊销成本迁移到时间更晚、不同
> generator 产生的候选？

与这篇竞品的精确差别不是“能否在执行前比较”，而是 **training-free judge 与 trained surrogate 的能力—成本边界**。
现有 deployment-cost attestation、median execution time、query/init 分账、真实 execution labels、噪声上界与
NAS-Bench-style tabular replay 是我方的证据基础。

## 3. 其他直接边界

以下一手工作继续关闭更宽的方法包装：

- [Learning Code Preference via Synthetic Evolution / CodeFavor](https://arxiv.org/abs/2410.03837) 已训练 pairwise code
  preference models，并建立代码 preference benchmark；“首次训练代码偏好模型”关闭。
- [Steer, Don't Solve](https://arxiv.org/abs/2606.21811) 已把 SFT 训练的小 critic 接入 frozen code agent，比较同尺寸
  untrained critic，报告跨两个 unseen agents 的迁移以及 30--92× teacher-cost reduction；其中一个 agent 上同时提高
  resolve rate、降低总成本。因此“首次训练小 critic 帮助大代码 agent”“首次 trained-vs-untrained critic 正结果”与
  “首次 critic cost--performance Pareto”全部关闭。它是 intra-trajectory strategy feedback，不是我方 final-candidate
  sibling ranking，但足以关闭宽 critic 叙事。
- [RewardCode](https://openreview.net/forum?id=zpsYG8fYc8) 已用执行验证的代码偏好对训练通用 code reward model，并面向
  candidate scoring/test-time selection；配合既有 Themis/APLOT 等，通用 code-RM、pairwise-RM 与模型 scaling 首创关闭。
- [More Convincing, Not More Correct](https://arxiv.org/abs/2607.05904) 已在代码与竞赛数学 best-of-N 中复现
  reference-free judge 的 plausibility/correctness 偏离；“首次指出 frozen judge 缺少可靠 correctness anchor”也关闭。
  它反而说明我方 pristine hidden execution anchor 是必要评估设计，但不是概念首创。
- [Solving the Granularity Mismatch / HPL](https://arxiv.org/abs/2510.03253) 已联合 trajectory/step/group preference 与
  curriculum；“首次 global→local 或多粒度 preference curriculum”关闭。
- [DIAL](https://openreview.net/forum?id=uqn5H9v1mv) 已研究 source→target domain 的 reward-model transfer；通用
  domain-adaptation novelty 关闭。
- 既有 NAS predictor suite、BRP-NAS、FOREAGENT、AI Research Preference Models 又分别覆盖 predictor 成本、binary
  relation predictor 和 MLE candidate selection。不得申 pairwise、ranking、transfer 或执行前选择的单点首创。

因此 global→local 五臂只能是**机制消融**：判断真实 global quality label、unique-code regularization 与 local-repeat
overtraining 各自贡献多少，不能升级为新训练算法。

## 4. 当前最有希望的正面突破：MLE-specific clean capability frontier

这条线不能写成新 critic 方法；它是 D&B 论文中的 MLE-specific empirical frontier。新的论文主图候选应是一个二维
frontier，而不是再发明 gate：

1. 横轴是总决策成本：初始化、单 pair query、必要 task-output/execution 和在线 judge 调用全部计入；
2. 纵轴是部署价值：run-clean sibling accuracy、top-1 regret、固定执行预算下 best-found grade；
3. 曲线同时放 static/TF-IDF、frozen LLM validator、不同规模的 learned critic，以及 external execution oracle；
4. 再按 candidate generator/client、task、真实 grade gap 与 execution status 分层，检验 critic capability 与 candidate
   difficulty/generator capability 的交互。

这能形成正面结果的三种合法形态：

- **scaling positive**：clean learned critic 随规模稳定提升，并在同池、同成本口径下超过 static/frozen judge；
- **amortization positive**：即使 pair accuracy 提升不大，在长执行任务上仍改善固定 GPU·时的 best-found grade；
- **routing positive**：不同方法各自在明确分层占优，简单的结果前 routing rule 形成更好的 cost–utility Pareto frontier。

第三种只能在 train/dev 上冻结 routing rule 后一次打开新 frozen cohort；不得看 frozen 结果后按 task/gap 挑赢家。
竞品结论中也把 validator capability 与 agent capability 的深入交互列为开放问题，但我方不写 `first`，只陈述精确
MLE execution-grade、physical-run 与成本口径差异。

## 5. 最小确认顺序（当前不授权长实验）

### S0：身份、时间与成本闭合，0 GPU

- 等待 current future identity cohort 从 33/300 闭合；truth vault 继续封存；
- 取得学长 producer provenance、exact experiment/run split、真实 G0 wall time 与 checkpoint recipe；
- 只按 outcome-free metadata 检查 generator/client/model strata 是否有足够 run/task 支持；不足则不做交互矩阵；
- 冻结 predictor 输入可见性：execution-free arms 不得读取 stdout、submission、runtime、exit status 或 workspace evaluator。

已完成的 schema-only 审计给出一个明确阻断：绑定 33-run receipt 的 11 份 `source_provenance.json` 共 33 records、
0 parse errors、1 种 schema，但 `client/model/generator/hardware/time_limit/execution_timeout` 六类字段均为 0/11。
审计双跑逐字节一致，script/output SHA-256 分别为
`e293209b7a10002d47d16fee6dfcf2a80b0053e492924f3094d49931f22ff003` /
`caa59456c864f07770e73fcb4a7fe5565c93bb7519b44b2faa873aafa1905589`。因此 current cohort 继续只服务 score-channel，
不能承载 generator-capability interaction；后者必须另冻 credential-safe config-provenance sidecar，不能结果后回填或
改变 33/300 协议。证据：`phase1/results/future_provenance_schema_only_20260823/`。

### S1：一次性 clean capability curve

- 先在 train/dev 确认可训练性和规模候选；所有 checkpoint hash 同时锁定后，才一次打开 physical-run-disjoint frozen；
- primary 为 task-clustered sibling accuracy；parent/run cluster 为敏感性；同时报告 task macro、LOTO、seed dispersion、
  coverage、abstention 与相同 pair pool 的 paired difference；
- model-size 曲线至少三事前 seed；不得复用已反复读取旧 2,087-row test 的 4B/8B checkpoints；
- frozen LLM validator 只能看与 critic 相同的执行前输入。若让它看 outputs，必须单列为 post-execution comparator，
  不能与 execution-free critic 混报。

### S2：离线 tabular search utility

- 在完整 sibling outcome 已知但对 selector 结果前封存的 cohort 上，固定预算模拟“只执行 critic 选中的候选”；
- 逐 run 报 best-found raw grade/regret、执行次数、失败率与 wall-time；以 run 为随机化/推断单位；
- oracle、random、static、TF-IDF、frozen judge、learned critic 使用相同候选池和预算；所有 orientation receipt 先锁定；
- 只有 S1/S2 同时过门，才申请 live A/B；离线 replay 不得写成真实在线因果收益。

### S3：单 pivot live A/B（需另报矩阵与 GPU·时）

- 只在 aira-dojo 上，固定 operator/base agent/task/budget，唯一改变 selector；
- 预先选择一个模型规模，不在同一 frozen test 上结果后扩模型；
- learned critic 必须相对 random/TF-IDF 和同输入 frozen judge 同时改善 task-cluster CI，并在固定执行预算下提高
  best-found grade，才可写端到端正结论。

global→local 五臂不与 S1 同时铺满模型矩阵。先确认 clean scaling/transfer；只有通过后，才在一个事前 pivot 模型上
运行 `L1/Lbudget/Gbudget/G→L/Ghash→L`，回答机制问题，避免把算力耗在已关闭的方法 novelty 上。

## 6. 当前裁决

1. Pairwise-guided code evolution 的宽方法 novelty 已被直接竞品关闭。
2. 通用 execution-free code judge、trained code critic/RM、跨 agent transfer 与 cost Pareto 都已有先例；当前可守的
   是 **MLE-agent physical sibling 上的 clean scaling、校准、时间外迁移、噪声上界与摊销边界**，作为 D&B
   benchmark 正结果，而不是新方法。
3. 学长 0820 scaling 仍是该方向最强探索信号，但 test-touched、两/一 seed 与 provenance 阻断不变，不能追认。
4. 当前不提交 GPU：exact fresh split、producer provenance、G0、模型×seed 矩阵与总 GPU·时尚未闭合。
5. 继续 current score-channel future cohort；它提供时间更晚、结果盲、raw-grade 可辨识的 confirmation substrate，
   不因本次 literature update 改 protocol、门槛或提前开 truth。
