# Choice-set fidelity：当前主张边界与可证伪结构

日期：2026-08-14。本文晚于旧 HCE、多保真、probe 与泛化的 critic 叙事；稳定主线仍是 run-clean、
decision-local 数据/benchmark 和 first-960 prospective confirmation。

## 1. 不能声称的新颖性

“候选集采样会改变离线排序指标，甚至反转算法排名”不是新定理。推荐系统中：

- [Evaluation Metrics for Item Recommendation under Sampling](https://arxiv.org/abs/1912.02263) 已证明
  sampled metrics 与完整指标不一致，模型相对排序甚至在期望上也不保留；
- [Candidate Set Sampling for Evaluating Top-N Recommendation](https://arxiv.org/abs/2309.11723) 已系统研究
  candidate-set 选择、size 与 popularity bias 的交互；
- [A Case Study on Sampling Strategies for Evaluating Neural Sequential Item Recommendation Models](https://arxiv.org/abs/2107.13045)
  已展示 uniform/popularity sampling 都可能改变模型排名。

NAS 侧也已有 [How Powerful are Performance Predictors in Neural Architecture Search?](https://openreview.net/forum?id=6RB77-6-_oI)
同时比较 rank/correlation、search utility、initialization time 与 query time。因此不能把“不能只看全局 accuracy”、
“要报查询成本”或 Simpson-style ranking reversal 本身申成方法 novelty。

## 2. 可防守的领域组合

我方最小主张是把上述通用风险第一次（截至当前可见检索，投稿前继续更新）做成真实 MLE-agent search 的可执行
数据契约：

1. sampling unit 是 flatten 前的 physical run，而不是被剪枝后的 fragment；
2. query unit 是真实 parent 下发布的 labeled sibling fragment；对 lineage 可恢复部分另发完整 source sibling
   identity registry，而不是把有限标签 fragment 冒充当时 operator 的完整 choice set；
3. endpoint reuse、orphan parent、set completeness、gap、task/run 支持与四层 split isolation 都机读；
4. predictor 同时报 pair-micro、parent-equal top-1/utility、run/task clustered uncertainty 与 init/query cost；
5. label repeatability 是独立 attestation，明确区分直接 agreement 与模型反演；
6. 机制冻结后用新 physical runs 做 prospective evaluator-channel confirmation。

贡献点是 **MLE 搜索决策的 domain-specific benchmark standard + 数据资产 + 实证 estimand shift**，不是发明
candidate-set bias。

## 3. 冻结 estimands

令 `u` 为 physical run，`d=(u,parent,budget,operator_contract)` 为决策点，`C_d` 为 source sibling identities，
`L_d\subseteq C_d` 为 retained finite labeled siblings，`E_d` 为 `L_d` 内发布的比较边。当前可估的是 labeled-fragment
parent-equal risk，而不是完整 `C_d` utility：

\[
R_{decision}(f)=\mathbb E_d\left[|E_d|^{-1}\sum_{(i,j)\in E_d}
\mathbf 1\{f_i-f_j\text{ 与 }y_i-y_j\text{ 异号}\}\right].
\]

任意 global pair sampler `q(i,j|task)` 估计的是另一个量 `R_q(f)`。只有在 conditional errors 不随
run/parent/gap/endpoint degree 变化，或 `q` 恰好重现 deployment choice-set weights 时，两者才可互换；当前数据
已经不满足这种无条件等价。正式论文不能把 pair-micro accuracy 继续放在唯一 headline。

## 4. 当前证据与证据等级

- physical-unit evidence：旧 fragment split 让 99.7% in-task test pairs 与训练共享 run；run-clean 后旧 L1
  从 0.776 降至 0.6493。该量是历史审计，不与 v11 OOF 混成同一实验。
- choice-set composition：verified v11 frozen b0 为 1,498 pairs / 845 parents / 92 runs / 22 tasks，
  `gap<1e-2` share=`0.5013351134846462`；train--frozen 在 pair/endpoint/parent/run 四层均为 0 overlap。
- graph interaction（描述性、非确认）：同一 OOF endpoint scores 下，char-TFIDF 在 sibling/cross-run task macro
  为 `0.5284907717433142/0.5814158858170438`，static LR 为
  `0.5389068809808808/0.49652226450484627`，模型排序发生反转；预注册 universal-inflation gate 没过，故不能
  写成所有 predictor 都被 global pairing 乐观放大。
- label quality：v2 的 original-vs-first-regrade raw agreement 为 `0.9658601259529334`，task-cluster CI
  `[0.9438143714671886,0.9913402891372938]`；frozen b0 transport 仍带 10→22 task extrapolation，不能称全任务
  empirical ceiling。
- prospective：external submission score 对 stdout 的发现集优势仍只是线索；first-960 未收够前没有确认结果。

## 5. 杀死条件与正面突破门

以下任一情况会杀死强主张，而不是靠换阈值补救：

1. first-960 的新 run 支持不足、被单任务主导，或 external-score 优势不复现；
2. 用新 run 的冻结 predictor 比较后，choice-set graph 不再改变模型相对排序或 deployment utility；
3. 未重评任务出现显著更低的 repeatability，使“噪声不是主因”不能 transport；
4. parent-equal utility 与 pair metrics 的差异可完全由预注册 gap/task weights 解释，且 audit protocol 不再提供额外
   决策信息。

若 prospective 复现，主线正结果是“常用评测 target 与真实 MLE search decision 不同，并会改变方法选择；我们
发布可复核契约和新 run 确认”。若不复现，数据/协议资产仍可发布，但不能把 discovery ranking reversal 升格为
普遍规律。

Balanced continuation E1-Q 是独立的 policy-indexed label-feasibility 支线；无论其结果如何，都不能替代上述
first-960 主确认，也不自动授权 E2/E3。
