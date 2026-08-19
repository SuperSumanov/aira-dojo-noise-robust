# Prospective operator support v1

日期：2026-08-19。裁决：`INSUFFICIENT_OPERATOR_RANDOMIZATION_SUPPORT`。

结果前 commit `1740d513b7ea2fc497c3906ca80771b52bdef91c` 固定了 outcome-blind 结构审计。输入是
35 个 append-only transactions、197 个 eligible physical runs、23 tasks 和 4,424 endpoints；未打开
label vault，未读取 numeric grade/outcome，未输出 raw code，GPU/API 均为 0。

远端完整测试为 `387 passed in 31.57s`。producer 两次运行的三个产物逐字节一致，summary SHA256=
`ce611700a9afa5a9f543f57992ef3b1033bbfa20198d8e78dc4d2759561ca0d5`；不 import producer 的 verifier
对两份产物均给出 `INDEPENDENT_OPERATOR_SUPPORT_ARTIFACT_VERIFIED`，verification SHA256=
`d91405269b20df4e9abcd4dd7d391e9218f530472d05aed1ba78974c2301a092`。

单节点边际计数是 Debug=2,034、Improve=1,998、Draft=392，且 Debug/Improve 分别覆盖 23/22 tasks；但
3,229 个 nonroot parents 中，mixed-operator parent=0、mixed tasks=0、exact-two mixed parent=0。因此
三个 parent-support 门全部失败，dominant share 在空支持下不可定义。

这说明现有生成数据中的 operator 多样性发生在 parent 之间，而不是同 parent siblings 内。当前语料不能支持
parent-matched operator effect、随机化自然实验或因果主张。未来若主动把 operator assignment 改为 child 级，
那是新的生产干预，需要独立 scheduler event stream、预算 ledger、预注册和用户批准；本结果不授权它。
