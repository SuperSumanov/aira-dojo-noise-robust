# DeploymentCostAttestation v1：工程停止，不构成科学裁决

日期：2026-08-20。状态：`ENGINEERING_STOPPED_BEFORE_FORMAL_COMPLETION`。

## 裁决

v1 没有完成预注册的 A/B × 3 models × 5 trials，因此不能引用其成本优势、稳定性或正式状态。停止原因不是正门
失败，而是首个完整 trial 揭示原预计严重偏低：按实际工作量外推，A/B 需
`16.161918904708` 小时，超过事前固定的 2 小时停止上限。进程于
`2026-08-19T23:41:10Z` fail closed，已完成的 partial artifacts 原样保留，不与后续协议拼接。

## 实际完成内容

远端 source commit 为 `88f05cd6504b8a703a8dff02068b6072f15a536f`，clean worktree 与输入 SHA 门通过；
focused tests 为 7/7，相关 Linux tests 为 446/446。正式 v1 只完成 A run 的 `static_lr` trial 0：

- init：`150.714913267` 秒；
- 30 次 1,498-pair full-batch measurement 总计 `1484.727355074` 秒，单次 batch 中位数
  `49.616991898500` 秒；
- 128 个 single-pair measurement 总计 `6.286048833` 秒；
- single-query p50=`43.288167` ms，p95=`95.77951159999998` ms；
- no fit warning，tie=0，exact antisymmetry=`1.0`；
- sample decision SHA-256（v1 full manifest receipt）=
  `f0d9779459d64ea776b023029d9cbc419ec5bd0bcd335bbb134cbc4bda1b3497`。

同一冻结 manifest 的历史执行参考覆盖 1,498/1,498 pairs 与 2,022/2,022 unique endpoints：endpoint runtime
p50=`153.0488602463156` 秒，pair serial p50=`324.42474597058026` 秒，pair ideal-parallel
p50=`199.62654004304204` 秒。由这个单一 partial trial 得到的 `4611.572951172592×` 与
`0.0004797934762549545` 只能用于工程诊断，不能作为论文数字。

## 根因

v1 的 30 次 full-batch 计时每次都重新提取全部候选的 34 个代码特征。首 trial 的观测量给出：

- 估计每 trial：`1939.430268565` 秒；
- 单 A/B arm 的 15 trials：`8.080959452354` 小时；
- A/B 共 30 trials：`16.161918904708` 小时。

旧 suite 的毫秒级值更接近预先缓存表示后的 estimator call，而 v1 full-batch 是端到端重复 feature extraction。
这说明旧值不能当部署端到端延迟；也说明 full-cohort batch throughput 不是在线 sibling selector 的主要 estimand。

## 后续边界

允许另立 v2，只测实际在线路径：每次对一个 sibling pair 做 feature/vectorizer transform、两方向预测与比较。
v2 必须保持同一输入、同一模型、同一 CPU 单线程、同一执行参考、同一正成本阈值和独立 A/B；只能删去辅助的
30 次 full-cohort batch 重复，不能引用 v1 partial 数字填补 v2 的 trial。

