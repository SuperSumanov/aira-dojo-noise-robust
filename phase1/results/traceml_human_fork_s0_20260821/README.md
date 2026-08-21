# TraceML human-fork future transfer：S0 输入与 schema 绑定

日期：2026-08-21。状态：`TRACEML_HUMAN_FORK_S0_INPUT_AND_SCHEMA_BOUND`。固定 release revision 为
`61faec615b179f186dbe9c82ee59d17e14817e96`；远端 HEAD 在下载时与之相等。已下载并逐文件哈希
`nodes/edges/trees/kernels.parquet`、`competitions.json`、两份官方 graph builder、README 与 LICENSE；没有下载
`trajectories_human.tar.gz`。

S0 只打开 Parquet schema/footer，未读取任何 column values。footer 记录 nodes=174,558、edges=3,995,719、
trees=2,721、kernels=4,847；所需 node/kernel/parent/depth/edge-kind/raw-code-path/best-private/score-direction 字段存在。
官方 builder 源码的 canonical priority 精确为 `version > fork > code_sim`。

固定 `competitions.json` 是 141-entry mapping，而 dataset card 文字是 134 competitions。S0 不猜测多出的 entries；
S1 必须逐 graph competition 唯一匹配 direction，并检查 node/kernel `score_is_max` 与 manifest 一致，未使用的 manifest
entries 也必须报告。任一不一致即 `IDENTITY_OR_JOIN_AMBIGUOUS`。

输入合同：`phase1/traceml_human_fork_s0_input_manifest.json`。schema reader SHA-256=
`9817eae5f1377cab7f6f2696c42fa20b49af026db1be7f1c487a680db3d84506`；schema receipt SHA-256=
`64859cea7fbb33df1031be41f898be17fed08870b03555d23626a8e0ef8631cb`。本阶段 support aggregates、score values、
raw notebook content、GPU/API 均为 0。
