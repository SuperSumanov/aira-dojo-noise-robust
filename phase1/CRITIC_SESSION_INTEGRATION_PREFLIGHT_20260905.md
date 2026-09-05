# 新critic运行入口：保存/恢复接入预检

基于91ca591（G0 12499已完成）。本轮用户指定继续“合格数据来源包与新训练入口的生产接入”。
目标是把现有真实模型consumer接到持续运行和完整checkpoint生命周期，而非新增方法臂。

## 数据侧

再次fetch与远端LFS元数据核验，学长head仍b8d0951；四项同发布来源未变，数据目录来源/生产/评分回执0项。
未解析payload。已经向用户发出非阻塞补充问题：允许历史开发的原始记录位置、experiment真实定义及映射、
实际生成/评分版本出处。现有声明包validator只检查声明/哈希，不得当作来源事实成立。

## 本轮实现及限制

- 新`CriticSession`直接驱动现有`PlannedCriticConsumer`，不另写batch/loss/optimizer更新逻辑。
- 完整framework checkpoint：model、optimizer、各rank RNG，另存plan/input/runtime/model/optimizer绑定与token cursor。
- 全rank文件在反序列化前核对；加载后逐项比对状态指纹，再推进cursor。失败毒化当前consumer，不就地重试。
- 复用既有atomic JSON和restored-state比较，不修改两参数CPU旧checkpoint guard。
- 此模块无dataset/label reader、模型构造或调度接口；调用方仍须合格输入与GPU预算，哈希不能代替授权或事实。
- 支持代码路径为普通Accelerate DDP；**DeepSpeed/FSDP保存恢复继续显式拒绝**，不把未验证的ZeRO3接入包装为成功。
  已核精确Accelerate源码：DS分支自己调用engine.save/load_checkpoint，且load返回值不向上传递，需单独校验。
- 本轮新GPU/API/真实语料fit为0。不会消耗G0剩余预算，正式15-fit/开发pilot仍未启动。

## 结果前固定CPU验收

固定G0运行环境、原source定义、随机tiny Qwen3（4433参数）、float32、真实AdamW、seed6、两CPU/Gloo进程。
仅G_to_L和Ghash_to_L；每臂uninterrupted、prefix2/resume2、prefix3/resume3，共10个分布式轨迹。
2/3分别覆盖G→L边界及L阶段后续恢复；A/B各跑一遍。模型注意力dropout启用，以检验实际随机状态恢复。
每个rank仅1线程，总墙钟上限20分钟；每进程组超时60秒。全部在新私有/tmp目录，禁止GPU上下文/真实输入读取。
期望同臂各cut的最终模型、AdamW、Python/NumPy/Torch RNG及累计tokens与未中断路径**逐位相同**，不设置可重选误差。
完整/截断轨迹在同样step保存，避免保存改变随机状态造成对照不一致；恢复进程故意用不同初始RNG作负控制。
这只证明新入口的CPU-DDP模型生命周期，不是生产ZeRO3/bf16或方法效果认证。
