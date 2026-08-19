# Senior augmented pair mismatch provenance v1

日期：2026-08-19。归因：`BATCH_CONTENT_MIXING_LIKELY`；上游裁决保持
`INSUFFICIENT_TRAIN_ONLY_DEV_SUPPORT`。

结果前 commit `5b9f285c2f1a62bf82a2820346da26be96e3570c` 固定了 run-family 正则、来源标签阈值与
匿名结构输入。远端 `391 passed in 34.88s`，producer 双跑逐字节一致；不 import producer 的 verifier 两次一致。
summary SHA256=`7c141bd6b74ee1f3aa6e60459d272da34edb99a1f6734508510d8d75c04ccc76`，verification
SHA256=`065f8b7e7d7d2ad3b334e29ca508896a99cb02352e9a0481da5b0fb7aece851d`。

9,001 个 full-train pairs 中有 708 个 config mismatch，比例
`0.07865792689701144`；它们涉及 8 tasks、71 runs、16 个无序 config transitions。708/708 mismatch pairs
均来自同一解析出的 run-family 与同一天，same-family-date share=1.0；run ID 解析失败=0。因此按冻结规则归因为
`BATCH_CONTENT_MIXING_LIKELY`：builder 在每个 batch 内只按 task 组合节点，而上游“一个目录就是同超参 batch”的
约定没有被机器校验。

该现象不是单任务或单一 config transition 独占：最大任务占 191/708=
`0.269774011299435`，最大 transition 占 98/708=`0.1384180790960452`。它分布在 8 个任务，不能靠删除一个任务
解决。

本轮不使用 numeric grade、pair orientation、raw code 或 frozen test，GPU/API/模型训练均为 0。归因仍标记
“likely”，因为旧 pair 文件没有保存原始 batch path；same-family-date 是固定的、可复现的 provenance proxy，不能
被升级成已观察的 batch identity。

未来数据的修复契约是：每条 pair 两端必须共享 exact `(task, client, hardware, time_limit,
execution_timeout)` stratum；producer 写入不可变 `experiment_stratum_sha256` 与 batch provenance，独立 verifier
逐条 fail closed。当前 708 pairs 可以用于错误清单和探索性敏感性分析，但过滤后的旧数据不能追认为确认性 scaling。
