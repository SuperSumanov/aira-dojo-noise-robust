# 定向解决真实候选的OpenCL错误，不重复G0

> 14:53 UTC终态更新：13007/13009/13010均结束；未执行任何OpenCL调用或人工LightGBM拟合。
> 13007查询字段不兼容退出；修复后的13009发现仅分配0仍可打开真实GPU9而停止。
> 13010请求相同的只读设备遮蔽后，0和9仍可打开，门再次停止；其requested masks字段不等于遮蔽生效。
> CPU无--nv复现确认Singularity拒绝把/dev/null绑定到不同/dev路径（source/destination必须一致）。
> 不是再加重试就能消失的错误；已向用户提出学长/管理员的技术确认问题，未修改宿主、镜像或放宽门。
> 三次检查实际共0.06111111111111111 GPUh；详细证据在results/forets_opencl_20260910。
> 下面是原设计与解释边界，不是新的自动启动指令。暂不继续投GPU，也不重投13004。

13004随机臂及12977都出现过`No OpenCL device`。原SIF只读检查发现没有`/etc/OpenCL/vendors`。
这是一条具体根因线索，不足以直接宣布“驱动配置一补就好”；基础Torch CUDA可用也不能替代这项检查。

## 固定的A/B诊断

仅在13004整个首配对终态、清理完成后，使用另一个gpu28单3090分配。一次分配最长5分钟；
名义上限由`1*5/60`计为0.08333333333333333 GPUh，若计300秒清理则0.16666666666666666 GPUh。
2个容器调用、每个最多100秒；无API、真实任务数据、critic加载、底座更新或Torch安装。

|条件|镜像与GPU|唯一环境差异|
|---|---|---|
|A 原始|既有SIF、3090、原`--nv/--containall/--cleanenv/--no-home`|无额外ICD绑定|
|B 只读ICD|同A|绑定仅含`libnvidia-opencl.so.1`的vendor配置目录|

容器内先核实际可以打开的GPU设备节点是否恰好是Slurm分配的那一张；若无法确认隔离，
在任何OpenCL枚举或计算前停止，不把`CUDA_VISIBLE_DEVICES`当成OpenCL隔离证明。
通过才枚举OpenCL设备，并在只有1个GPU设备时执行64行人工数据、2轮LightGBM GPU库计算。
不会在失败时改`device_type=cpu`，不会修改真实候选；人工库检查不算真实任务成功。

若仅B能成功，得到的是ICD配置对这项库故障的定向修复证据。下一步才将相同只读绑定加入
新的、双方一致的实验环境；13004始终保持原配置，其失败/结果不改、不拼入新环境的确认数字。
若B也失败，就按具体loader/平台/设备/库错误继续诊断，不先增加critic规模或反复重投整个矩阵。

原设计的脚本`scripts/forets_opencl_readonly_ab.py`显式拒绝在13004分配内运行。
原SIF保持原地只读；尺寸/mtime检查不冒充完整内容hash验证。

依据：[Singularity官方OpenCL说明](https://docs.sylabs.io/guides/3.7/user-guide/gpu.html#opencl-applications)、
[LightGBM安装说明](https://lightgbm.readthedocs.io/en/v4.5.0/Installation-Guide.html)。
