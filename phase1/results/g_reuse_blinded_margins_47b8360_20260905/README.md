# G-reuse label-blind margin materialization

状态：`LABEL_BLIND_MARGIN_MATERIALIZER_READY_NOT_MODEL_SCORED`。

本结果冻结了从无标签 endpoint scalar 到匿名 pair margin 的唯一方向：endpoint ID 先按字典序形成
`left < right`，pair identity 为 `sha256(left + NUL + right)`，每臂 margin 恒为
`score(left) - score(right)`。输入 support 必须逐项等于所有 pair endpoint 的并集；输出只含
pair/task/parent/run SHA 和 16 个 margin，不含 raw endpoint ID、truth、outcome、accuracy 或 utility。

结果前源码 commit：`47b83604e489309f6221b3b3770c6667160733b8`。

Linux exact deployment：

- archive SHA-256：`5b26287690d0c39b62a21d3b7e62f8935c1257020c65fd96c4d002b234e07088`
- root：`/research/d7/spc/yzyang4/g-reuse-blinded-margins/formal-47b8360-v1`
- 两次独立测试执行：`10 passed`、`10 passed`
- protocol SHA-256：`1b13bd111f074d9f4a703fe2e04a1dc06a46eb3d5dbd329daa85fcd45e122edd`
- producer SHA-256：`1c936389e8fd8eab288be0f9e9a92733285f66209d666a58768b2a9e0a108248`
- independent verifier SHA-256：`108c697160b6fff8258dff687d06341f601cb7c7dd7d05b8c135c16519c8ece7`

合成负控覆盖 orientation、truth字段、missing/extra endpoint、NaN、pair hash、重复 endpoint score
和输出 margin 篡改。producer 与 verifier 分别解析、核 hash 和重算差值。

边界：这里没有真实模型分数、checkpoint 或效果读出。通过只证明物化层定义确定且双实现一致；不证明
checkpoint 合法、模型推理未访问标签，也不证明 G-reuse 优于任一对照。GPU、付费 API、model fit、
protected-value read 均为 0。
