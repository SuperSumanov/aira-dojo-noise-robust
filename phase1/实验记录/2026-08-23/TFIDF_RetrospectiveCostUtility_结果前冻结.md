# TF-IDF retrospective cost--utility：结果前冻结

日期：2026-08-23。状态：`FROZEN_BEFORE_GRADE_GAP_AND_PARENT_UTILITY_READ`。

本轮只追问一个已经存在的弱 predictor 是否仍有**决策效用**：component-clean test 上 char-TFIDF 的普通
pair accuracy 为 532/931=`0.5714285714285714`，但错误可能集中在真实分差很小的 pair。冻结前没有读取
本轮 raw-grade gap、parent utility、加权 accuracy 或任何 gate 结果；future/prospective truth 继续封存。

## 固定估计量与裁决门

输入逐字节固定为：released Cards、TF-IDF per-pair margins、对应 baseline summary 和独立 cost attestation；
四个 SHA/bytes 均写入 `tfidf_retrospective_utility_protocol_v1.json`。不重新拟合模型，不改 pair pool，不筛 task，
不调阈值。

主估计量只有两个：

1. **task-macro raw-gap-weighted pair accuracy**：先在每个 task 内以 oriented raw grade gap 加权，再对 task
   等权；不同任务的 raw-grade 单位永不直接混合。随机选择的期望为 0.5。
2. **task-macro parent oracle-gain capture**：每 task 内汇总 `selected utility - uniform-candidate mean`，除以
   `oracle utility - uniform-candidate mean`，再对 task 等权。随机候选的期望为 0。

只有 test 同时满足 task 数≥20、完整 parent 数≥300、上述两个 task-bootstrap 95% CI 下界分别严格高于
0.5 和 0，并通过输入、图一致性和既有成本门，才记为
`RETROSPECTIVE_COST_UTILITY_POSITIVE`。否则固定记为
`VALID_NO_STRONG_COST_UTILITY_POSITIVE`，不得换 gap 变换、pool、task、阈值或 CI 聚类方式救正数。

该 test 的普通 accuracy 已经看过，因此即使通过，也只是 D&B 的 retrospective mechanism evidence；不是新的
frozen-test confirmation，更不是 live-search causal speedup。Draft/Improve、普通 accuracy、top-1、normalized
regret 和加权减普通 accuracy全部是 secondary。

## 结果前预飞（13 项）

1. PASS：方向为当前 MLE clean calibration/cost--utility frontier；旧 HCE/TD/probe/multifidelity 不恢复。
2. PASS：9 个合成/攻击测试覆盖正例、input hash、grade orientation、图断连/矛盾、margin/label、不可变输出、
   独立复核、manifest-consistent 篡改及 cost scope 越界。
3. PASS：四个输入 exact SHA/bytes 已冻结；不接受替代 Cards、pair rows、summary 或 cost receipt。
4. PASS：固定 dev/test 与 Draft/Improve；test pool 931 rows，不按结果重采样。
5. PASS：task/parent support 由冻结输入决定；主门要求≥20 tasks、≥300 parents，并报告 dominant task share。
6. PASS：CPU 短任务；输出目录必须不存在，producer/verifier receipt 均不可覆盖；双 producer 独立目录。
7. PASS：pair/Card task、task direction、better/worse raw orientation、source micro accuracy、physical input hash
   全部 fail-closed；future vault 参数不进入程序。
8. PASS：task bootstrap=50,000，base seed=20260823，各 metric seed 由固定 crc32 公式导出；数值线程固定为 1。
9. PASS：只读已发布的 sanitized Cards；不读取 senior raw tar payload 或 `.env`，提交前执行文件名和内容凭据扫描。
10. PASS：0 GPU、0 API、0 model fit；Cards 604,190,866 bytes，单进程顺序执行，设 wall-time/memory 观测。
11. PASS：两个 primary gate 结果前固定；task-cluster bootstrap；raw grade 只在 task 内归一化。
12. PASS：任何 schema/hash/方向/图/成本/完整性异常均 INVALID，不 partial salvage，不当成 negative result。
13. PASS：producer 双跑、独立 verifier 双跑、artifact manifest/hash 比较；命令、commit、环境和结果随后落盘。

## 实现独立性与攻击面

producer 根据 antisymmetric pair margin 重建每个 parent 的标量 potential；图必须连通、cycle residual≤1e-9、
唯一 winner。verifier 不 import producer，独立重建 source rows、Cards truth、parent graph、全部 task metrics、
bootstrap、cost gates、CSV 和 artifact manifest。测试还模拟先篡改 parent utility、再同步更新 manifest hash；
独立重算仍必须拒绝。

冻结文件：

- `phase1/tfidf_retrospective_utility_protocol_v1.json`；
- `phase1/tfidf_retrospective_utility_audit.py`；
- `phase1/verify_tfidf_retrospective_utility_audit.py`；
- `phase1/tests/test_tfidf_retrospective_utility_audit.py`。
