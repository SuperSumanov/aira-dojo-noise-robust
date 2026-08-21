# Source-choice：FOREAGENT 直接竞品与边界修正

日期：2026-08-22。状态：结果前 related-work 审计；本记录形成时，固定 TF-IDF 的正式 OOF 尚未输出结果，
frozen/extension label vault 均未读取。

## 结论先行

FOREAGENT / *Can We Predict Before Executing Machine Learning Agents?* 是当前路线的直接竞品，而不是泛相关工作。
它已经定义 Data-centric Solution Preference、发布 MLE solution preference corpus，并把执行前 pairwise prediction
接入 Predict-then-Verify 搜索。因此下列 novelty 表述立即关闭：

- 首次在执行前判断两个 MLE 解谁更好；
- 首次用静态/LLM preference prediction 减少 MLE-agent 执行；
- 首次发布 MLE solution preference corpus；
- 只凭 predictor accuracy 申方法 novelty。

这不关闭我们的 D&B 路线，但把可防守边界收窄为：**真实 parent/source decision unit、候选与 physical-run/task
依赖显式建模、execution cliff/unknown-preserving 标签、run-clean 与 temporal frozen 评估、query/init 成本和严格
前瞻 utility bridge**。其中任何 predictor 正结果都只能作为这套 benchmark/integrity 贡献中的一项，不能单独申
“predict-before-execute”。

## 一手证据

固定检查对象：

- 论文 v2：arXiv:2601.05930，2026-04-07 修订；ACL 2026 long paper；官方仓库标注 SAC Highlight；
- 官方代码仓库：`zjunlp/predict-before-execute`，审计 HEAD
  `c4d52cf99bd870d830b456ac7c0684aec1aef375`；
- 官方 Hugging Face：`zjunlp/PredictBeforeExecute`。

论文与官方 release 明确报告：26 tasks、895 solutions、18,438 pairwise comparisons；DeepSeek-V3.2-Thinking
accuracy=61.5%；ForeAgent 在 5 个任务、每任务 3 个独立 runs 上报告 6x convergence acceleration、3.2x search
breadth 与 +6% Beat Ratio。它还报告 within-trajectory accuracy=60.4%、cross-trajectory accuracy=61.7%，但其
cross-trajectory 定义合并“不同 run session **或不同 task**”，不等价于固定 task 下的 physical-run-heldout
评估。

官方 `prepare_bench_subset/group.py` 不是从真实 parent choice set 取一个决策，而是：

1. 对每任务保留最多 50 个可评分 solution；
2. 使用 `itertools.combinations(range(len(filtered)), group_size)` 枚举所有组合；
3. `group_size=2` 时，同一个 solution 会重复出现在多个 pair；
4. 过滤 `submission_exists=false`、`valid_submission=false`、缺 score 与近似同分组合；论文附录同时说明 syntax/
   runtime crash 被过滤。

因此 18,438 是派生 comparison rows，不是 18,438 个独立 agent 决策或独立 execution units。对 Hugging Face
自动转换 Parquet（8,456,690 bytes，SHA-256=
`79363b7ef0b6154061f18e81f6c6fdf380e71ae3f1d7b9a262cc79acb08f0b5f`）的只读结构复核得到：18,361 rows、
18,361 unique canonical pairs、895 unique solution paths、26 connected components；solution degree median=49、
mean=`41.03016759776536`、max=49。26 个 component 中 7 个为完整 clique，按各 component 节点数计算的潜在边比
release 多 425 条。该复核不读取 solution code，只读取 `paths/best_index` 两列。

官方
`grade/util/report.py` 同时输出 record-level micro mean 与 per-task mean；当前 release 未在该实现中提供按候选身份、
trajectory/run 聚类的区间或检验。Hugging Face viewer 当前只暴露一个 `train` split，并显示 18,361 rows，与论文
18,438 的口径有 77-row 差异；本审计没有下载 158 GB release 去判断差异来源，因此只记录、不解释。这里不据此
否定其 LLM 能力结论，只说明它和我们的 estimand、独立性单位与失败
选择机制不同。

官方链接：

- https://arxiv.org/abs/2601.05930
- https://github.com/zjunlp/predict-before-execute
- https://raw.githubusercontent.com/zjunlp/predict-before-execute/main/prepare_bench_subset/group.py
- https://huggingface.co/datasets/zjunlp/PredictBeforeExecute
- https://huggingface.co/datasets/zjunlp/PredictBeforeExecute/resolve/refs%2Fconvert%2Fparquet/default/train/0000.parquet

## 与当前资产的精确差异

| 轴 | FOREAGENT release | 本项目当前 source-choice S2 v2 |
|---|---|---|
| 决策单位 | 同任务 solution pool 的组合 pair | logged parent 的真实 source choice set |
| 基础对象 | 895 solutions 派生 18,438 pairs | 3,000 groups / 8,027 candidate slots |
| 候选复用 | 同一 solution 进入多个组合 | train 的 5,739 candidate IDs 唯一，cross-run/task code hash=0 |
| 失败节点 | syntax/runtime crash 过滤 | status-certified invalid 与 unknown 显式保留 |
| 依赖控制 | within/cross trajectory 描述；cross 混合不同 run 或 task | physical-run split、task-LOTO、run-cluster/task-cluster inference |
| 冻结评估 | 官方 HF 当前单一 `train` split；LLM 为 inference-only | train/frozen/temporal extension，winner vault 分离 |
| 输入/成本 | task + verified data report + 两份 code，强 LLM | 当前门为 code-only 轻量 TF-IDF；query/init 成本单列 |
| 系统收益 | 已报告 5 tasks x 3 runs 的 ForeAgent utility | 尚未证明；必须另做预注册前瞻 utility bridge |

“候选不复用”仅指当前 S2 v2 train choice-view 的 5,739 candidate IDs 已验合同；完整 release 另有 8,027 slots，
不得把 train-only 的 cross-run/task code-hash 结论未经复核外推到其他 role，也不得外推为
原始 16,012-card corpus 的所有节点都只出现一次。FOREAGENT 的 HF 单 split 也不能被写成“没有任何内部
holdout”；准确说法是公开 dataset viewer 当前只暴露一个 18.4k-row train split，而论文主体是 inference-only LLM
评估。

## 对当前实验的裁决

1. 正在运行的固定 TF-IDF OOF 不因竞品而作废：它回答的是 task-LOTO/run-OOF 下，真实 source choice 是否有
   廉价、跨依赖单元的预执行信号；FOREAGENT 没有给出这个 estimand。
2. 若 OOF 为 `NO_NARROW_POSITIVE`，不得借竞品缺口追子集或改模型；source-choice 仍可作为 D&B 数据资产，方法
   正结论关闭。
3. 若 OOF 为 `GO_CROSS_TASK`/`GO_RUN_ONLY`，先执行已冻结的 recovery-provenance sensitivity，再产生 label-free
   frozen/extension prediction escrow；不得立即写 utility。
4. frozen/extension 只能一次性独立揭盲；最终方法主张还必须有真实搜索或 replay 的预算等价前瞻桥。因为
   FOREAGENT 已有系统收益，只有离线 accuracy 不足以形成方法突破。
5. 论文 framing 改为与 FOREAGENT 互补且更严格的 benchmark/integrity study：FOREAGENT 证明该想法有用；我们
   问在真实 sibling/source decision、失败选择与依赖稳健协议下，哪些结论仍成立，并发布可复核资源。

## 新正方向优先级

在不看 OOF/frozen outcome 的前提下，后续正方向固定为：

1. 先过当前 OOF 与 recovery-mix 双门；
2. 用既有 escrow 做 frozen + temporal extension 一次性复制，不调模型；
3. 只在前两项通过后，预注册等执行预算的真实 source-selection replay，报告 best-of-budget、regret、失败避免率、
   wall-clock、query/init 成本与 run/task-cluster uncertainty；
4. 把 FOREAGENT 作为最直接 baseline/related work，不能只列 AIRA-dojo、SciNav、ArchPilot。

这条路线的正面价值不是“竞品没做预测”，而是把一个已证明有潜力的机制升级为真实决策、失败不删、依赖稳健、
时间前瞻且可审计的 benchmark 与验证标准。
