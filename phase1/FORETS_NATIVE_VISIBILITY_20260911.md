# ForeTS：原生 CUDA 选卡与真实 Jupyter 接入已通过

2026-09-11香港；最后队列与镜像元数据核验：07:58:51 UTC。

## 结论

**gpu28 原镜像的两步真实 Jupyter 接入通过**：13076两个单卡步骤分别使用原生CUDA选中的物理卡0、1，
每步都完成 Torch CUDA 算术与 LightGBM OpenCL GPU 拟合。没有再把Slurm列表编号当作NVML下标选到设备9。
这是当前节点/镜像/入口的实测修复，不是全节点隔离保证，也不是critic正收益。

学长的澄清是正确的：STEP_ID只是步骤身份，没必要等于GPU编号；原sandbox/Jupyter不依赖这种对应。
我方13042问题来自新增adapter把STEP_GPUS误作NVML枚举下标，不是学长原代码的问题。
不再索要不可读的gres.conf，不修失修的pool恢复逻辑。新控制器只接受fresh pending、零attempt任务。

## 修复与真实证据

1. 在Slurm单卡step内继承原生CUDA_VISIBLE_DEVICES，CUDA Driver API返回实际逻辑卡0的UUID与PCI地址。
2. 用同UUID的只读`/proc/driver/nvidia/gpus/*/information`解析物理minor；不做Slurm编号到NVML下标转换。
3. 原SIF只绑定这张卡及驱动控制设备，驱动库/ICD只读绑定；CUDA与OpenCL看到同一张原生选中的GPU。
   保留原镜像、Torch、Jupyter任务payload和workspace，不升级Torch、不退CPU。
4. 真实`SingularityJupyterServer`内验证，而不是宿主venv成功替代任务容器。

| 13076步骤 | 原生CUDA实选物理minor | 容器可访问GPU | CUDA算术 | OpenCL GPU拟合 |
| --- | --- | --- | --- | --- |
| 0 | 0 | 仅0 | 正确 | 完成 |
| 1 | 1 | 仅1 | 正确 | 完成 |

两步各见一张RTX3090、一个OpenCL GPU设备；Torch **2.5.1+cu124**、LightGBM **4.6.0**。
各有独立UUID/PCI与设备节点证据；原生选卡发生在绑定之前。GPU9未纳入本次容器设备集合。
独立读出核对完整字段，不以job COMPLETED或kernel_ok单独判定通过；5份回执本地/远端SHA一致。
原SIF大小19,717,783,552、mtime_ns=1784638286000000000与既有记录相同；本轮未重新哈希大镜像。

执行代码commit：`4a7fae18e8dcbd256ccbae13e37c86264fc2d314`。
任务源码tree：`3aae90ae26b5ae7b65e6efed14fb49f2907c9c42`。
新adapter SHA256：`30feeb303352530077d97f1297ba84658295e04ba226654136436eb3c0005383`。
远端根：`/research/d7/spc/yzyang4/forets-native-gpu-adapter-20260911-y8jOwZ`。
回执：[步骤0](results/forets_native_visibility_20260911/13076-step-0.json)、
[步骤1](results/forets_native_visibility_20260911/13076-step-1.json)、
[独立复核摘要](results/forets_native_visibility_20260911/verification.json)。

## 失败与诊断边界

- 13073：metadata观察器首个GPU步骤未在25秒就绪期限内交回观察，控制器失败；不据此判断GPU隔离失效。
  旧控制器取消时未保留完整stderr，根因未证实；原失败回执保留。
- 13074：延长就绪期限、保留错误输出，并采用生产相同6CPU/step后metadata完成。
  零卡与两单卡步骤均打印`devices.list = a *:* rwm`；这个输出本身不能判断允许/拒绝边界。
  Linux cgroup-v1默认allow模式可能不在该输出列出拒绝例外；不能声称现场无限访问。
  [Linux实现说明](https://github.com/torvalds/linux/blob/v4.18/security/device_cgroup.c)
- 13075：两并行步骤原生CUDA各见一张不同卡，对应minor0/1；仅身份查询，没有脚本显式创建CUDA上下文或算术。
- 13076：上述实际Jupyter/人工GPU库测试通过；两步最终退出码均0，分配已释放。

Slurm allocation elapsed分别为30、64、4、44秒，均分配2GPU；合计 **284 GPU·秒 / 0.07888888888888888 GPU·h**。
只按allocation计一次，不重复加extern/step；包含失败13073。没有API、critic模型调用或真实MLE任务运行。
最近队列仅12535 JobHeldUser，未操作它。旧13041/13042仍不合格，不恢复其成功声明或执行旧副本。

## 对主线的影响

- 解除“必须等待管理员GPU映射配置”的阻塞，限定范围的真实Jupyter GPU接入已完成，不重复G0。
- 新adapter只开放独立integration根；8-run生产入口仍未发行，不能靠改readiness布尔值直接启动。
- 后续需把此已测实现固定接入新控制器、补齐历史输入模板的已知/未知裁决及新鲜路由，然后进入同预算对照。
  不再把已完成的控制器/配置准备写成没做，也不擅自恢复旧任务。
- 首对13004仍为random logloss0.66022、critic2.5208；一个探索seed，既非收益也非普遍无效结论。
  当前没有新增critic收益或干净scaling结果；保护集未打开，两臂公平契约未改变。
