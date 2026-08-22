# Rehearse：执行前选择直接竞品与 score-channel 主线边界

日期：2026-08-23。状态：`PREEXECUTION_MEMORY_METHOD_NOVELTY_CLOSED_SCORE_CHANNEL_RETAINED`。本审计没有
读取 prospective/frozen outcome，没有调用 API、训练模型或提交 GPU。

## 1. 必须纳入的直接工作

[Rehearse](https://arxiv.org/abs/2607.27687v1) 于 2026-07-30 发布。它从 39 个 paper-derived AutoSOTA
任务构造 296 个严格 same-baseline 的主 pair：一边严格改善 metric，另一边 crash/timeout/invalid/non-improvement；
另有 70 个 worked-vs-worked 辅助 pair。候选以 outcome-blind description/hypothesis/implementation 呈现，pair 两个顺序
都判断，只有一致时才给 verdict。

论文报告：无记忆 LLM judge 在主 pair 的 selective accuracy 为 79.5%；当 accepted baseline 已累计至少三个成功修改时，
无记忆 selective accuracy 从浅层 82.8% 降至 56.9%，coverage 却升至 85%。检索同任务相似历史修改及二值 outcome 后，
深层 selective accuracy 为 83.5%。端到端实验是三种 autoresearch loop、每配置五个 seed、合计 4,000 个固定训练 run；
Rehearse 在同一 training-run 数下改善最终 endpoint。论文同时明确把
[FOREAGENT](https://aclanthology.org/2026.acl-long.182/) 视为最接近的 completed-solution 先例。

因此以下主张都已关闭：首次在 autoresearch 中执行前 pairwise 选择、首次用候选相关 outcome memory 改善选择、首次在
固定训练-run 数下证明这种 controller 有端到端收益。不得把本项目的 history retrieval、Predict-then-Execute 或
global→local calibration 包装成方法首创，也不得借用 `confidence cliff` 作为新术语。

## 2. 与本项目的不可混同之处

Rehearse 的强结果不能直接外推为我方真实 sibling critic 应当很强，也不能被我方旧随机结果直接否定：

1. 它的主 estimand 是 worked-vs-did-not-work 二分类；我方真实 Improve/sibling 多为两个已执行、均可用且 grade
   接近的候选。它自己的 worked-vs-worked probe 也单列且更弱。
2. 它判断尚未应用的修改 rationale；我方 benchmark 主要判断完整 code/node。v11 release 的 16,012 cards
   顶层只有 `code/id/label/lineage/obs/provenance/run_id/task`，嵌套 `obs` 也只有
   `error/fidelity/runtime_s/stdout_tail/val_at_low/val_curve`，没有原生 `analysis/plan/hypothesis/implementation`。
3. 它的 366-pair benchmark 没有我方 physical-run/tree lineage、真实 logged sibling choice set、repeat-grade noise、
   score-channel missingness 与 run/task/parent 三层依赖审计。
4. 它把 proposal/judge inference 排除在 training-run budget 外；我方 NAS-style 容器要求初始化、query 与 execution
   cost 分开报告。
5. 它诚实承认 depth 是 observational、endpoint 是 serving alias 而非冻结 checkpoint，且 live loop 中 model 与 task
   配对而非 crossed；这些不削弱其结果，但限制可比较范围。

v11 schema 审计先对完整 305 MB 语料做高置信 credential scan，三类命中均为 0，随后只输出字段名/类型/计数；
cards SHA-256=`6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75`，16,012/16,012
可解析。由于 authentic pre-execution rationale 支持为 0，当前不允许为追随 Rehearse 临时事后生成 rationale 并称作原生
决策信息，也不启动 API judge。

## 3. 对当前路线的裁决

1. **score-channel 前瞻主线保留。** Rehearse/FOREAGENT/RPM 都没有比较同一短时执行预算下 pristine
   `submission.csv` 外部分、stdout 自报分与选择性可观测性，更没有机制 commit 后新 physical runs 的 append-only
   identity closure。因此 150-run future truth-support/score-channel 协议仍是当前唯一主实验。
2. **global→local 五臂只作 D&B 机制消融。** 它能解释 global capacity scaling、local overtraining 与真实 label
   information，但不是 transfer 或 memory 方法论文。
3. **“决策难度阶梯”只保留为数据分析候选。** 494 个 failure-vs-success parent-matched pairs 已是正面数据资产，
   但固定静态 TF-IDF 的 task-LOTO micro 仅 0.5243、CI 跨 0.5；不能因为 Rehearse 的不同信息条件就追认“粗筛已解决”。
   若未来扩展，必须先找到结果前保存的 authentic rationale，再预注册同一模型、同一信息、同一依赖单位下的
   failure-filter→worked-vs-worked→viable sibling 阶梯；否则停止。
4. 论文定位进一步明确为：FOREAGENT/RPM/Rehearse 给出正面 deployment systems；本项目用更大的物理搜索树语料检验
   这些正结论依赖何种 pair construction、信息通道、执行状态、成本口径与审计契约。

## 4. 一手来源

- Rehearse v1：https://arxiv.org/abs/2607.27687v1
- FOREAGENT / ACL 2026：https://aclanthology.org/2026.acl-long.182/
- AI Research Preference Models：https://arxiv.org/abs/2608.13940
