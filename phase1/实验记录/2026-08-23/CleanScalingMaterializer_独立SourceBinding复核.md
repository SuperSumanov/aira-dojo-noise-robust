# Clean scaling materializer：独立 source-binding 复核

日期：2026-08-23。状态：`INDEPENDENT_SOURCE_VERIFIER_READY_SYNTHETIC_ONLY`。

单靠 materializer 自己的 tests 不能证明 pairs/Cards→truth 或 one-shot→prediction 没有同源实现错误。新增
`verify_critic_scaling_confirmation_materialization.py`，明确不 import producer，并用第二套实现：

- 重新解析 grouped JSON / flat JSONL Cards，重建 task/run/lineage/grade；
- 独立重建 maximal connected components、component digest、pair digest、oriented utility 与 support receipt；
- 独立检查 checkpoint manifest、pairs/Cards 哈希、prelocked output/ledger path、upstream output/ledger；
- 逐 pair 重建 normalized predictions，并核对 derived ledger 的完整 source hash chain。

focused 合成测试现在为 materializer/verifier 18/18，包含一个“篡改 prediction 并同步更新 derived hash”的正面对抗：
producer 自洽仍不够，verifier 必须从 upstream source 重建并拒绝。联合 scaling analyzer/endpoint tests 总计 28/28。
真实 future truth/GPU/API/model fit 仍为 `false/0/0/0`；集群 exact-commit full regression 尚待本 commit 推送后执行。
