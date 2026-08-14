# Prospective first-960 accumulator：盲态预注册

日期：2026-08-14。协议：`prospective_accumulator_v1`。状态：**在任何 activation 后 outcome 被读取前冻结**。
本协议只聚合 `prospective_drop_intake_v1` 的 label-free 产物，不改 active scorer、first-960 estimand、支持门、
bootstrap 或 evaluator。

## 1. 目标与唯一允许输入

输入是人工维护、append-only 的 registry JSONL；每行严格只有 `drop_id/intake_dir/summary_sha256`。每个 intake
目录只允许打开：`summary.json`、`archive_manifest.tsv`、`archive_audits.json`、`source_provenance.json`、
`all_blind_views.jsonl`、`eligible_blind_manifest.jsonl`、`structural_pairs.jsonl` 与
`eligible_structural_pairs.jsonl`。accumulator 不 stat、不打开 `label_vault.jsonl`，只把 summary 已记录的 vault
SHA 作为不透明字符串传递；任何 grade/label/prediction/scorer score 文件均不是输入。

每个 drop 必须重新通过：summary/file SHA、freeze receipt SHA、硬编码 16,012-endpoint denylist SHA、严格
code+lineage schema、`run_id == journal:<source_sha256>`、root start 严格晚于 activation 的 eligible 重算、
all→eligible exact subset、provenance/endpoints/tasks/counts、结构 pair 从 blind rows 的精确重建，以及安全字段。
intake summary 还必须携带与 accumulator 当前冻结版本一致的 Git commit、intake 源码 SHA、资源配置与软件环境；
跨 drop 的 journal/run/card/source-archive 重复均 fail closed；exact-code 跨 future drop 的重复只作盲态计数，
不据此删样本。

## 2. 固定排序与 late-arrival 问题

所有合格 physical runs 按
`(generation_started_at_utc, source_sha256, physical_run_id)` 全序排序；没有 label-based tie-break。
但 run 的上传时间可晚于 generation time，所以在生产仍进行时，后上传的旧 run 可能插入当前 first-960 前缀。
因此：

- 未关闭生产时，所有 first-240/first-960 文件一律标记 `provisional`，不得称 frozen、不得运行 evaluator；
- 即使 provisional run 数达到 960，也只能记 `PROSPECTIVE_COHORT_AWAITING_CLOSURE`；
- accumulator 不以 pair 数、任务分布、scorer margin 或任何 outcome 决定停止。

## 3. 非 outcome 的 accrual closure

只有生产者停止该轮数据生产、补齐所有计划 archive 后，才能额外提供 hash-locked closure receipt。严格 schema：

`status/protocol/closed_at_utc/registry_sha256/all_scheduled_runs_uploaded/outcomes_read`。

必须满足：`status=PROSPECTIVE_ACCRUAL_CLOSED`、`protocol=prospective_decision_v1`、receipt 内 registry SHA 与实际
registry 一致、`all_scheduled_runs_uploaded=true`、`outcomes_read=false`，且所有已登记 run start 不晚于
`closed_at_utc`。closure 是生产完整性的声明，不得由 critic 表现触发；receipt 自身与 exact command 一并归档。

closure 后：

- 总 eligible runs >=960：冻结排序后的 first-960；first-240 是其固定前缀；
- 总 eligible runs <960：状态只能是 `CONFIRMATORY_COHORT_INCOMPLETE`，冻结已有 identity 供删失报告，但不降低
  确认样本量、不改停止点；
- 到 closure 前不得读取任何 label vault，closure 后 evaluator 仍须另跑一次独立的 hash-locked 解封流程。

## 4. 输出与完整性

每次 accumulator 使用新目录并原子提交，输出一行一个 run 的 provisional/frozen identity、对应 blind endpoint
manifest、结构 pairs、sealed-vault registry 与 summary。summary 必须记录 registry/receipt/所有输入 SHA、代码
commit、run/task/endpoint/structural-pair 数、first-240/960 支持、任务占比、跨 drop exact-code 重复数、
`label_vault_opened=false`、`outcome_files_opened=[]`。0 GPU、0 API、0 base-LLM update。

在真实新 drop 前只允许 synthetic 单测与 0812 eligible=0 的 shadow registry 回放；不能用 0812 outcome 调整
排序、门或 closure 规则。
