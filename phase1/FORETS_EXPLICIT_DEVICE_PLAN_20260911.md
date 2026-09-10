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

## 实际迭代

13037于22:20:47 UTC在gpu28执行，source cb710133；两条件均只暴露/可打开分配的GPU0，
50个驱动库绑定实际只读；不再出现设备9。两条件均OSError，未进入LightGBM拟合或Torch。
随后无GPU原SIF检查明确 `libOpenCL.so.1` 不存在：此前假设镜像自带loader不成立。
将宿主现有loader与NVIDIA库一起显式只读绑定，两个条件完全相同；它本来就在站点nvliblist中，
不安装/升级任何包。第二次独立单卡至多5分钟用于完成同一A/B问题；旧目录/结果保留，不覆盖13037。
新总诊断预算仅两次各5分钟（名义0.16666666666666666 GPUh，含各30秒KillWait共0.18333333333333332）。
实际usage由sacct另计；修复loader不代表GPU调用已通过，更不是模型收益。

13038在库清单构建时以ambiguous driver library拒绝，尚未启动容器：多个OpenCL安装的同名alias冲突。
新增固定解析规则：只取ldconfig报告顺序中首个x86-64 SONAME=libOpenCL.so.1及它自己的真实文件名，
不混合其他安装的alias；在产物保留全部loader候选路径与选定路径。两个条件共用同一loader。
这不是按运行结果挑库，也不声称与原--nv的具体loader字节相同。第三次独立单卡至多5分钟完成诊断。
三次名义总上限0.25 GPUh，含各30秒KillWait为0.275 GPUh；前两次实际仅秒级，按独立sacct报告。
一次申请0GPU的节点纯元数据查询被集群CPU:GPU比例规则拒绝，无新运行/数据返回；不绕过规则。
