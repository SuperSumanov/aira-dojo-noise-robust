# ZeRO-3 主体实现与恢复核验（2026-09-05）

本轮按用户“继续推进剩余工作，不要停”在当前会话完成代码、检查与交付准备，未创建定时任务。
**相较上一轮，ZeRO-3 已不再只有观察器：完整 session 主体和真实双卡验收入口已实现。**
但它仍是实验性接入，真实 DS engine / 双卡 GPU / CPUAdam 完整路径尚未运行验收；
不能声称生产 ready、开始正式训练，或有了新的 G-reuse/scaling 收益。

## 实际实现

`global_local_zero3_session.py` 复用既有 consumer 的训练执行与 token cursor，不改 loss、LR、batch 顺序或方法臂。
新增显式 `DeepSpeedCriticSession`，普通 DDP 与旧两参数原型的 guard 未放开：

- 固定两路纯 DP、dense BF16 ZeRO-3、CPU-offload AdamW；拒绝额外 scheduler、NVMe、elastic、Universal、TP/MoE。
- 保存/核验每个 rank 的模型分片、FP32 master、AdamW、随机状态和实际 token cursor；不聚合完整模型到单卡。
- 明确绑定 checkpoint 清单和 SHA，拒绝缺失分片、链接、额外文件、`latest` 猜选、损坏和错误 rank。
- 用已有恢复观察器阻止优化器失败后退回仅恢复权重；核验实际内存中的全部状态，而非仅检查 load 返回。
- 固定 DeepSpeed 源码恢复 global_steps/global_samples/skipped_steps，但未完整恢复其它进度计数器。
  本接入保存 micro_steps/micro_step_id/step_applied；先核实际状态，再恢复这些计数器，最后提交 consumer cursor。
  `global_samples` 只是框架计数器，**不是** partial batch 的真实消费量；消费量仍来自原 token/pair receipts。
- 对非有限 master/模型分片/AdamW 拒绝保存或放行；分块核验，避免一次性聚合大权重。
- 任何失败毒化当前 consumer，不能在部分恢复后的 live engine 上就地重试。

入口没有语料加载器、模型下载器或作业提交接口。绑定哈希不替代输入资格、GPU 预算或对不可信 pickle 的隔离。
底座 agent 没有更新；这个组件是独立 critic 的运行支持。

## 诚实的测试过程

|版本|实际结果|说明|
|---|---|---|
|`9c5179b65564019c65b50fa69dbafa7137378369`|69 tests passed，真实分片方法的 CPU round-trip 通过|当时还未覆盖整个 session 恢复成功分支，不能据此称完整恢复已通过|
|`bd1673c83b19b36207b064e18c5d803e3937a819`|1 failed，92 passed|新加的整体恢复调用测试发现错误：DS 新状态字段仍传给旧 DDP 固定字段比较器；合法恢复也会被拒绝|
|`f4d58348330a70c1d3c8634e8c419bab472fb932`|100 tests passed，分片 round-trip 与继续更新再次通过|改成严格比较 DS 的全部状态角色，不改旧 checker、不放宽容差；新增逐角色缺失/篡改覆盖|

失败是我方集成错误，不是语料问题，也不是应忽略的测试 fixture 错误。原失败日志在 `r2_failure/tests.txt`。
它在新 GPU 提交前被发现；本轮新增 GPU 作业为零。

最终测试包括严格文件清单、逐分片/RNG 损坏、rank/计数器、非有限状态、权重-only 防退回、
完整恢复成功以及最后一步验证失败时 cursor 不得前进。GPU 入口的运行环境/两卡/明确配置绑定检查也在其中；
这类环境检查不是能防止调用者伪造批准的安全机制。

CPU round-trip 使用**固定真实 DeepSpeed Stage-3 的 `_rigid_state_dict/_rigid_load_state_dict` 方法**，
接收者是 CPU 测试对象、优化器为 Torch AdamW，不是真实 DS engine/DeepSpeedCPUAdam。
保存并加载实际 tensor checkpoint 后，FP32 master、BF16 分片、AdamW 状态相同，继续一步更新仍相同。
故意 `load_optimizer_states=False` 的负控制保留 master，却未恢复 AdamW，被完整状态观察识别。
因此它核验的是方法接口和内容观察，不是 GPU 集体通信、真实优化器内核或 1.7B/16K 运行能力。

R1 和 R3 各自生成的两个合成 checkpoint 经独立文件 SHA 比较，字节一致：

- rank0：`a251c8cff2341f1df59c45afe1b2c14151013719e3a3a95c085311080722ab55`
- rank1：`deb9204afdd92d55a81821c6aed6b91c525fad4a504f73fa3be040109aa82c13`

两个测试 rank 并非一次真实分布式执行，也不能作为两个独立科研 seed。随机 seed 固定为 6。
R3 的 22 个导出源码文件与结果前 archive 逐项相符；本轮不修改运行环境或原 source worktree。
`postcheck.json` 的 `payload_reads=0` 特指**真实语料 payload**；其中确实读取了上述自生成 checkpoint 的字节以核 SHA。

## GPU 验收已准备，尚未提交

已实现 `scripts/validate_zero3_session_gpu_20260905.py` 与
`scripts/zero3_session_engineering_20260905.sbatch`；后者语法检查通过，不会自行提交。
复用 G0 已成功的 runtime 和目标节点工具链检查，独立输出与编译缓存，记录设备、资源、文件访问和退出状态。
不调用旧 G0 的真实语料/model loader。

提请用户批准的精确工程配置保持：

- 一个作业，两张 PRO6000/projgpu39，30 分钟、no-requeue；加 KillWait/余量的 GPU·h 上界为 **1.2**。
- 随机 tiny Qwen3 4433 参数，BF16、ZeRO-3 CPU-offload AdamW、seed6、合成短输入。
- `G_to_L` 五条轨迹：完整4步、prefix2/resume2、prefix3/resume3；比较最终全部状态和实际消费顺序。
- 不读真实 train/dev/保护 cohort，不新增科学方法臂，不作收益/速度结论。
- 批准后仍须固定完整 control、核 storage/source/runtime、无重复作业，再 held 核 Slurm 字段后 release。
  脚本存在和 CPU 检查通过不替代这些提交前检查。

本轮已在会话中提出上述预算，**尚未收到批准，也没有利用原 G0 剩余额度自动提交**。
GPU 通过后才进一步安排真实规模/合格数据开发训练；tiny GPU 工程验收本身仍不认证 1.7B/16K 的内存和吞吐。

## 来源包与下一步

再次 fetch，学长 `dojo-reproduce` 仍为 `b8d095180415957aa1bab31fa53ead1bba261c03`。
已知共享 Drive 根单次 metadata 请求：43 children、37 日期目录，最新0903，无0904/0905，未下载语料 payload。
这只覆盖已知入口，不能证明他在其它地方没有上传。
来源资格仍缺允许的历史开发范围、真实 run→experiment 定义/映射、实际生成/评分出处；
详见 `../../SENIOR_MINIMUM_SOURCE_HANDOFF_20260905.md`。本轮未把同一发布、声明布尔值或旧 test 改名当作资格。

最短后续路径是批准并完成真实 ZeRO-3 硬件验收，同时补齐一个实际可用开发包，然后固定开发效果预算。
不是继续增加谱 selector 或用工程测试数量代替模型效果。0L45 的 full G-reuse→L 假设和冻结成功门保持不变。

## 证据位置

原始 CPU wrappers 为 `run_r1.sh`、`run_r2.sh`、`run_r3.sh`；每次新私有输出，上限600秒、计算线程1，GPU不可见。
R3 源码 archive SHA：`ef997ea48cbd3dd944d037d12db7ea55ea14ea007c559ec9e6d9e7c7f09d250a`。
安全结果包 SHA：`407ed84307c130cb2f80aa631f3784d9002929da7e4456d646b41f2773cb59e9`，下载后8项清单核验通过。
原始日志、成功/失败结果与运行库精确绑定均已保留；不导出二进制 checkpoint、真实数据或密钥。
实验规范在运行前固定范围与成功标准；发现缺口后增加针对性故障覆盖，没有重选漂亮结果或放宽比较标准。
