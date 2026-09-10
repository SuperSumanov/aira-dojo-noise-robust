# ForeTS替代部署：gpu28双3090，原任务镜像不变

2026-09-10。用户明确提供gpu27/gpu28作为现有MLE-bench镜像可用节点，并要求两臂同硬件、不升级Torch、不退CPU。
本次选择gpu28；06:15 UTC其状态IDLE，gpu27为MIXED。节点状态不是执行证明。

最新：修复启动后的12977于香港14:25:24启动；06:29:38 UTC仍RUNNING。任务SIF的真实CUDA计算已通过，
critic单3090全参数CUDA-BF16及16K一次前向也已通过，未CPU卸载；首个MLE run已启动，1running/7pending、无最终结果。
原8run入口60bad030，唯一运行根为本目录的package-r2，而非首次失败的package。
正常分配时限18:55:24，不含可能的清理延迟。提交与容器实测见results/forets_3090_20260910。

06:33:39 UTC跟进：首个随机run在draft的生成接口失败，1个APIError及2个CancelledError（按attempt_id去重），
reserved attempts=3，provider实际取消与费用未知；不是3个独立APIError。第二个critic run已有4个成功响应、仍运行。
首个失败早于该批候选执行，不能当作critic优于random的证据。HTTP细因未知，不擅自换路由或重跑seed。

实测任务镜像torch2.5.1+cu124/CUDA12.4，3090能力8.6，25秒步骤完成。critic仍为宿主torch2.11.0+cu128，
加载/绑定164.63458847487345秒，16K一次前向7.913172740023583秒，peak reserved18.80078125GiB；
不是重复计时基准，也不代表真实candidate排序有效。一次加载完成后同服务直接供搜索。

## 固定范围与预算

- 原leaf-classification/spaceship-titanic × seed6/7 × random/critic，8run、4配对，顺序不变。
- 同一gpu28分配：2×RTX3090、12CPU、270分钟；单卡critic、单卡串行任务执行，随机臂闲置卡仍计预算。
- 名义9.0 GPUh；加已观测300秒KillWait为9.166666666666666 GPUh。检查与启动全部计入，不追加GPU验收作业。
- 原SIF `superimage.root.2026-07-macos-v1.sif`、source-v5 tree2ff5277ba17327c6c03326a018b59f704402af6b不变。
- 原8B checkpoint、BF16、16K上下文、同免费Nemotron及320请求上限不变；不再做外部端点预检，不训练模型。
- 新独立根 `/research/d7/spc/yzyang4/forets-e2e-3090-20260910-j6zb6d6i/package`；12933原包只作取消历史保留。

## 具体新增检查，不重做PRO6000验收

1. 在分配内用实际任务Singularity命令构造器与原SIF做小型CUDA矩阵乘法及反向，核结果有限、单3090；
   无task数据bind、无生成器、不修改镜像。最长180秒计算等待，Slurm step4分钟，失败不继续加载模型/执行任务。
2. critic只加载一次，之后一次人工16K前向；核全部参数CUDA BF16且eval，不允许auto device_map卸载到CPU后继续。
   通过后同一服务直接供实际搜索；不是新的计时基准、模型准确率或多seed验收。
3. 成功后运行原8run；总分配仍270分钟，剩余时间不足则保留未开始run。失败不重投、不换GPU/镜像/模型。

## 已完成的低成本预检

四项本地检查通过：允许的分配、错误/旧节点拒绝、batch/缺GPU拒绝、容器计算代码语法。
远端脚本语法通过；实际生成8个RunConfig并以真实worker类型往返读取；新旧配置除机械路径外完全相同，source tree相同。
gpu28的sbatch --test-only通过，预计香港14:19:46可开始；返回的12973只是预检编号，不是提交。

原项目预检逐项应用：实际配置配对已核；变更分支先CPU检查；无训练/过采样/新划分，因此训练去重与checkpoint保存不适用；
逐任务/seed、完整失败覆盖、原RNG规则和未触碰保护集不变；发布扫描完整staged内容；退出码直接读取；
270分钟含检查/加载/最多8个30分钟worker，启动时剩余时间门保留；两任务四对仍只是探索，不能统计确认。
不为旧评估分层规则另改本轮矩阵，也不重跑旧G0来满足不适用的训练检查。

截至本准备记录，尚未实际执行3090上的容器/critic；是否通过以运行产物为准，不能用用户经验或CPU检查替代。
两臂将共同从PRO6000计划迁至3090，故不能把旧PRO6000推理时延当新部署实测成本。

## 实际首次替代提交及启动修复

06:22:05 UTC提交12974，入口commit43211ace978da1596723a2c67bbf8f5945f0a08c。
gpu28立即分配，sacct显示14:22:06开始并结束，FAILED 1:0、Elapsed0；无campaign.started、无容器/critic产物，两份Slurm日志为空。
这不是容器GPU检查失败；实际代码尚未到达该检查。失败记录和原入口保留，不是8run结果。

只读源码发现env_setup追加LD_LIBRARY_PATH但未提供默认值；compute batch可能不继承该变量。
在CPU子进程移除该变量、保持bash -u时，原初始化返回127且无输出；先给空值默认后返回0并到达完成标记。
原12974未保存该变量，且rc1不等于此次127，因此这是已复现的启动缺陷/强嫌疑，不冒充原作业完整根因捕获。
修复仅补默认空LD_LIBRARY_PATH及两条不含环境值的阶段日志，不改环境脚本、Torch、镜像或搜索设置。
修后需新包/新提交；原12974终态，无模型/API/任务执行，调度按秒记录0，不将其精度解释为物理零开销。
