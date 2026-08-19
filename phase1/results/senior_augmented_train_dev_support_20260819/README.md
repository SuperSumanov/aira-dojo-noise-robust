# Senior augmented train/dev support v1

日期：2026-08-19。裁决：`INSUFFICIENT_TRAIN_ONLY_DEV_SUPPORT`。

结果前 commit `af51c8cefae81faeeafa34a673282949e99ad042` 固定了 physical-run-clean
train/dev 划分、0.25/0.50/0.75/1.00 nested curve 与全部资格门。输入来自学长
`dojo-reproduce` commit `92a9651f2e13a9e43623235b82c07c19721bc2ee`；四个 LFS 输入在解析前完成
高置信 credential scan，命中数为 0。本轮不读取 numeric grade，不训练模型，不使用 frozen test 做 validation，
GPU/API/底座更新均为 0。

远端完整测试为 `390 passed in 35.43s`。producer 双跑逐字节一致，summary SHA256=
`7745dd157e41dc96a00ac76979afa6369f06395b0aa8ad67756de4d84e7297e8`；不 import producer 的 verifier
两次均通过，verification SHA256=
`205d89fa1b4db4cc7fec9fb52ae6b61bc467828c9a8a972f75c787b02b32d1e2`。

原始 split 结构一致：11,946 train pairs、1,574 test pairs、0 split inconsistencies；148 frozen-test runs
没有进入 train/dev。固定哈希划分得到 430 train runs、92 dev runs、6 low-support excluded runs；dev 有
626 pairs / 23 tasks，最大任务占比 `0.16932907348242812`，9 个任务至少 20 pairs。四层训练 pair 数为
1,118 / 3,061 / 5,798 / 9,001，样本规模支持充分。

唯一失败门是同实验配置配对：dev share=`0.9808306709265175` 通过，但 full-train share=
`0.9213420731029885`，低于结果前固定的 0.95。它表示约 7.9% full-train pairs 的两端在
`(client, hardware, time_limit, execution_timeout)` 上不完全相同。为避免把运行配置差异当成模型 scaling，
本数据不启动确认性 TF-IDF learning curve，也不事后降低阈值或筛选配对。

保留下来的正面资产是：冻结 test 隔离正确，train-only dev 的任务/样本支持充足，且审计链可复现。下一步只做
outcome-blind 的 mismatch 来源定位，并为未来新增语料固化 exact experiment-stratum pairing contract；修正后的
未来 cohort 另行预注册，当前数据最多作为探索性诊断。
