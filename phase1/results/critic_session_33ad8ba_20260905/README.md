# 合格来源包与新训练入口：2026-09-05 接入进度

结论：新 consumer 的普通 DDP 训练、阶段切换和完整保存/恢复已接通并复验；
**合格真实数据 caller 和生产 ZeRO-3/bf16 保存/恢复尚未完成，不能开始正式效果矩阵。**
这不是 G-reuse 或 scaling 的新正结果。G0 12499 的真实双卡完成记录另见
`../critic_component_g0_r5_20260905/terminal/README.md`；原 Trainer 的成功不替代这里的新入口验收。

## 1. 数据端：文件存在，但生产事实尚待确认

本轮再次 fetch，学长分支仍为 `b8d095180415957aa1bab31fa53ead1bba261c03`。
Cards、G、L、split 四项 LFS 元数据仍指向同一发布提交
`5baccb170ce287f9c8eed7b23ccf693a0268515a`，不是发现了新的完整来源包。
同一 Git 发布不证明相同实际 producer/config 或 whole-experiment 隔离。
数据目录的来源/生产/评分回执命名匹配仍为零，但没有据此断言其它位置不存在记录。

没有解析这些 payload。学长只需补三项已有生产事实，不需要重传全集或手写七份声明：

1. 哪些原始记录允许用于历史开发，以及远端位置；排除 first-960、Target-300、Target-522。
2. experiment 的实际定义、run 到该单位的映射和出处。
3. 实际生成/评分使用的版本、配置和执行记录位置；不可追溯的项保留 unknown。

详细交接及四个确切 LFS SHA 在 `../../SENIOR_MINIMUM_SOURCE_HANDOFF_20260905.md`。
现有声明包 validator 只证明声明/文件哈希相符，未被升级为实际来源资格认证。
非阻塞补充问题已发给用户；没有向学长擅自发送消息或编造生产事实。

## 2. 已落地的新入口能力

`global_local_critic_session.py` 直接调用已有 `PlannedCriticConsumer`，不重写 loss、batch、
token 预算、LR 或更新归一化。调用方提供已准备的模型、优化器、输入和绑定后的训练配置。
模块本身不打开语料、不构造模型、不提交作业；配置摘要不是输入资格或算力授权。

- 保存 model、AdamW、各 rank 的 Python/NumPy/Torch RNG、实际完成步数和 token cursor。
- 清单绑定 plan/input/runtime、seed/arm、模型结构、优化器初始配置与入口源码。
- 所有 rank 文件先核哈希，加载后再核真实状态，最后推进 cursor；失败后不复用已部分加载的进程。
- 沿用旧 CPU 原型的限制，不删除 guard。普通 GPU-DDP 路径也尚未经过硬件验收。
- DeepSpeed/FSDP 在这个 session 中仍显式拒绝，没有为了“接通”而跳过恢复检查。

## 3. 固定配置与真实检查点复验

结果前代码：`33ad8baca0f23fd54ea4e79c5c23f3c44bbef2ec`。
奖励模型结构来自固定 source `5f3bc362db922c8edee2ef134656dfdb9a2b74fb`；只构造随机 tiny Qwen3，
没有读取预训练 checkpoint 或真实输入。4433 参数、float32、AdamW、attention dropout=0.1、seed=6、
两 CPU/Gloo 进程，每进程一线程；CUDA 不可见，离线环境，整个 A/B wrapper 上限 20 分钟。

两臂为 `G_to_L` 与 `Ghash_to_L`，不是效果对比；方向控制臂不读取 G 真值。
每臂完整运行至 4 步，另在第 2 步（G→L 边界）和第 3 步（L 阶段）保存，再从全新进程恢复。
恢复进程故意使用不同初始随机状态，且每步实际消费 Python/NumPy/Torch RNG。
完整与截断轨迹在相同位置保存，避免保存副作用造成不公平比较。

|验证|结果|证据|
|---|---|---|
|consumer + session 单元测试|40 passed|`tests.txt`|
|独立 A/B，每次 10 个分布式轨迹|均完成；summary、CSV 和全部 trajectory 逐字节一致|`a/`、`b/`|
|最终模型、AdamW、各 RNG 指纹|每次 8 个恢复后的 rank 比较完全相同|各 `trajectory.json`|
|独立直接加载实际 checkpoint 比较|16 组 model/AdamW/各 rank RNG 全部相同|`independent_verification.json`|
|所有检查点清单及文件哈希|36 个检查点通过|同上及各 `manifest.json`|
|前缀+恢复后的消费序列|16 个 rank 组合精确等于完整序列|同上|
|运行前导出的源码对照|DDP 18 个、DS observer 6 个文件均未改变|同上|

这里的 A/B 是同 seed 的独立执行重现，**不是跨 seed 的方法证据**。验证器没有调容差：要求逐位一致。
独立检查脚本不导入 session/consumer 实现，直接对本轮自己生成的 safetensors、AdamW 和 RNG 内容作比较，
不是仅重复读取汇总中的 `pass=true`。包含 NumPy 的 RNG pickle 只在核清单后读取本轮私有合成产物；
它不是接受任意不可信 pickle 的通用入口，也不是外部攻击者模型下的文件系统隔离证明。

## 4. DeepSpeed 源码发现与修复边界

固定环境中 `Accelerator.load_state` 不向上返回 `engine.load_checkpoint` 的返回值。
实际 DeepSpeed 源码在 `_load_zero_checkpoint` 返回 False 时会调用 `_restore_from_bit16_weights`，
因此“函数返回/权重加载成功”不能证明优化器分片已恢复。
**这是源码分支风险，不是断言 G0 曾触发它；G0 没有做完整 resume。**

提交 `6d425476aff3394f10442befc4d1f7c7bccd4e04` 在既有 DS 适配器增加单次恢复观察器：
分片恢复失败就在 fallback 之前抛错，核 strict/full-optimizer 标志、client binding 与恢复步数，
失败后的 engine 不可原地重试；上下文退出恢复原方法属性。

25 项单元测试通过。另以真实 `DeepSpeedEngine.load_checkpoint` 方法和 CPU 测试接收器核验两种分支：
未加观察器的失败控制确实进入 fallback；加观察器后失败在 fallback 前停止，成功分支则完成绑定检查。
未初始化真实 DS engine、未加载 DS checkpoint、未申请 GPU。这**不是双卡 ZeRO-3 恢复通过**。
真实方法 SHA 为 `5728d3dfa42a3d6c44836873002f5ccfb9e72091c98029b3843b30ec5651161f`；
原始结果见 `ds/source_control_flow.json`，警告与测试输出保留在 `ds/source.log`、`ds/tests.txt`。

观察器本身不管理分片文件、不证明实际优化器/RNG 内容相同，尚未解除 session 的 DS 拒绝。
下一项实际实现是接入 DS 分片清单、全 rank 状态指纹和保存/恢复生命周期，然后单列精确双卡验收预算。
不得先开真实数据 fit，再把退出码当作上述工作已完成。

## 5. 复现、原始证据与剩余准入

环境：Torch 2.11.0+cu128、Accelerate 1.14.0、Transformers 5.12.1、DeepSpeed 0.19.3、
safetensors 0.5.3、NumPy 1.26.4。运行参数与命令保留在 `run_ddp.sh`、`run_ds_observer.sh`；
这些是当时新私有目录的原始 wrapper，不应直接复用既存输出目录。
独立核验源码提交 `da95a9cb316fe6f21bc9396b6d97551e1a894bb4`，审计脚本 SHA
`2f15bb6adc59bc01d9dbbe315b9cbf6397816ce471b9b322c0bf511922981fbb`。

运行目录为远端 `/tmp/critic-session-33ad8ba-vod7xI` 与 `/tmp/ds-restore-6d42547-ufPK0D`。
安全导出包 SHA `896ac2c514072288a26bd40ecbf2c30145d1701e13c3d451ff5997c2f04d23b3`，
只导出清单、结构轨迹、汇总、日志，不含二进制 checkpoint、真实语料或标签。
`artifact_inventory.json` 绑定这些导出文件，下载后本地逐项复核通过。
日志中的 CPU accelerator 探测与 NFS Triton cache 警告原样保留，未宣称这里不存在环境警告。

本轮全程在当前会话推进，未新建定时任务，`g0-r5` 继续暂停。没有新增 GPU、付费 API、真实语料训练，
没有读取保护 cohort。旧失败记录与科学成功门不改。

完整生产接入还有两个实质缺口：**实际来源事实支持的训练包**，以及**ZeRO-3/bf16 的真实保存恢复验收**。
原 G0 的剩余预算不自动授权新 fit；开发 pilot/正式矩阵也仍需各自固定配置与预算审批。
不能把本轮的工程正确性累计成新的 critic/scaling/search 正效果或录用概率提升。
