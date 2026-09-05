# ZeRO-3 session 接入：结果前计划

基于 `62a450faf0be5e13b30204bdb1fb1974db383a58`。用户要求继续剩余生产接入工作，
在当前会话实现；数据的生产事实仍待提供，不扩大旧来源资格或读取保护 cohort。

## 实现范围

复用现有 consumer、token plan、BT loss、更新/恢复观察器和 DDP session 的哈希/游标工具。
新增显式 ZeRO-3 session，不删除普通 DDP 和旧 CPU 原型的 guard。仅支持实际固定版本、
两路纯 DP、全参数 critic、BF16、CPU-offload AdamW；拒绝 TP/PP/MoE、NVMe、elastic、
Universal Checkpoint、额外 scheduler、混合溢出或未完成梯度的恢复。

完整生命周期必须含每 rank 模型分片、FP32 master、AdamW 状态、RNG、进度计数器和 client binding。
先核全文件与明确给定的 manifest SHA，再调用完整 DS 恢复；禁止 latest 猜选与权重-only fallback。
实际张量/优化器/RNG验证通过后才恢复已保存的额外计数器并推进 token cursor；任何失败使进程不可重试。
这只是生产组件实现，非数据来源资格认证；无 GPU 验收前不称 production ready。

## 先做的 CPU 检查

固定方法和文件 SHA，核 DS 实际 checkpoint 命名、全 rank 输出、FP32 master/AdamW 布局和计数器恢复语义。
对读取门/错误分片/错误 rank/游标/缺失文件/优化器失败作故障测试；使用合成文件与 CPU 测试接收器。
必要时对实际 pinned DS state_dict/load 方法做受控 CPU 张量 round-trip，不初始化 GPU、不读取语料。
单次 CPU wrapper 上限 10 分钟，计算线程最多两条；不改既有 runtime 或 source worktree。

## 待用户批准的真实 GPU 工程验收

- 一个 Slurm 作业，两张 PRO6000，时限 30 分钟、no-requeue；加 300 秒 KillWait 与 60 秒余量，
  上界 `2*(1800+300+60)/3600 = 1.2 GPU·h`。不因原 G0 尚有余额就自动启动。
- 固定原成功 runtime、随机 tiny Qwen3 4433 参数、BF16、ZeRO-3 CPU-offload AdamW、seed6。
  synthetic input/短 context、同一 arm G_to_L；没有模型下载、真实训练集、dev 或 protected 数据。
- 五条轨迹：完整4步、prefix2/resume2、prefix3/resume3；同处保存，恢复使用全新进程和不同初始 RNG。
  显式覆盖 G→L 边界与 L 内部恢复，不新增科学方法臂。
- 期望最终分片参数、FP32 master、AdamW、RNG、完成步与消费序列逐位相同，不事后调容差。
- held 核实际资源/时限/无重复后才 release；输出独立，回执/实际设备/访问 trace 均须保留。
- 这是新入口的真实 ZeRO-3 恢复工程验收，不是 1.7B/16K 内存验收或 G-reuse/scaling 效果。

截至本计划写入，已向用户提出上述明确预算问题，尚未收到批准；没有提交新 GPU 作业。
