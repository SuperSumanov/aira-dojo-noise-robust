# Senior Augmented Pair Mismatch Provenance v1：执行前冻结

日期：2026-08-19。状态：`FROZEN_NOT_RUN`。本轮只使用上一轮已经去掉 code、label、grade、gap 和 orientation 的
匿名结构产物，定位 full-train 配对中 experiment-contract mismatch 的来源。它是结果后数据工程诊断，不产生
predictor scaling、效果量、search utility 或因果主张。

## 固定输入

- run manifest SHA256=`bd707dd992a131d03dc20bdc981626826325f461e086a945b2f85fc41c2c171b`；
- pair structure SHA256=`52ffcdc0b7cc4486b61de0c664c7c057c26171a520372ca2071d55f2fb7a127b`；
- 上游 support summary SHA256=`7745dd157e41dc96a00ac76979afa6369f06395b0aa8ad67756de4d84e7297e8`；
- 上游裁决已经看到 full-train same-experiment share=`0.9213420731029885`。本轮不能改变该裁决。

## 固定分析

1. full-train pair 定义为 `original_split==train` 且全部 endpoint run role 为 `train`；必须精确重现 9,001。
2. mismatch 仅使用已冻结的 `same_experiment_contract==false`；不得新增或改变 config 字段。
3. run family 只由 run ID 的固定正则
   `^(.*)_seed_[0-9]+_id_[0-9a-f]+__(YYYY-MM-DD)$` 解析；family-date 键为捕获的 prefix 与 date。解析失败单列，
   不猜测或回填。
4. 统计：mismatch pair 数/占比、按 task 的 pair/run/config 数、无序 config-transition 计数、同 family-date share、
   same-day share、top-task 与 top-transition concentration；不读取或输出实际配置值。
5. 固定来源标签：mismatch=0 为 `NO_MISMATCH`；mismatch 中 same-family-date share≥0.95 为
   `BATCH_CONTENT_MIXING_LIKELY`；≤0.05 为 `AGGREGATION_OR_PROVENANCE_LOSS_LIKELY`；其余为
   `MIXED_OR_AMBIGUOUS_PROVENANCE`。该标签明确是推断，因为 pair 文件没有原始 batch-path provenance。
6. 未来契约建议固定为 pair 两端必须共享 `(task, config_sha256)`；producer 写
   `experiment_stratum_sha256` 与 immutable batch provenance，独立 verifier 对每条 pair fail closed。此建议不回写
   当前数据，不把过滤后当前结果追认为确认性。

## 十三项执行前检查

1. 方向：服务最新 augmented scaling 接入和 D&B 数据质量，不恢复 HCE/TD/多保真。
2. 代码：在 clean commit 上新增单用途 producer/verifier；新目录输出，不覆盖上游结果。
3. 输入：三个 SHA 固定；不再读取学长原始 cards/pairs。
4. 单位：physical run、unordered config transition、task；pair 不当 iid 效果样本。
5. 已见结果：明确披露 9,001 与 0.921342；本轮只定位来源。
6. 特征：run role/task/config hash/run ID；不使用 code、stdout、runtime、grade、gap、orientation。
7. 泄漏：frozen-test pair/run 不进入 full-train；若重算不为 9,001 立即失败。
8. 安全：输入已是匿名结构产物；仍做 SHA 与 schema 校验，不接触 `.env`。
9. 统计：描述性精确计数/share/concentration；不报显著性或效果 CI。
10. 复现：固定排序与 JSON 序列化；producer 双跑；独立 verifier 不 import producer。
11. 资源：CPU-only，预计<5分钟；GPU=0、API=0、底座更新=0。
12. 失败：SHA/schema/run reference/full-train count/duplicate pair 不一致均 fail closed。
13. 停止：完成一次即冻结；不得按输出改 family 正则或 0.95/0.05 标签阈值。
