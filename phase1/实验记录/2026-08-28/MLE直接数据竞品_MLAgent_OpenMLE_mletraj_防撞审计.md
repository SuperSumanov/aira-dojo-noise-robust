# MLE 直接数据竞品防撞审计：ML-Agent、OpenMLE 与 mle-traj

日期：2026-08-28

本轮只读取公开论文、官方代码仓库与官方数据卡；没有读取 first-960/Target-300 的 label、outcome、prediction、
accuracy 或 utility，也没有调用 GPU/API 或训练模型。结论是主张边界审计，不是“相关工作不存在”的形式证明。

## 1. 三个必须进入正文的直接邻居

### 1.1 ML-Agent（arXiv:2505.23723v2）

[ML-Agent](https://arxiv.org/html/2505.23723v2) 已在 MLAgentBench/MLE-Bench 上收集 9 个任务、10,000 条
最长 15 步/30 分钟的执行轨迹，并用它们做 Qwen2.5-7B 的 SFT 与 step-wise PPO。它把错误、非编辑动作和执行成功后的
任务指标增量统一成 step reward；还明确报告训练任务数、训练样本数和推理前成本。因此以下主张不能再使用：

- 首次收集大规模 execution-grounded MLE trajectories；
- 首次把 MLE 执行经验用于 step-wise learning；
- 首次讨论 MLE agent 的训练/执行成本分摊；
- 首次证明学习过 MLE 经验的小模型可迁移到 held-out MLE tasks。

与我方不同之处是：ML-Agent 的目标是更新 agent policy，训练状态来自线性 expert trajectories，reward 依赖执行后的
metric improvement；它不是在自然搜索树的同一 parent 下，对多个尚未执行的完整候选程序做独立 critic benchmark，
也没有我方 physical-run/comparison-component/time-forward closure 与撤回审计。项目 hard NO 仍禁止照搬其 SFT/PPO
去更新 agent 底座。

### 1.2 Frontis-MA1 / OpenMLE（arXiv:2607.28568）

[Frontis-MA1](https://arxiv.org/abs/2607.28568) 已发布 OpenMLE full stack，把 Draft/Improve/Debug/Crossover 四个
程序演化算子在 execution-grounded SFT/RL 中训练，再接到长程 evolution search；官方
[OpenMLE-SFT-Traces](https://huggingface.co/datasets/FrontisAI/OpenMLE-SFT-Traces) 数据卡列出 26,259 条公开轨迹、
4,891 个 task names。它直接关闭：

- “最大/首个公开 MLE 训练轨迹集”一类规模与先发主张；
- “首次把程序演化 operator 的训练和搜索统一”一类方法主张；
- 把四个 Draft/Improve/Debug/Crossover 操作本身包装成我方新颖性。

OpenMLE 的核心是 actor/operator post-training 与端到端 search utility；我方核心应明确错位为独立 predictor 的
measurement benchmark：在固定 agent/search 产生的真实 choice set 上测执行前排序、初始化/query/执行成本、噪声上界、
pair graph 权重和时间前瞻 transport。两者可互补，但不能声称我方覆盖 OpenMLE 的模型训练规模或端到端成绩。

### 1.3 MLE Trajectory Dataset v1/v3

官方 [mle-traj-v1](https://huggingface.co/datasets/jerryyan/mle-traj-v1) 数据卡列出 7 个 Kaggle 比赛、622 条
human/agent trajectories、15,572 个逐版本代码快照和 14,944 个 transition，并给每个版本连接 held-out score；
其中 agent 侧含 11 个 Codex runs 与 13 个 MLEvolve physical runs（后者线性化为 189 条 root-to-leaf branches）。
它还有 GPT-5-mini 生成的 state/action/intent、magnitude 与 score-effect 标签。

[mle-traj-v3](https://huggingface.co/datasets/jerryyan/mle-traj-v3) 又把人类 kernels 组织成 forest：13,692 human
versions、13,412 canonical-parent edges，加入 37 个 fork 和 113 个 token-Jaccard code-sim edges；agent 侧仍是从
13 个 MLEvolve runs 线性化出的 189 branches，加 11 个 Codex runs，共 1,514 agent versions。

因此以下主张关闭：

- 首个带逐节点分数的 MLE trajectory dataset；
- 首个同时发布完整代码、action/intent 标签和人类/agent 轨迹的数据集；
- 首个把 MLE 代码版本组织成 graph/tree view；
- 单靠“约 1.5 万节点”宣称规模领先。

它与我方的**已证差异**是：v3 的 human forest 含按 fork/code similarity 构造的边，agent canonical tables 把
MLEvolve tree 线性化；我方 canonical release 直接保留 physical run、真实 parent、siblings 与 labeled choice
fragment，目标是 execution-free predictor 的严格评价而非行为标签或人类对照。对方把 per-version score 烘焙进
canonical tables；我方则在前瞻阶段把 outcome vault 与 prediction escrow 隔离到 closure 后一次揭盲。

但 v1 的公开 layout 同时列出每个 MLEvolve run 的 `trajectory.json`、`paths/path_###.json`、逐版本代码和
`tree_summary.json`。原始文件是 gated 的，本轮没有取得授权并检查字段；所以不能从 canonical 线性化外推为“整个
release 无法恢复真实 parent/sibling”，也不能据此声称我方是首个/唯一 true-sibling MLE 数据集。当前精确状态是
`UNRESOLVED_GATED_RAW_TREE_RECOVERABILITY`。

## 2. 更新后的可守主张

不能再把论文写成“MLE trajectory dataset”。更精确的容器是：

> 一个面向自主 MLE 搜索中**真实分支决策**的 Decision Corpus 与 Predictor Benchmark：以同一 parent 下的完整候选
> 程序为评价单元，用 pristine continuous external grade 定义 truth，系统比较 execution-free critics，并对 physical-run、
> config、time-forward transport、pair-induced weighting、噪声、覆盖、查询/初始化/执行成本和撤回链做机器审计。

当前公开、已核验的 canonical 材料中，尚未确认有一组同时提供以下组合：

1. 大量真实、非线性搜索产生的同-parent sibling choice sets；
2. 多 predictor family 在同一 frozen decision pool 上的横向 benchmark；
3. physical-run/config/comparison-component/time-forward 隔离；
4. outcome-blind accrual、prediction escrow 与独立 closure receipt；
5. query/init/full-execution 成本、regrade noise 与 pair-graph weighting 联合账本。

这仍只是基于当前检索的差异化判断，且 mle-traj raw tree recoverability 未决；正式论文不写 “first/only”，也不把
“公开 card 未说明”改写为对方最终论文或 gated raw release 明确没有。

## 3. 对实验路线的直接影响

1. **保住 true branching，不再把树线性化。** 我方 canonical release 直接给真实 siblings/choice fragments 是确定
   资产；但它相对 mle-traj 是否为独有差异，要等 gated raw tree 审计。发布时必须同时给 parent/run/component
   identifiers 与可复建边表。
2. **把 predictor study 做成主贡献，而非附录。** ML-Agent/OpenMLE 强在 actor learning，mle-traj 强在行为标签；我方
   的空位是 decision-time critic 的公平横评、成本与 transport。
3. **把 linearization 当预注册 sensitivity。** closure 后，同一 scorer 可比较 true-sibling estimand 与线性
   parent-child/人为 cross-run estimand，量化“把树压成轨迹会怎样改变模型排序”；不能用 sensitivity rescue frozen primary。
4. **规模主张用 physical decision units，而不是节点总数。** 正文同时报告 physical runs、真实 parents、choice sets、
   sibling pairs、tasks 与 generator/config strata，避免与 26k linear traces 或 15k human versions做误导性单列比较。
5. **外部 transfer 只作后续扩展。** 若取得 mle-traj 的正式访问，先锁 revision/license/hash，并按 13 个 physical
   runs 而非 189 paths 重建 parent/sibling；只有结构资格门通过后，才可在不混入主 estimand 的前提下测试 critic
   transport。资格不足时只作 domain-shift 结构描述，不运行效果测试。

## 4. 当前正方向结论

这次检索不是把主线推翻，而是把真正有价值的部分剥离出来：**“轨迹很多”已不新；我方已经落地的是大规模 physical-run
decision provenance、结果盲 closure 与成本感知 predictor measurement 的组合。** true-sibling 相对 mle-traj raw
release 的独有性保持未决，不拿未获授权的数据替自己制造正结论。当前最优动作仍是完成 full-release split certificate、
继续 first-960 outcome-blind accrual，并把最终 predictor 表严格组织成 provenance-bound sibling-fragment benchmark。
