# Component 同池 TF-IDF：v1 反对称失败与 v2 定义修正

日期：2026-08-21。状态：`V1_FAILED_NO_SCIENTIFIC_OUTPUT / V2_CORRECTION_BOUND_NOT_RUN`。本文件写于任何
component-split baseline accuracy、margin 或 summary 被输出之前。

正式 producer 1 在输出目录创建前触发预注册的 prediction antisymmetry gate。原因是实现调用了二分类器的
`decision_function(x_better-x_worse)`；该函数包含拟合截距 `b`，所以正反方向相加为 `2b`。Bradley--Terry
endpoint score 为 `s(x)=w·x+b` 时，合法 pair margin 必须是 `s(better)-s(worse)=w·(x_better-x_worse)`，截距
严格抵消。把分类器截距带进 pair margin 是定义错误，不是可接受的数值容差。

v1 没有写出 `summary.json`、`per_pair.jsonl` 或任何 accuracy；GPU/API/model download 均为 0。失败 bundle=
`/research/d7/spc/yzyang4/critic-component-tfidf/e5f97d2-baf6bdd-v1.tar.gz`，SHA-256=
`37b0fcd8c2e630d7f2671f3abf0b05145f45775e5f3156a519a3eb14a46ee1c4`。

v2 只做一个定义修正：模型仍用完全相同的对称样本、TF-IDF、LR 超参和截距拟合，但 pair margin 改为稀疏矩阵
`(x_better-x_worse)·coef`；同时独立计算反向 `(-difference)·coef`，原 `1e-8` 反对称阈值不放宽。summary 显式写
`pair_margin_uses_classifier_intercept=false`，并继续记录拟合截距供审计。其他 input、bootstrap、输出和失败门逐字
不变；用新 commit、新 worktree、新输出目录重跑 producer×2 与独立 full-refit verifier×2。
