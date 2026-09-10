# 原镜像显式设备绑定：独立短诊断

2026-09-11香港。只更新隔离排障策略，不放行新8-run包。

目标：不使用自动注入全部GPU设备的 `--nv`，仅绑定当前Slurm step分配的GPU与控制设备，
另将宿主NVIDIA驱动库只读绑定。原SIF、Torch、任务数据与模型不变。
这不是放宽设备访问，而是把namespace从全部设备改成精确允许列表。

新证据：登录节点实际CE4.3允许用户绑定。原SIF `--containall` 无 `--nv` 时没有GPU设备；
同路径 `/dev/full` 显式绑定只新增该character device，major/minor与宿主一致。
设备挂载实际是rw，即使请求ro；故**不声称设备只读**。GPU本来需要rw，只有驱动库要求实际ro。
此前 `/dev/null`→不同路径被拒绝不适用于同路径绑定。
[官方绑定机制](https://docs.sylabs.io/guides/4.3/user-guide/bind_paths_and_mounts.html)

## 唯一短诊断矩阵

- 新独立gpu28 allocation：1 GPU、2 CPU、最多5分钟，单次、不自动重试。
  名义GPUh=300/3600；若计Slurm30秒KillWait，上限330/3600。不是正式e2e预算追加。
- 先只用新方式核精确device namespace、major/minor与库文件只读挂载。失败则不加载OpenCL。
- 同一allocation里两个新容器：无ICD／只读ICD；除此以外完全一致。
  只运行64×4人工输入、2轮LightGBM GPU库检查；不使用任务数据或critic，不访问API。
- ICD条件实际GPU库检查成功后，最多30秒检查新库绑定下原Torch的一次2×2 CUDA算术；
  不重做G0、模型验收或16K前向。绝无CPU fallback、安装包、重建镜像。
- 仅单卡namespace可见后才尝试GPU库；不触碰设备9或12535，不更改Slurm/宿主访问控制。
- 绑定清单、实际命令、代码SHA、作业ID、返回码与失败写入独立目录；旧结果原样保留。

这是用户既有“自主修复并继续”授权内的新机制验证；此前暂停的是失败的遮蔽及无事实的e2e重投。
CPU证据足以测试该支持机制，但不是实际GPU隔离/兼容性证明。此诊断不宣称修好、模型收益或正式发行。
历史checkpoint模板仍待学长；本诊断与该事实无关，不因此放行新8-run。

预检：便宜机制检查已通过；新脚本语法/命令与路径独立检查后才提交；无测试集/训练/采样/模型保存项；
全局队列最后22:17:28 UTC仅12535 held；实际提交前核无同名作业及旧诊断终态。采用srun immediate有界排队。
结构/机器结果和失败保留；发布前扫描文件名与完整暂存内容。效果研究仍必须跨seed同预算，不拿此人工输入充作结果。

另已排除13004客户端40,000字符裁剪归因：仅已存candidate batches，random 5段代码最长9477字符，
critic 4段最长8777字符，均未越阈值；不外推未存root/debug，也不改写该pair的负结果。
