# First-960 暂定集合 churn 与 prediction escrow 完整性：预注册

日期：2026-08-26。性质：outcome-blind、CPU-only 协议完整性修复；不是 predictor 效果实验。

## 1. 发现与风险

`prospective_accumulator.py` 对所有 eligible physical runs 使用预注册全序
`(generation_started_at_utc, source_sha256, run_id)`，并在每个 snapshot 重建 `[:960]`。因此 append-only
source 只保证旧 run set containment、旧有序序列为新序列的 subsequence，以及同一 run row 不变；它**不保证**
`provisional_first960_runs.jsonl` 是 byte prefix，也不保证达到 960 后 membership 单调。

旧 WL append verifier 和 transition producer/verifier 都要求 prior prediction support 是 current support 的子集。
当迟到上传的较早 run 进入前缀并挤出旧尾部时，这会把合法 cohort churn 误判为失败；若新 run 排在 960 之后、
first-960 完全不变，旧 WL verifier 还会因“没有增长”误拒绝。该风险尚未发生在当前 366/960 cohort，但在达到
960 后、独立 accrual closure 之前会成为确定性边界故障。

## 2. 冻结修复

不改 frozen scorer、activation、模型、预测值、chronological first-960 estimand 或 closure 条件。每个 artifact 继续
绑定不可变 snapshot，并由原独立 scorer verifier 逐值复算；跨 snapshot 的控制 verifier 改为：

1. 旧 physical run set 必须包含于新 set，旧 run row 逐字段相同，旧顺序必须是新顺序的 subsequence；
2. 两代 first-960 均须逐字等于各自全量有序 run list 的 `[:960]`；
3. 两代 artifact 的共同 endpoint/pair prediction row 必须逐字段相同；
4. prior-only row 只能来自被挤到 rank≥960 的 run；current-only row 只能来自进入 rank<960 的 run；
5. transition 若真实发生 removal，current artifact 必须不传旧 `--prior-artifact`，再由独立 scorer verifier 与本
   control verifier 双重验证；历史 artifact 不修改、不删除；
6. closure 前任何结构支持门都只是 provisional，可随 churn 反转，不能触发 accuracy/effect 揭盲。

机器合同为 `phase1/provisional_first960_snapshot_chain_protocol_v1.json`；独立实现为
`phase1/verify_provisional_first960_snapshot_chain.py`。

## 3. 十三项 preflight 与资源矩阵

1. **方向**：仅 Decision Corpus + Predictor Benchmark + Audit Protocol；不恢复旧 HCE/多保真/Probe。
2. **问题**：验证 snapshot chain 完整性，不计算 accuracy、effect 或 search utility。
3. **输入**：只读 accumulator run manifests、prediction escrow artifact 和已有 independent receipt。
4. **禁止输入**：label/outcome vault、score registry、regrade、prospective truth 全不传。
5. **顺序**：固定三字段升序、target=960，不按结果改动。
6. **正例**：合法 append、prefix stasis、合法 insertion+displacement 均应通过。
7. **反例**：共享预测变化、旧 run row 变化、无法由 rank 解释的 row 增删必须 fail closed。
8. **独立性**：control verifier 不重训模型；current artifact 仍须原 independent scorer verifier 通过。
9. **可复现**：producer/receipt 双跑逐字一致；Python/平台、命令、commit、SHA 写入正式包。
10. **统计**：无统计量、无 seed、无均值；只报告精确计数与布尔不变量。
11. **资源**：本地/远端均单 CPU；GPU jobs/API/model fit/base-LLM update=`0/0/0/0`（已有 artifact shadow）。
12. **安全**：forbidden path trace/打开清单与边界感知 credential filename+content scan 必须为 0。
13. **停止门**：任一 hash/schema/order/intersection/explanation/independent receipt 失败即不发布 PASS，不作
    scientific negative claim。

矩阵：两种 family（WL、transition）× 合成 append/stasis/churn/篡改反例；真实 shadow 先只跑 transition 最近两代
snapshot。总 GPU·时=0，总 API=0，总新模型拟合=0。

## 4. 预期裁决边界

通过只证明 prediction-before-outcome 的托管链能正确承受暂定 cohort membership churn；它不是 predictor 方法提升，
不提高任何 accuracy，也不授权 closure 前读取 outcome。若真实 shadow 失败，结论只能是完整性实现需修复，不能写成
critic 负结果。
