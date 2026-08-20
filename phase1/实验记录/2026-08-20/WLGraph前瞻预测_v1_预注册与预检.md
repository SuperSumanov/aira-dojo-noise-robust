# WLGraph 前瞻预测 v1：预注册与执行前检查

日期：2026-08-20。状态：`PREREGISTERED_NOT_ACTIVATED`。

## 固定目的与矩阵

将已独立重拟合验证的 v11-train-only bundle 用作 outcome-unread extension。固定四臂为 `step_only_lr`、
`wl_graph_lr`、`wl_graph_static_lr`、`wl_graph_static_tfidf_lr`；唯一 primary extension arm 是最后一项，
唯一 primary comparator 是 2026-08-13 已激活的 `char_tfidf_lr`。其他三臂只解释位置、graph 与 static view，
不得结果后挑 champion。

bundle SHA=`df02cd1f5ba74be6b171ee9c377eeb58cf209a310a470b2ade671f2db03ee19e`；build summary
SHA=`d8d1b57172e4b63f391a0ca93b1213c0f040adf9592637c38d057ad6576622f5`；独立 verifier SHA=
`9918e6797b8f48fa9bb72e8cb740d1d5fab0ef81c0a961809fef40250b3e6b6e`。独立重拟合的数组和 5,499 个
reference endpoint score 最大差均为 0.0。

当前 first-960 前缀只能封存为支持性预测，因为 graph family 是看过这些 blind covariates 后决定补的，且旧协议
手填时间已作废。严格方法效果只来自稍后自动 activation receipt 之后生成的 physical runs，边界固定为
`generation_started_at_utc > activated_at_utc`；相等也归支持集。activation 之前不手填时间。

## 效果门（现在不执行）

严格 post-activation 子集至少需 1,500 finite non-tie pairs、150 finite-decision runs、15 tasks，最大任务 share
不超过 0.25。唯一主检验为完整多视图 arm 相对既有 char-TFIDF 在完全相同 canonical sibling pairs 上的 paired
accuracy difference；physical-run clustered 20,000 bootstrap 为主、task clustered 为次、run-level sign test
为辅助。强正结论还要求完整多视图 accuracy 的 run-clustered 95% 下界高于 0.5。search utility 不由 accuracy
自动推出；需要另立 end-to-end 协议。

## 13 项执行前检查

1. **旋钮产物验证**：bundle summary 固定四臂、WL=2、65,536 hash dimensions、8,192 node cap、seed；预测产物逐端点写四个分数。
2. **便宜路径先验**：本地无 SciPy 部分 3/3；既有 bundle 聚焦 10/10、phase1 473/473；新 scorer 必须在远端先过 synthetic 数值测试和全套测试。
3. **测试集查重**：不读取训练/测试 label；snapshot 按 `(task, run, parent)` 独立生成 canonical unordered combinations，每对一次。
4. **分布先看**：当前只打印 endpoint/run/task/pair 与 activation strata；不打印 accuracy、均值或任何 outcome。
5. **评估配平**：效果阶段预固定 run cluster 为主、task cluster 为次，并设 15-task/0.25 dominant-share 门；当前不评估。
6. **保存模型**：1.9 MiB NPZ、summary、train reference 与独立 verifier 均 append-only 保存，bundle SHA 已锁。
7. **泄漏三查**：只读 v11 train manifest；v11 frozen/extension、0812 label vault、first-960 outcome 均无 CLI 参数；blind manifest 精确 schema 且先做 credential scan。
8. **RNG 复现**：评分无随机；first-960 顺序固定为 `(generation_started_at_utc, source_sha256, run_id)`，不 shuffle。
9. **密钥扫描**：每个 blind manifest 在 JSON 解析前扫描高置信 credential shape；提交/推送前再做文件名与 diff 内容扫描。
10. **墙钟核算**：全量 build 1,316.87 秒、独立 refit 744.52 秒；当前 5,643-endpoint score+verify 预计 25–40 分钟，hard timeout 2 小时，CPU 单线程、GPU=0。
11. **功效含训练侧**：训练固定 4,263 pairs/5,499 endpoints/333 runs/23 tasks；效果侧另设 1,500 strict pairs/150 runs/15 tasks 门，失败不降门。
12. **链脚本 rc**：每步立即保存 `${PIPESTATUS[0]}`，build/producer/verifier 任一非零停止，不在坏产物上继续。
13. **扩语料冻结抽签**：无抽签；旧 first-960 前缀按全序逐字保持，后续 snapshot 只增加更晚 run，activation stratum 逐 run 确定。

资源：0 GPU·h、0 API、0 base-LLM update。当前评分只生成 escrow，不构成效果实验；即使当前支持性预测看起来
有异常 margin，也不得打开 outcome 或改 arm。
