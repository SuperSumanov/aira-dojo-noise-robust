# TraceML Human Fork Future：S0 输入绑定与 schema 预检

日期：2026-08-21。状态：`S0_PASS_WITH_MANIFEST_CARD_COUNT_DISCREPANCY_REQUIRING_S1_CHECK`。

预注册 commit `76e91fd...` 在任何 graph support 或 score 值读取前冻结。随后从公开固定 revision
`61faec615b179f186dbe9c82ee59d17e14817e96` 下载四个 graph parquet、competition manifest、官方构建源码、
README 与 LICENSE；远端 HEAD 精确等于固定 revision，raw notebook archive 未下载。逐文件 size/SHA 已写入
`phase1/traceml_human_fork_s0_input_manifest.json`。

schema reader 只使用 Parquet footer/schema 与 JSON key/direction category，不读取任何 parquet column values。
metadata 行数为 nodes=174,558、edges=3,995,719、trees=2,721、kernels=4,847；需要的 identity、canonical parent、
depth、fork kind、kernel eventual score、score direction 与 raw path 字段全部存在。官方代码 literal 同时确认 canonical
parent priority=`version > fork > code_sim`，因此 S1 可以严格只选 chosen `fork`，不需要 heuristic 重建。

唯一预检异常是 `competitions.json` 有 141 个 mapping entries，而 card 写 134 competitions。它尚不等于 graph join
错误，但禁止静默按 card 数量裁剪。S1 已被输入合同强制要求：每个 graph comp 恰有一个 manifest direction；node 与
kernel 的 `score_is_max` 必须一致；所有未被 graph 使用的 manifest entries 单列。任何失败即
`IDENTITY_OR_JOIN_AMBIGUOUS`，不计算支持门、不下载 2.9GB raw code。

schema receipt SHA-256=`64859cea7fbb33df1031be41f898be17fed08870b03555d23626a8e0ef8631cb`；
reader SHA-256=`9817eae5f1377cab7f6f2696c42fa20b49af026db1be7f1c487a680db3d84506`。本阶段
score values/support aggregates/raw code/effect metrics/GPU/API 均为 0。
