# TF-IDF comparison-component cost--utility：正式裁决

日期：2026-08-23。正式状态：`VALID_NO_STRONG_COMPONENT_COST_UTILITY_POSITIVE`。

## 完整性与复现链

V1 结构假设失败、V2 首轮数值非确定性失败均已独立保留，未作为结果。排序修复 commit
`e3cffbb6ec041e9de73efe6e112f1bd9859f6e69` 不改变协议、输入、estimand、bootstrap 或 gate；fresh no-smudge
exact commit 的聚焦/完整测试为 14/14、823/823（33 warnings），文件名/高置信内容凭据扫描为 0/0。

正式 producer A/B artifact 全部逐字节一致，独立 verifier A/B receipt 逐字节一致；verifier 不 import producer，
重建 1,482 pair、806 comparison components、156 task/subset CSV rows 和所有 task-bootstrap/gates。summary SHA=
`f740fb03bb5743b5cba381940ec64407c789aef15dbfe8c71ece4c16967b6e91`，独立 receipt SHA=
`517e08fd2473f3db74ccd84b41d3ccc62a3fe4cb40648e14486e9c1c4eeb7005`。两个 producer elapsed=7.20/7.60s，
max RSS=1,381,292/1,381,176 KiB。GPU/API/model fit/base-LLM update/future truth open=0/0/0/0/false。

## 冻结 test 结果

支持为 931 pairs、550 parent groups、559 identifiable comparison components、28 tasks；dominant component task
share=`0.10912343470483005`。task-bootstrap 50,000 次：

| 估计量 | point | 95% CI | 冻结门 |
|---|---:|---:|---|
| unweighted pair accuracy | 0.575798 | [0.507935, 0.640492] | secondary；高于随机 |
| raw-gap-weighted pair accuracy | 0.583455 | [0.494969, 0.669352] | **FAIL**：下界不严格高于 0.5 |
| weighted - unweighted | +0.007657 | [-0.057661, 0.067203] | 无大 gap 富集证据 |
| component oracle-gain capture | 0.073160 | [-0.215758, 0.316046] | **FAIL**：下界不严格高于 0 |
| component top-1 | 0.515086 | [0.433768, 0.592565] | secondary |
| component normalized regret | 0.926840 | [0.682951, 1.212128] | secondary |

样本支持两门通过、效应两门失败，故 overall primary=false。predeclared secondary 中，test Improve 的
gap-weighted accuracy=`0.6049657508514212`、CI=`[0.5029129993574336,0.7030161608082931]`，但 component gain
CI=`[-0.2951723243862662,0.3792797559908769]`；Draft 两个效应门均不满足。dev merged gap-weighted CI 高于 0.5，
但 component gain 跨 0，且 frozen test primary 失败。因此不得用 Improve/dev 替换 merged test primary。

## 裁决

TF-IDF query 的确很便宜：p95=48.958ms，execution parallel p50=199.627s，比例约 0.000245；但低成本不等于
可靠搜索价值。现有 57.58% task-macro accuracy 没有转化为稳健的 raw-gap 或 comparison-component utility。
“弱 headline accuracy 隐藏强高价值决策能力”路线在这个冻结 baseline/test 上关闭；禁止同池改 gap transform、
筛 task、丢 component、调 margin 或只报 Improve。这个结果作为 benchmark 的 accuracy≠utility 机制证据保留，
正方向资源回到新 physical runs 上的前瞻 score-channel 与 clean scaling/calibration，不再在本 test 追正。

证据：`phase1/results/tfidf_retrospective_component_utility_20260823_e3cffbb/`。
