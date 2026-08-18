# Probe-First Artifact Contract A/B V2：正式无效与事后诊断

日期：2026-08-19。四个冻结 replay shards 11160/11161/11162/11163 分别在 719/737/547/600 秒完成，
全部 `COMPLETED 0:0`，16/16 index 完整。replay 实际 allocation=2,603 GPU 秒，含 generation 共 25,731 GPU 秒
=`7.1475` GPU·h；API=0、底座更新=0。

冻结 primary validator `rc=0`，得到 coverage `4->4`、gain=0、contract probe=4/8、full-valid `6->4`、
paired quality=4、median relative oriented full delta=`-0.0014093470316371487`、catastrophic harm=1。
K0/K1/K2 失败、K3 通过，点裁决为 `QUALITY_KILL`。

独立 verifier 在重建数值后、比较 gate map 时 fail-closed。根因是 primary `classify(summary,"v2")` 数值上使用
正确的 `quality_pairs_min=4`，但 gate 名仍硬编码成 `quality_pairs_at_least_3`；独立 verifier 正确写
`quality_pairs_at_least_4`。这是冻结前测试只检查 gate values、没有检查 V2 gate schema 一致性造成的实现缺口。
按预注册“任何双验证失败均 INVALID”，本轮正式状态固定为 `INVALID_INDEPENDENT_VERIFIER`。

事后只做影响诊断，不修复正式结果：原 primary SHA=
`1459de4c2bbe4ef77a0540669379aa70c907cc6b6dd3e3ed95492e98ed20b34a`；在独立目录只重命名 gate key，
scientific scalars unchanged，corrected SHA=`df9c0cfb8e58709cb07e8dcdbe22069c8254cfe4fd477f9405494c3683367064`。
冻结独立 verifier 随后完成 30 次唯一 artifact regrade，结果 SHA=
`d9fbac4003745d93b6c571d8f207f05995f2268cf51808d83c1c334e612a3326`，与 primary 的 verdict、gates、summary
全部一致，仍为 `QUALITY_KILL`。

因此不能声称这是有效确认性负实验，但可以得出开发裁决：bug 只影响字段名，未遮住正结果；当前 prompt-only
artifact contract 没有提高 120 秒 coverage，且 full validity 更差。禁止按 outcome 改 prompt、任务、阈值或补样，
该正方法线关闭。代码修复仅把未来 gate 名改成由 `spec.quality_pairs_min` 生成，并加入 primary/independent V2 schema
一致性回归测试；它不改变或覆盖本轮原始产物。
