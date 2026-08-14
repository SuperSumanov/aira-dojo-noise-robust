# Label Repeatability Attestation v2 预注册

日期：2026-08-14。状态：本文写在 v2 的 v11 分桶结果、bootstrap 区间与 sensitivity 结果生成之前。
本轮为 CPU-only、0 GPU、0 API；不训练模型，不读取 endpoint code/observation，也不改变论文 frozen split。

## 1. 为什么旧数字不能直接进入 release card

旧 `noise_ceiling.py` 的 cross-session raw agreement `0.9649` 是可复核的描述量，但其 300 次 node
bootstrap 创建了重采样集合却没有用于后续计算，因此打印出的区间不具备 bootstrap 含义。另有 9 个
`(card_id, rep)` 在 append-only 重评日志中出现多次成功执行且分数不同；把它们静默去重或当成普通独立
replicate 都需要显式 sensitivity。修复不得追溯改写旧 artifact；v2 另立协议与输出目录。

## 2. 冻结 estimand 与输入

主 estimand 是原始评分与按输入/行号排序的第一次成功重评在同任务节点对上的**排序一致率**。两边都是
单次、跨时段评分；它直接衡量 pair label 的 repeatability，不等同于预测器 accuracy ceiling。只有在
“给定 gap 后两次单次标签误差独立、可交换且关于真实顺序对称”的工作模型下，才把一致率 `r` 转成单次
标签正确率：

\[
a=(1+\sqrt{\max(0,2r-1)})/2.
\]

发布字段必须称为 `model_inferred_single_label_accuracy`，不得省略模型假设或直接称“真实 ceiling”。

冻结输入为全部 `phase1/regrade_results*.jsonl`，以及已通过 Decision-Corpus Audit v1 的九个 v11 pair
sets。排序一致性在同时翻转两次标签方向时不变，因此不读取 `task_orientation.json`。pair 文件只读取
`task` 与 `gap_raw`，其路径、规范化 LF
SHA-256 与行数必须和 audit card 一致；不读取 `better/worse` 的标签方向。

## 3. 重复记录、配对与 sensitivity

- primary 使用 append-only 日志中每条 finite successful execution record；物理记录身份是
  `(input-order, line-number)`，不能用重复的 `rep` 元数据覆盖；
- 每个 card 的 task 与 finite `orig_graded` 必须一致，至少有两个成功重复才进入；
- primary label 比较 `orig_graded` 与该 card 第一次成功重评；任一侧 tie 的节点对
  不进入分母；
- secondary-1 比较 `orig_graded` 与所有成功重评的均值，但由于单次与均值不可交换，**不得**对它做单次
  准确率反演；secondary-2 比较每个 card 按输入与行号排序的前两次成功执行；
- 固定报告 `all_successful_records`、每 `(card,rep)` 首条成功、末条成功三种 sensitivity；不按结果选择。

## 4. gap 曲线与 transport

gap 固定为两个 card 的 repeat-mean 绝对差；桶沿用 Decision-Corpus Audit v1：
`[0,1e-4,3e-4,1e-3,3e-3,1e-2,3e-2,1e-1,3e-1,inf)`。

gap 固定为两个 card 在**除去第一次成功重评后**其余成功重评均值的绝对差。它既不含 original，也不含
primary 的 first-regrade label，只用于分层；至少两次成功重复的门正是为此设置。目标 pair 的 `gap_raw` 是
冻结数据中的观测 gap，因此 transport 仍需声明“reference-gap 曲线可搬运到 observed-gap 分布”的近似。
每桶先记 raw successes/trials，再以 trial 数加权的 PAVA 拟合随 gap 非递减的 repeat agreement。空桶只继承
最近的更小-gap 已观测桶，开头空桶置 `0.5`；所有拟合值在转换前下截于 `0.5`。这条规则不得在看见结果后
改变。九个目标 pair sets 均报告：

1. 固定目标 gap 分布下的 transported repeat agreement；
2. 工作模型下的 transported inferred single-label accuracy；
3. 目标 pair 中属于 10 个（实际数量由输入重算）重评任务的覆盖率与同任务覆盖子集 transport；
4. 是否向未重评任务外推。

## 5. 推断、独立复核与解释门

- primary CI 针对 `original vs first successful regrade`：固定 seed `20260814`，2,000 次 task-cluster bootstrap；每次有放回抽取全部重评任务，保留
  被抽 task 的全部 dyadic pairs，再重拟合 PAVA；目标 v11 gap 权重固定；
- 任务数少、pair 共享 endpoint，因此禁止使用 pair-i.i.d. binomial CI 作为 primary；
- verifier 不 import producer，须从 hash-bound 输入独立重建 usable cards、重复元数据冲突、节点对、PAVA、
  transport、sensitivity 和 bootstrap；篡改任一发布量必须失败；
- 若 raw cross-repeat agreement 很高而 task-bootstrap/未覆盖任务外推很宽，只能写“在已重评任务上标签噪声
  不足以解释当前性能差距”；不得声称所有 25 tasks 都有已测 ceiling；
- 该 attestation 只增强数据质量审计，不解锁 critic、E2/E3 或 first-960 outcome。
