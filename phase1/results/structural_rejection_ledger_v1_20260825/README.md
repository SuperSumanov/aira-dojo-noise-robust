# Outcome-blind 结构拒收总台账 v1

该台账把截至 snapshot `7cdaefcf...` 的 218 个 source archives 精确分成 128 个 sealed baseline、78 个
accepted archive transactions、12 个 immutable structural rejections 和 0 个 pending，并把 post-baseline 的 90 个
dispositions 绑定到同一个可独立复算的 population。

## 机器复核结果

- settled archive decisions：90；accepted：78；rejected：12；拒收率 `12/90 = 0.13333333333333333`；
- 11/12 拒收来自任务身份元数据，比例 `0.9166666666666666`；其余 1 个 archive 没有 checkpoint journal；
- 6 个出现拒收的竞赛，6/6 也至少出现过一次 accepted archive transaction；
- 因此结构有效性是 archive-level、随批次变化的属性，不能用 task-level whitelist/blacklist 替代逐归档门控；
- source partition SHA-256=`aa161d4cf601bd323420336381f932818b4b4bbb310abedeb6951b852910f07c`，其独立复核
  SHA-256=`ffa0974dcc09d7cf67c55f348ea601c39c84eb688c83535ff8ed5a62bf77b82e`；
- ledger SHA-256=`b194b1bc88e561e77f982ae6f46d5ea7cccb745cc960c26da2661ea0ce8bad03`；独立 verifier
  SHA-256=`1281797c52007f3a6f9687ded4a785f21f0cc779bb8276e9e41e4ed057587a60`。

`build_archive_disposition_partition_receipt.py` 只读取 observer metadata，并证明 218 个 archive 的分区互斥且完备；
`verify_archive_disposition_partition_receipt.py` 从冻结 observations 独立重算计数、原因与四个 mapping hashes；
`build_structural_rejection_ledger.py` 再从 12 个单归档 registry、相邻 diagnostic receipt、最终 structural gate 和该
partition receipt 重建结果；`verify_structural_rejection_ledger.py` 独立重算计数、原因分布、分数和竞赛时间线。

## 结论边界

这里没有读取 label、grade、outcome、winner orientation 或 prediction value，也没有计算 accuracy、方法效果或 search
utility。6/6 mixed disposition 只证明 archive-specific validation 必要，不估计 producer metadata 修改的因果效果，也不说明
被拒收归档的模型质量较差。
