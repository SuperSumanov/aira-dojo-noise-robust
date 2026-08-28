# Senior 0819 decision relation taxonomy：正式审计证书

正式分类：`HISTORICAL_RELATION_AWARE_DECISION_TAXONOMY_INTEGRITY_GATE_FAIL`

本次按结果前冻结的三类 taxonomy 和 15 个 hard gates 运行。13 个 hard gates 通过；失败的是
`all_decision_endpoints_parent_tasks_and_splits_valid` 与 `train_test_physical_run_overlap_zero`。旧 7,644-row
decision 文件因此不能整体升级为 relation-aware、run-clean benchmark，也不能用下面的 sibling 子组宽度救回冻结分类。

## 正式结构结果

- `verified_direct_sibling`：1,270 rows（train/test=`952/318`）；
- `same_run_declared_context_non_sibling`：2,119 rows（`1620/499`）；
- `cross_run_declared_context`：4,255 rows（`3912/343`）；
- train/test unordered-pair 与 endpoint overlap 均为 0，但把 declared parent run 也计入引用闭包后，有 96 个 physical runs
  同时被两侧引用；并且并非每一行的 declared parent 都与 endpoints 属于同一 frozen run partition；
- 三类 train/test composition 的 total-variation distance 为
  `578477/1880360=0.30764162181709886`，说明旧 train/test 的关系混合比例也明显不同；
- taxonomy exhaustive/purity、零 unordered duplicate、零 orientation conflict、输入 hash 和上一轮 overall aggregate 复现均通过。

尽管整体 gate fail，冻结前未见的 test sibling-core 结构支持面本身较宽：318 pairs、29 tasks、89 physical runs、
591 endpoints、282 connected components；最大 task/run/component pair share 分别为 `25/159`、`7/106`、`1/53`，
预注册的 8 个 sibling support gates 全部通过。这是后续“隔离 sibling core、明确 quarantine 其余 rows”的可行性信号，
不是本轮 strong-pass，也尚未授权 row-level release。

## 复验与安全

- protocol/source commit：`df94c4ec6a3bb2c0856e29d148cb898d2b796cc1279800456b8f8e6108e08e32` /
  `f534114e60658043c07f7a15d6440492caffc8ad`；
- producer A/B 逐字节一致，SHA-256=`b75df026fdab24a5a3da6f01d734820ad908e505df0140f13586c2386624c6d3`；
- 独立 verifier A/B 逐字节一致，SHA-256=`d5613fe7780df6a7c4c894780a44d971ac470af9070d804705b26e729bc0b66a`，
  且 `all_aggregate_fields_equal=true`、不导入 producer；
- focused/full tests=`6/1469 passed`，full 有 47 个既有 deprecation warnings；
- forbidden file opens/network calls=`0/0`；remote formal manifest=
  `68d845cc6e2801d814bcd320017bce5ae5712c2e01f94dff7a010b1195230f56`；
- first-960/Target-300 前瞻值、raw senior archives、模型 prediction/accuracy 与 search utility 均未读取或计算；
- GPU/API/model-fit/base-update=`0/0/0/0`。

`formal_summary.json` 是匿名 aggregate 主结果，`verification.json` 是独立核验回执。历史 test 曾被周期使用，不能称
untouched final test；本证书也不证明 critic scaling 或端到端 search utility。
