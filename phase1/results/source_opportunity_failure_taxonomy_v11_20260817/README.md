# Train-only source-opportunity failure taxonomy v1

日期：2026-08-17。正式裁决：`VERIFIED_STRUCTURED_FAILURE_MEMORY_SUPPORT`。

## 结果

- 锁定的 691 个 train execution-error nodes 全部找回，691/691 均有非空 diagnostic；
- 560/691=`0.8104196816208393` 命中结果前冻结的 9 类 structured taxonomy，覆盖 12 个任务；
- 最大 structured task 占比为 128/560=`0.22857142857142856`，不是单任务结果；
- 最大类别为 `DATA_SCHEMA_SHAPE_TYPE` 318，其次为 `LIBRARY_API_ATTRIBUTE` 104、
  `RESOURCE_TIMEOUT` 81、`DEPENDENCY_IMPORT` 36；
- `ARTIFACT_OUTPUT_CONTRACT` + `DATA_SCHEMA_SHAPE_TYPE` 为 324/691=`0.46888567293777134`。
  这是描述性 contract-related share，不是 contract prompt 或 memory 的因果收益。
- 126 个目标 journal SHA 的 credential-shaped 命中为 0；输出不含 raw diagnostic、代码、grade 或 pair orientation。

## 完整性与复现

Producer commit 为 `a70cc689bbb88497f14c4358fc899599cd0e15fc`；完整 `phase1/tests` 为
`346 passed in 27.94s`。八个预定 roots 上正式双跑逐字节一致：producer summary SHA256=
`adf630c63986f2aabaff064f68a00bb512c0b767a0b263e45b4297c395ba0c0a`，per-child SHA256=
`a5f46021d61d1415d49476728fa988feda5cd9d97e80697099f6af467eca2087`。

不 import producer 的 verifier commit `c1016b7343a5158ff74e6b2c333c1a517e31f10d` 在 `349 passed in 29.35s`
后重新计算 691 行计数、资格门、manifest、字段白名单与无 raw diagnostic 约束，状态为
`INDEPENDENT_FAILURE_TAXONOMY_VERIFIED`；verification SHA256=
`785d94d9043be6d6f938b306b40658868df5ce2ad4ef8841076fa8a7a8a58215`。

完整无原文 producer artifact 留在远端
`/research/d7/spc/yzyang4/failure-taxonomy-v1-a70cc68/`；仓库只提交汇总，不提交 691 行 identity 明细。

前四次前置失败均保留：remote alias 不同、默认环境缺 pytest、一次性测试环境缺 NumPy、script-path
CLI import 失败。前三次发生在测试/环境阶段，第四次发生在 345 tests 之后、日志输入打开之前；修复为有真实
子进程测试的 module CLI 后才产生正式结果。

## 主张边界

允许：现有 run-clean 训练语料含一个覆盖广、可机械标注的 evaluator-verified failure-memory 数据资产；
后续可预注册轻量 failure-risk controller。

不允许：声称 failure memory、contract 或 controller 已提高搜索分数/速度；把 46.89% 解释为全部可修复；
读取 frozen/extension/前瞻 outcome 来调 taxonomy。
