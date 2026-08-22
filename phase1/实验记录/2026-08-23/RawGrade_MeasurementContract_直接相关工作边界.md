# Raw-grade measurement contract：直接相关工作与主张边界

日期：2026-08-23。检索在不读取 future outcome、不调用模型/API、不提交 GPU 的情况下完成；只参考论文/官方代码等
一手材料。本记录用于收缩主张，不把基本的单调变换事实包装成算法 novelty。

## 1. NAS predictor 的直接评价对象

[White et al., NeurIPS 2021](https://proceedings.neurips.cc/paper_files/paper/2021/file/ef575e8837d065a1683c022d2077d342-Paper.pdf)
把 predictor 定义为预测 fully trained architecture 的 validation accuracy/ranking，并同时报告 Pearson、Spearman、
Kendall 与 sparse Kendall，以及 predictor-guided evolution / Bayesian optimization 的实际搜索加速。也就是说，相关
领域把**原任务性能的次序**和下游 search utility 作为核心，而不是先用有饱和区的 medal transform 制造新的 pairwise
truth。

[BRP-NAS, NeurIPS 2020](https://proceedings.neurips.cc/paper_files/paper/2020/file/768e78024aa8fdb9b8fe87be86f64745-Paper.pdf)
更直接把 accuracy prediction 改成“两个 architecture 哪个更好”的 binary relation，并以 ranking/top-K 与最终 NAS
效果评价。它覆盖 pairwise predictor 先例，因此我方不能主张“首次用 pairwise critic”；但它也说明 within-task
decision truth 应保存真实 performance ordering。

## 2. MLE-bench 官方接口与我方变换的归属

MLE-bench 官方 `grade_csv` 同时返回 competition raw `score`、gold/silver/bronze thresholds、`is_lower_better` 与 medal
flags；见[官方 grading 实现](https://github.com/openai/mle-bench/blob/main/mlebench/grade.py)。官方 leaderboard 的 canonical
系统级汇总推荐报告 Any Medal (%)，并没有定义我方 `cards.py::normalize_graded` 的连续 piecewise-linear + `[0,1]`
clipping；见[官方 benchmark 说明](https://github.com/openai/mle-bench#benchmarking)。

因此 147/158 alias 是**我方派生 label contract 的缺陷**，不能写成 MLE-bench grader 缺陷。官方 raw score 仍只有
五位小数，未四舍五入 truth 不可恢复；本项目只是避免再用额外 clipping 抹掉已经存在的 within-task ordering。

作用域也必须收紧：这不是整个 v11 predictor benchmark 的标签污染。`build_decision_v10.py::finite_label` 明确读取
`label.graded`，b0 decision release 的 orientation/gap 审计也按 official raw grade 闭合；147-parent alias 发生在
score-channel 机制实验另行使用的 `cards.py::normalize_graded` truth-support 链。因此不能把 raw extension 包装成
“修复全部 critic 训练标签”，它只修复 score-channel 的可辨识性并提醒 release 同时保留两套 contract。

## 3. 防 scoop 裁决

本轮定向检索没有找到一篇直接同时覆盖以下组合的工作：MLE-agent 真实 search-tree sibling sets、外部
`submission.csv` evaluator vs stdout self-report、先物化 structural/truth/channel-overlap 漏斗、并在 temporal closure 后
用 raw-vs-clipped 双 truth contract 决定是否值得 replay。这个交集仍可作为数据集/测量协议贡献。

但“非严格单调 clipping 会制造 ties”“ranking 应使用保序 truth”“小 gap 应结合噪声处理”都不是新理论，禁止
first-ever 表述。可守住的主张只有：

1. 在我方真实旧 cohort 上，结果前协议实证量化了 147 parents / 16 tasks 的 alias；
2. release 同时保留 official raw grade、task orientation、normalized utility 与 transform-induced tie audit；
3. 每个 predictor/evaluator 表固定报告 structural support、raw truth support、normalized support、channel overlap 与成本；
4. future score-channel 结果必须把原 `y_norm` status 与另名 raw-grade status 并列，不能用后者擦除前者。

## 4. 当前执行影响

当前不新增模型或长实验。`score-channel-future-raw-grade-support-extension-v1` 已按上述边界冻结：同一 parent selection、
raw support 无跨任务 gap bins、effect 前另做 orientation receipt、PASS 仅允许准备另名矩阵并再次申请 GPU 预算。论文中
该项定位为 benchmark measurement contract / retraction audit，而不是独立算法贡献。
