# v11 failure-censored source-opportunity hurdle baseline

日期：2026-08-15。协议：`source-opportunity-hurdle-baseline-v1`。source commit：
`c89c5bd015fa4d71170df1b836a93200154f610d`。

## 冻结裁决

producer、逐字节确定性复跑与不 import producer 的独立 verifier 一致裁决：

`VERIFIED_FAILURE_CENSORED_MECHANISM_ONLY`

构造门通过，但正方法门未通过：`method_positive_claim_allowed=false`。该实验只支持“source opportunity
存在 informative failure censoring，benchmark 应同时建模 feasibility 与 conditional quality”的机制说明；
不支持 hurdle 方法改善完整候选集选择效用，也不改变评分通道主线。

## 输入与构造

- train：497 个 eligible parents / 126 runs / 13 tasks；相对 exact-recoverable incomplete parents 的 coverage
  为 `0.9136029411764706`；
- frozen：150 个 eligible parents / 40 runs / 10 tasks；coverage 为 `0.9036144578313253`；
- extension：10 个 eligible parents / 3 runs / 2 tasks；只作隔离描述；
- 所有 source/journal parent、retained code/status、status category 与 journal SHA 完整性 mismatch 均为 0；
- 模型只在 train role 拟合；共 2,397 candidates，其中 train 1,851、scoreable train candidates 1,152。

固定模型为 static/char-TF-IDF 的 scoreability logistic regression 与 conditional-quality Ridge；hurdle 分数为
`P(scoreable) × clipped conditional quality`。TF-IDF 只在 train 拟合，seed=`20260815`。

## 结果与边界

主比较是 frozen 上 `hurdle_tfidf` 相对 `quality_tfidf`：

| metric | overall delta | run-cluster 95% CI | task-cluster 95% CI | gate |
|---|---:|---:|---:|---|
| scoreability | +0.020000 | [-0.022857, +0.071429] | [-0.050505, +0.088398] | CI 门失败 |
| parent utility | -0.001350 | [-0.014959, +0.015212] | [-0.015266, +0.017847] | 效应与 CI 门失败 |

执行前 static scoreability 模型相对随机的 scoreability 增量为 `+0.120444`，task-CI
`[+0.059630,+0.160741]`，说明“是否能产生可评分结果”并非完全不可预测；但该信号没有转化为预注册的
完整 utility 增益，不能把机制可预测性写成方法成功。

实验不读取 first-960/prospective outcomes、pair orientation 或 journal numeric grade magnitude；不记录 raw
code/stdout；GPU=0、API=0、底座更新=0。冻结只有 10 tasks，部分 task 仅 1--3 parents，所有 headline 均保留
task/run 聚类区间，不能只报 micro 平均。

## 独立复核与失败历史

- producer 与 verifier 两次完整 `phase1/tests` 分别为 `309 passed in 24.45s`、
  `309 passed in 23.03s`；
- independent receipt：2,397 candidate rows、150 frozen parents / 10 tasks，重建全部 parent metrics、cluster
  intervals 与 gates，`imports_producer=false`；
- 三个主 CSV 的复跑逐字节一致：construction、candidate scores、frozen parent 分别为 SHA-256
  `846da509...`, `bdc5b653...`, `8b964f64...`；
- producer/repeat 最大 RSS 分别为 2,418,632 / 2,420,472 KiB，exit status 均为 0；
- 产物与 post-verification 高置信 secret hits 均为 0。

首次正式 `a1` 已完成科学计算，但因 `numpy.bool_` 无法 JSON 序列化，在写 summary 前失败；该运行没有可读
结果，失败目录保留。修复仅把 gate 值显式转成 Python `bool/float` 并增加 JSON regression test；`a2` 才是本页
报告的正式结果。成功产物保留在：

`/research/d7/spc/yzyang4/source-hurdle-v11-c89c5bd-a2`

独立 receipt 中的 blind-score SHA-256 为
`b42375fb879b26ee800d37f016678e629211d0f8faad66115d57c43c482f9120`，producer summary SHA-256 为
`243283471e5951f068d0c11607052552d9ba725c56f1d11d8cd5d12c8a196c03`。
