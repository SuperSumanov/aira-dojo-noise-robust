# DeploymentCostAttestation v1：预注册与执行前检查

日期：2026-08-20。状态：`PREREGISTERED_NOT_EXECUTED`。

## 唯一问题

在 v11 b0 的 run-clean 决策资源上，三个真实可运行的执行前 CPU predictor，其初始化成本与单个 sibling
decision 的在线查询成本各是多少；相对于完整执行两个候选所需时间，成本优势是否在重复计时和最保守的
理想并行执行口径下仍成立？本实验只证明部署成本，不计算 frozen accuracy，也不证明 predictor 能选对。

## 输入与冻结口径

- cards：`phase1/cards_current_v11.jsonl`，normalized-LF SHA-256=
  `6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75`；
- train：`phase1/v11_decision/decision_train_v11_b0.jsonl`，4,263 pairs，normalized-LF SHA-256=
  `bd31b4679c7b4405703b976921df0bc63acba4fc0c4a002f4b8f36d171251fca`；
- query manifest：`phase1/v11_decision/decision_frozen_v11_b0.jsonl`，1,498 pairs，normalized-LF SHA-256=
  `2717e331c9e7156bdc47a31ea1fdd13c5eecb4465c33ad249c41bfac597a8da8`。

query 端只抽取 endpoint ID，并将每对按 ID 字典序 canonicalize；不使用 `better/worse` 方向、gap 或 accuracy。
train/query endpoint overlap 必须为 0。cards 只访问 `code`、`lineage` 和历史 `obs.runtime_s`；不会接触当前
prospective label/outcome/scorer vault。

## 固定矩阵与计时定义

三个模型固定为：

1. `static_lr`：与已审计 suite 相同的 34 个执行前静态特征、成对差分、LR；
2. `static_gbm`：同一静态特征、成对差分、HistGBM；
3. `tfidf_lr`：train-only char-wb 3—5 gram、30,000 features、LR。

每个模型固定 5 次独立初始化；每次初始化后先丢弃 5 次完整 batch warmup，再做 30 次 1,498-pair batch
计时；另由 seed `20260820` 事前固定 128 个 pairs，逐对计时，得到在线 latency 分布。所有 estimator 的分数
固定用 `raw(d)-raw(-d)` 显式反对称化，因此反向 pair 必须精确翻转。线程固定为 1；数据 JSON 读取在计时外，
但 feature/vectorizer transform 在 query 计时内。报告 p25/p50/p75/p95/min/max，不报单次数字。

初始化包括从内存中的 train code/lineage 构造训练表示、拟合 transform 和 estimator；不含原始 JSON I/O。
在线单对查询包括两个候选的 feature/TF-IDF transform、两方向打分与比较。batch 每对成本只作 throughput 辅助，
主成本为 128 个逐对 latency。

历史执行参考同时固定三种口径：每个 unique endpoint 一次；两个候选串行之和；两个候选理想并行时的最大值。
`self-report` 明确是执行后信号，不作为可部署 predictor。任何 hard-coded LLM/RM 延迟不进入本证明。

## 预注册门

完整性门：

- runtime 完整 pair coverage ≥0.95；
- 15 次 model×trial 全部完成，无 optimizer `ConvergenceWarning`；库内部 deprecation notice 记录于环境版本，
  不作为数值收敛失败；
- 每一 trial 的 30 次 batch decision SHA 一致，同模型 5 trial 的完整 decision SHA 一致；
- 反向分数 exact antisymmetry=1.0；
- 同一 run 内各 trial 的 single-query p50 最大/最小≤2，init 最大/最小≤3。

正成本门只在完整性全过后判断：

- 三模型各自 single-query p95 均≤理想并行 pair-execution p50 的 1%；
- 三模型各自 init p50 均≤10 个理想并行 pair-execution p50。

通过写 `DEPLOYMENT_COST_ADVANTAGE_SUPPORTED`；完整性过而正成本门不过，只写
`VERIFIED_DEPLOYMENT_COST_ATTESTATION`；完整性失败则不得引用成本优势。

正式执行固定 A/B 两个顺序独立 run，各自含上述 5 trials。独立 verifier 不 import producer，重算全部分位数、
比值、row count、input/source SHA 和状态。跨 A/B 要求同 host/platform/package、同 decision SHA、single-query
p50 最大/最小≤2、init p50 最大/最小≤3；任一失败不得只保留较快一轮。

## 资源与中断恢复

CPU only，GPU=0，API=0，不训练或微调底座 LLM。预计每个 formal run 10—30 分钟，A/B 合计不超过 1 小时；
如实际超过 2 小时则停止并记录。每个 model×trial 完成后原子写 CSV 与 receipt；`--resume` 只跳过已有完整
receipt 的 trial，中断 trial 的部分行先删除再从头重跑。输出目录存在且未显式 `--resume` 时拒绝覆盖。

## 13 项执行前检查

1. 产物记录三个模型的全部参数、seed、warmup/repeat/trial 数和反对称查询定义。
2. 先跑 synthetic/focused tests，再跑 Linux 全套测试；正式计时不在测试环境中拼接。
3. 三个输入 normalized-LF SHA 与上文锁值逐项相等，train/query endpoint overlap=0。
4. estimand 是 initialization 与 orientation-free query latency；不算 frozen accuracy。
5. 逐模型、逐 trial 报告，不能 pooled 均值掩盖某模型不稳定。
6. checkpoint/resume 以完整 trial receipt 为边界；中断 trial 不与续跑结果拼接。
7. 不读取 prospective vault；v11 frozen 只生成 canonical endpoint manifest。
8. seed=`20260820`；NumPy/sklearn 与 single-pair sample 均固定。
9. 不调用网络、不读 `.env`；Git push 前文件名与内容 secret scan 均须为 0。
10. CPU 单线程；记录 host、CPU affinity、Python/NumPy/SciPy/sklearn/threadpool；warmup 与 measurement 分离。
11. 这是计时证明，不做 accuracy 功效分析；正成本门事前固定，不能看结果后改成 batch 口径。
12. producer 与独立 verifier 必须真实非零退出；A/B 任一失败则整体失败。
13. source commit、输入 SHA、命令、CSV 每行、summary 和 verification SHA 全部随结果保存，目标存在拒绝覆盖。

## 旧数字纠正

截至本预注册，`REVIEW_PACKET.md` 中“561,077ms / 4.8ms = 七百万倍”算术错误：程序打印的比值为
`116891.041666666671517`。`suite_v9.csv` 的后续单次计时为 `437888.154ms / 4.245ms =
103153.864310954057146`，但也缺少多次重复、单线程和硬件绑定。两者均不得替代本次 formal attestation；
不得把成本比和旧 accuracy 相乘或写成联合方法收益。
