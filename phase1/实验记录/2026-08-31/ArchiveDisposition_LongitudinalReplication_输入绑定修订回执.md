# Archive disposition longitudinal replication：输入绑定修订回执

- 初始冻结 commit：`d821a55c93ef5efd7877f57176bf916471bded4f`。
- 初始 live-observer SHA：`3b0780991fd55fde5d49f1dbd56ff28a27513cf3d71a74954d00e8367df5f470`。
- 失败位置：fresh worktree 完成后、focused tests 与 producer 启动前；不存在 result/verifier 文件。
- 诊断状态：observer 仍为 194,489 bytes；LATEST 未变；source=275；baseline/accepted/rejected/pending=`128/126/21/0`。
- 修订输入：远端私有只读快照 SHA-256
  `dccd59d9e3fe964aabce2458647013d772070c40a120f79f9a6b02605356e855`，194,489 bytes。
- 修订边界：没有读取 competition identity、mixed-disposition 聚合、rejection reason 分布、标签、结果、预测、accuracy 或
  utility；没有运行 GPU、API、模型训练或底座更新。
- 不变项：Strong/Partial/Kill 门、历史锚点、competition 解析、archive disposition 定义与全部 claim boundary 均未改变。

该修订只消除 live observer 的观测状态字节漂移，不改变科学问题或判定条件。初始失败目录保留在远端，不做覆盖或删除。
