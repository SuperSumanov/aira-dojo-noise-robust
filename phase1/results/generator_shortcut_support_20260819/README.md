# Generator/client shortcut structural support v1

日期：2026-08-19。正式裁决：`INSUFFICIENT_GENERATOR_SHORTCUT_SUPPORT`。

结果前 commit `3048d2236031e3f9b11305d98996c69f7cc053fd` 固定 5-fold physical-run OOF、严格
same-environment pool 与六个支持门。正式 Linux 环境先通过 `393 passed in 35.10s`；producer 双跑逐字节一致，
不 import producer 的 verifier 两次独立重建一致。summary SHA256=
`59e607e5f62973d515780d8f5881cb69aa47011b5b569242df04292b0bf11cfe`，verification SHA256=
`6032a80dbfa20fca921ac0b85a004a6d82b23a411c9b4647a3ff9e4b1abfb596`。

锁定 augmented train 数据为 31,742 cards / 676 runs / 28 tasks / 11 clients / 11,946 train pairs，client
缺失 run=0。关键结构事实是 **11,946/11,946 pairs 均为 same-client，cross-client=0**；5-fold OOF 可评估
5,318 same-client pairs / 28 tasks，但 cross-client/same-environment 仍为 0 pairs / 0 tasks。因此两个
cross-client 支持门失败，正式状态必须是 `INSUFFICIENT_GENERATOR_SHORTCUT_SUPPORT`，不启动预注册的
client-prior/TF-IDF/static 效果实验。

这直接排除“value-pair critic 仅靠比较 pair 两端的 generator/client identity”这一强解释；它不排除同一 client
内部的 run style、搜索阶段、代码模板或其他表面捷径。不得把 0 cross-client 解释成“无 shortcut”，也不得改成
跨 pair 的 client 平均质量分析后追认原假设。

本轮不读 test、v11 frozen、0812 temporal vault、numeric grade 或 raw code，GPU/API/模型更新均为 0。
