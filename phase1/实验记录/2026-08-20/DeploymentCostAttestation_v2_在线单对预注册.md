# DeploymentCostAttestation v2：在线单对成本预注册

日期：2026-08-20。状态：`PREREGISTERED_NOT_EXECUTED`。v2 在读取任何 v2 timing result 前冻结；v1 partial
只用于发现工作量估计错误，不进入 v2 结果。

## Goal

回答唯一问题：在 v11 b0 run-clean 资源上，三个真实可运行的执行前 CPU predictor，从收到一个未执行 sibling
pair 到给出 orientation-invariant preference 的端到端在线延迟与初始化成本，是否相对执行两个候选仍低两个数量级
以上？这是部署成本证明，不计算 frozen accuracy，不证明 predictor 能选对，也不构成方法 novelty。

## Context 与固定输入

- source 必须是本预注册提交的 clean Git commit；
- cards：`phase1/cards_current_v11.jsonl`，normalized-LF SHA-256=
  `6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75`；
- train：`phase1/v11_decision/decision_train_v11_b0.jsonl`，normalized-LF SHA-256=
  `bd31b4679c7b4405703b976921df0bc63acba4fc0c4a002f4b8f36d171251fca`；
- orientation-free query manifest：`phase1/v11_decision/decision_frozen_v11_b0.jsonl`，normalized-LF SHA-256=
  `2717e331c9e7156bdc47a31ea1fdd13c5eecb4465c33ad249c41bfac597a8da8`。

query 只读 endpoint ID，并将 pair 按 ID 排序；不读 `better/worse` 方向、gap、accuracy 或 prospective vault。
train/query endpoint overlap 必须为 0；execution runtime coverage 必须≥0.95。

## 固定矩阵与公平契约

模型仍为 `static_lr`、`static_gbm`、`tfidf_lr`，定义与 v1 相同。CPU affinity 固定单核，NumPy/BLAS/sklearn
线程均为 1；A/B 在同一 host/platform/package 上顺序独立执行。

每个 A/B run × 每模型固定：

- 3 次从头初始化；
- 每 trial 丢弃 10 次 single-pair warmup；
- 用 seed `20260820` 从 1,498 个 canonical pairs 事前固定同一 256-pair sample；
- 对 256 对逐一计时，共 `2 × 3 × 3 × 256 = 4608` 个 measured online queries；
- 每 trial 另做 sample batch 与反向 batch，只用于核对逐对 decision digest 和 exact antisymmetry，不计时、不进入
  latency 分布。

初始化包括从内存中的 train code/lineage 构造训练表示、拟合 transform 与 estimator；不含 JSON I/O。在线查询
包括两个候选的静态特征或 TF-IDF transform、正反差分打分与 preference 比较。v1 的 30 次 full-cohort batch
throughput 从 v2 删除，因为它不是部署在线路径；所有正门和历史执行分母保持不变。

## Verification 与事前门

完整性门：

1. 18 个 model×trial 全部完成；每模型每 trial 恰有 256 个 item index `0..255`，无 duplicate/missing；
2. producer 与不 import producer 的 verifier 独立重算 row count、decision digest、分位数、比值与状态；
3. 无 `ConvergenceWarning`，sample-batch 与逐对 decision 完全一致，反向 exact antisymmetry=`1.0`；
4. 同一 run 内每模型 trial-query p50 最大/最小≤2，init 最大/最小≤3；
5. A/B decision digest 相同；A/B query p50 最大/最小≤2，init p50 最大/最小≤3；
6. 输入/source SHA、命令、seed、环境、CPU affinity、每行 CSV 与 receipt 均随产物保存；目标存在拒绝覆盖，完整
   trial receipt 才可 resume。

正成本门仅在完整性全过后判断，且与 v1 完全相同：

- 三模型各自 online single-query p95≤pair ideal-parallel execution p50 的 1%；
- 三模型各自 init p50≤10 个 pair ideal-parallel execution p50。

通过写 `DEPLOYMENT_COST_ADVANTAGE_SUPPORTED`；完整性通过但任一正门失败写
`VERIFIED_DEPLOYMENT_COST_ATTESTATION`；完整性失败则不得引用成本优势。A/B 任一失败不得择优报告。

## 资源、风险与停止规则

CPU only，GPU=0，API=0，不微调底座。根据 v1 partial 的 init 与逐对总时长，v2 预计 20–60 分钟；hard wall
仍为 2 小时，超时即工程停止并保留 partial。主要风险是 init 波动、TF-IDF transform 尾延迟与系统负载；因此
报告 min/p25/p50/p75/p95/max、逐 trial p50 和 A/B 比值，不只报一个均值。历史 execution runtime 是既有
post-execution reference，不与 query latency 混成 accuracy-adjusted speedup。

