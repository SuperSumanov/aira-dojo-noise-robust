# ForeTS设备映射错误：停止与撤回

2026-09-11香港；本报告supersede显式设备方案中的“隔离已解决”泛化结论。

## 事实

- 13037：新namespace只露设备0，OpenCL loader缺失；13038：多个loader alias冲突，未启动容器。
- 13039：固定loader后，无ICD为0平台；有ICD进入native拟合但abort。诊断HOME不可写。
- 13040：改为实际任务使用的可写workspace/home，设备0上LightGBM GPU和原Torch CUDA运行成功。
  SIF未改，未升级Torch，不用CPU fallback。这是局部库兼容事实，不是正确Slurm设备映射的独立证明。
- 13041：真实Jupyter入口启动失败。随后在有界13042内只读查询发现：gpu28的Singularity在/usr/bin，
  而登录机在/usr/local/bin；第一次adapter错误沿用了登录机路径。
- 13042：修正路径后两个实际Jupyter步骤均完成了人工OpenCL GPU拟合与CUDA运算；
  step 1的SLURM_STEP_GPUS=0，程序选择minor0；step 2的SLURM_STEP_GPUS=1，程序选择minor9。
  **后一项实际使用了设备9，不只是看了元数据。它是否获该step分配没有独立证据，因此此项不合格。**

## 为什么此前门不够

代码将SLURM_STEP_GPUS的整数作为nvidia-smi可见index，再将UUID解析为physical minor。
之后“实际可见设备=expected minor”的门只检查了对这个选择结果的自洽性。
Slurm全局ID、NVML可见index、物理minor不能未经验证视为同一编号空间。
先前单卡情况下0碰巧对应0，不能替代非零编号核验；旧0-only的成功不构成通用隔离证据。

raw回执的`gpu_isolation_verified`或`exact_device_namespace`不应改写：它们的窄含义是与自选minor一致，
**不是已独立核实分配合法性**。新接入回执全数不作为发行依据，错误日志保留用于追查。
目前不能断言Slurm ID1实际一定对应minor1；也不能为迁就结果而宣称minor9合法共享。

官方文档分别说明SLURM_STEP_GPUS为全局ID、不会随cgroup重编号；设备File/minor与NVML编号不是固定同一映射。
这支持撤回该假设，但不替代本节点Slurm19.05.4实际GRES配置事实。
[srun变量定义](https://slurm.schedmd.com/srun.html#OPT_SLURM_STEP_GPUS)、
[GRES设备编号说明](https://slurm.schedmd.com/gres.html#GPU_Management)。

## 已执行的处理

- 发现设备9后停止后续GPU调用，主动退出13042并释放allocation；不干预12535或他人作业。
- 新adapter在任何GPU查询/绑定之前拒绝；新OpenCL诊断main也直接拒绝。未打开8-run release。
- 未改8份配置、搜索源码、训练权重、原SIF或已有13004的负结果；没有新生成器API、critic前向或任务结果。
- 尝试在已有allocation内只读/etc/slurm/gres.conf，遭PermissionError，未绕过权限。
- 需要学长/管理员给gpu28的Slurm GPU ID→File路径/UUID映射（节点相关配置行即可），或官方支持的确定方法。
  此前问题是泛问单卡OpenCL；现在缺的事实已具体到编号映射，不能继续靠猜测完成。

## 保留与禁止重做

GPU库短检：forets-opencl-allowlist-20260911-l7imxH、r2-Ivk6pJ、r3-EQEZuE、r4-Z61pJp。
实际入口：forets-gpu-adapter-20260911-BGk4T8、forets-gpu-adapter-20260911-DosPND。
以上均在/research/d7/spc/yzyang4下；旧部署副本含错误映射，**不能执行**，保留产物，不删除或覆盖。
当前Git关闭入口不是完成映射修复；没有新的critic收益结论。下一项必须是拿到独立设备映射事实。

22:40:20 UTC独立查询：队列只剩未干预的12535 held；13037/38/39/40/41终态COMPLETED，13042终态FAILED。
对应allocation实耗4/1/21/23/9/155秒，GPU数1/1/1/1/2/2；合计377 GPU秒=0.10472222222222222 GPUh。
COMPLETED不是通过，FAILED也不删除其记录。CPU负控证实两个撤回入口在GPU查询前拒绝；错误映射实现已移除，
不能仅通过改布尔值或填哈希重启。原错误代码完整留在ef6a4d04及各独立运行目录。
