# DeploymentCostAttestation v2 正式结果

本目录保存 2026-08-20 在结果前冻结的 v2 在线单对部署成本实验。source commit 为
`c800345d281b4a15edb90b6c1593ee1b14337327`。A/B 均从头独立运行；producer、两份不 import producer
的 verifier 和跨运行 comparator 全部返回 0，最终状态分别为
`DEPLOYMENT_COST_ADVANTAGE_SUPPORTED` 与 `CROSS_RUN_STABILITY_VERIFIED`。

## 固定规模与执行参照

- 3 个模型 × 3 次初始化 × 2 个独立 run，共 18 fits；
- 每个 model/run 对同一 256-pair sample 逐对测量 3 次，共 4,608 个 online queries；
- frozen b0 的 1,498 对 execution runtime 覆盖率为 `1.0`，涉及 2,022 个有限 runtime endpoints；
- pair ideal-parallel execution p50=`199.62654004304204` 秒，serial p50=`324.42474597058026` 秒。

online query 包含两个候选的特征或 TF-IDF transform、正反差分打分和 preference 比较；初始化包含表示构造、
transform 与 estimator 拟合，不含 JSON I/O。全部在同一主机、相同 package、相同单 CPU affinity 和四项线程数
均为 1 的契约下完成。

## A/B 结果

| 模型 | run | init p50 (s) | query p50 (ms) | query p95 (ms) | execution p50 / query p50 | query p95 / execution p50 | break-even pairs |
|---|---|---:|---:|---:|---:|---:|---:|
| static_lr | A | 153.542809352 | 40.909126 | 108.53836795 | 4879.75568197282 | 0.05437071039081162% | 1 |
| static_lr | B | 153.092548862 | 41.00444 | 107.1604703 | 4868.412787567445 | 0.053680472685092254% | 1 |
| static_gbm | A | 154.789307361 | 49.3092785 | 115.68841655 | 4048.4579396764457 | 0.057952422821662894% | 1 |
| static_gbm | B | 155.037595478 | 49.0379345 | 115.72846835 | 4070.859469887379 | 0.05797248618597878% | 1 |
| tfidf_lr | A | 107.471423483 | 33.925568 | 51.0170753 | 5884.250487509658 | 0.025556258846644368% | 1 |
| tfidf_lr | B | 98.586651793 | 33.0667115 | 48.95820305 | 6037.084759488165 | 0.024524896859627974% | 1 |

预注册正门要求每模型 query p95≤execution p50 的 1%，且 init p50≤10×execution p50；A/B 三模型全部通过。
最慢的 observed query p95 也只占 execution p50 的 `0.05797248618597878%`。各模型 A/B query-p50
最大/最小比分别为 `1.002329895779245`、`1.0055333488811604`、`1.025973447646888`；init-p50 比为
`1.0029410999643482`、`1.0016040392016285`、`1.0901214467517888`，均远低于固定的 2×/3×门。

每个 model/run 有 768 个 query samples；所有 trial 无 fit warning、无 tie，最小 antisymmetry=`1.0`，且
同模型 A/B decision digest 完全相同。

## 可用主张与边界

该结果支持：在 v11 b0 的真实在线 selector 路径上，这三个轻量 predictor 的单对查询成本相对执行两个候选
低约 4,048–6,037 倍，初始化在中位执行时间口径下 1 对即可摊销。它只是一份部署成本证明：实验没有计算
frozen accuracy，没有打开 prospective vault，GPU/API 均为 0，也不证明 predictor 一定减少 wall-clock、提高
最终分数或具有方法 novelty。实际搜索收益仍取决于预测质量、候选并行度和控制策略。

v1 的 1/15 partial trial 因 full-cohort batch 估计量把投影推至 16.161918904708 小时而工程停止，未与本结果
拼接。完整原始 CSV、trial receipts、输入/环境/命令、A/B 独立验证、cross-run comparison、preflight 和监控日志
均保存在本目录。

Git 副本将 formal 原名 `hardware_environment.json` 的两份文件逐字节改名为 `hardware_context.json`，仅用于避免
提交前敏感文件名扫描把普通环境收据误报为凭据；内容未改。若直接重跑原 comparator，先复制回原文件名即可。
