# Decision Semantic Mixture v1 结构失败与 v2 exact-config 资格门预注册

日期：2026-08-21。状态：`V1_INVALID_BEFORE_MODEL_FIT` / `V2_SUPPORT_NOT_READ`。

## 1. v1 不可追认

固定 commit `3ab396550e00e089d11fdbc5b256cc0387501991` 的正式 producer 在读取任何 test prediction/accuracy 前，
因 `exact_execution_config_within_every_pair=false` rc=1。没有生成 `summary.json`，第二次 producer 与两个 verifier
均未启动。该次只能记作结构性 INVALID，不能称 `DISCOVERY_NO_UNLOCK`，也不能删除失配 row 后续跑同一个 v1。

## 2. 新的 outcome-blind v2 支持问题

另立 v2，仅按事前已经交付学长的 exact stratum
`(task,client,hardware,time_limit,execution_timeout)` 过滤：pair 两端五元组完全相同才 eligible。过滤器不得读取或
使用 `gap_raw` 数值、better/worse 方向、code、label、模型 prediction 或 prospective vault；endpoint 名称只作无向
identity join。Draft/Improve 来源由固定输入文件决定，不从结果反推。

固定输出并独立复核：

- 原始与 eligible 的 merged/draft/improve × train/test 数；
- 每个 config field 的 mismatch 数、联合 mismatch pattern、task/type/split 分布；
- eligible pair/card/run/task/parent 支持、dominant test-task share、test≥10 的任务数；
- train/test endpoint 与 physical-run overlap；
- 三个 filtered JSONL 的 SHA，且 filtered merged 必须是 filtered Draft+Improve 的 exact disjoint union。

## 3. v2 资格门（计数前固定）

只有以下全部成立才允许另立新的 source commit，把 filtered 文件 SHA/精确计数绑定到原来不变的三-head模型协议：

1. eligible merged train `>=4,000`、test `>=750`；
2. eligible Draft train `>=2,000`、test `>=200`；
3. eligible Improve train `>=1,500`、test `>=400`；
4. eligible test 至少 20 tasks、至少 15 tasks 有 ≥10 pairs、dominant task share `<=0.25`；
5. filtered train/test endpoint overlap=0、physical-run overlap=0、pair/config/task identity 全部一致；
6. producer 双跑逐字节一致、独立 verifier 双跑一致、安全扫描=0。

任一失败则 `V2_INSUFFICIENT_EXACT_CONFIG_SUPPORT`，不得降低阈值、改成只跑 Improve、按任务补 pair，或读取旧 test
结果后再决定过滤。若全部通过，v2 的唯一 primary arm、0.5 mix、统计门和 `DISCOVERY_UNLOCK` 条件继续逐字使用
`DecisionSemanticMixture_CPU发现门_v1_预注册与预检.md`，不会因结构筛选修改。

## 4. 资源与完整性

本阶段只做 provenance selection：CPU only，GPU/API/checkpoint/model fit/prospective outcome 全为 0；预计双 producer +
双 verifier 2--8 分钟，峰值 RAM <6 GiB。输入仍锁 `baf6bdd` 与四个既有 SHA；输出新目录、manifest 和失败/通过
receipt。用户已授权离开期间推进有利于正方向的实验；本阶段不扩张 GPU/API 预算。
