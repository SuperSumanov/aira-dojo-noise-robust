# ForeTS：运行接线与自主排障进展

香港2026-09-11；远端最终CPU核验为2026-09-10 22:05:14 UTC。
目标仍是同预算下critic能否改善最终选中解的外部成绩。**没有新的效果结果，也没有新GPU作业。**

## 本轮实际完成

- 新增固定seed8/9分块运行层，接入已有真实SrunPool与critic服务；保留两块各4run，不自动重试/恢复。
- 启动期限按allocation实际开始时间计算。Linux计时器可中断阻塞调用；启动时SIGTERM也进入清理。
- 同一节点上的路径检查直接检查路径/可执行程序，取消额外占GPU、原本无超时的路径检查step。
  仅改变启动管理，不改变候选算子、任务镜像、worker预算或两臂配置。
- worker和critic共享一次最多30秒清理，不再各等一轮；只取消本allocation内、名称匹配的步骤。
  本地srun退出不等于远端资源清理成功；无法确认时记录cleanup_unconfirmed。
- 每块单独要求新鲜免费路由回执，第二块不能沿用四小时前的检查。未调用任何API。
- 新增独立收尾采集：先查allocation终态，再读最终pool记录，避免取到查询前的过期RUNNING状态。
  保留8槽位、实际失败及未开始项；不存在的block不能被自动填成NOT_STARTED。
  这里只产生元数据清单，不打开分数；随后才由已完成的新reader读最终选中节点的外部分数。

22项新增CPU测试通过。远端Python3.12.13实际导入pinned pool并核过继承接线、Linux阻塞计时、
启动中断清理和8份既有配置绑定；**未构造真实pool、未加载模型、未生成真实runtime manifest**。
新collector的Slurm字段解析还只读核对了旧13004的终态/2577秒/2GPU；不是重做实验或新增block结果。
一次远端CPU导入先因核验脚本缺LOGGING_DIR失败，补齐非凭据环境后通过；没有失败GPU作业。

新模块：`forets_block_runtime_20260911.py`、`forets_block_collect_20260911.py`。
证据：[implementation.json](results/forets_block_runtime_20260911/implementation.json)。
远端独立CPU准备根：`/research/d7/spc/yzyang4/forets-block-runtime-20260911-75kVIA`。

目前入口只提供inspect；缺失硬件/历史输入release时，在读取凭据或创建资源之前拒绝。
生产front door代码已接线，但**未发行可执行release，也未完成真实Slurm/服务生命周期验收**。
设备隔离方案若要求源码或环境变化，需明确固定新绑定，不能直接把草案readiness改成true。
预算仍为280分钟/块，两块名义18.666666666666668 GPUh、计allocation KillWait为19.0；本轮使用0 GPUh。

## 自行排障得到的具体事实

1. 权重包只有一个safetensors文件。只读47,680字节header，400项tensor、metadata仅`format=pt`，
   credential-shape命中0；没有隐藏训练参数、指令模板或训练commit。没有重下/重哈希15GB权重。
2. 调度器配置显示`task/cgroup`与`proctrack/cgroup`。gpu28登记9张RTX3090，节点Slurm版本19.05.4。
   旧检查中可打开0和9而只分配0；“设备9未纳入GRES列表或被默认允许”是排查假设，**不是已证实根因**。
3. 我尝试通过普通SSH只读计算节点配置，未执行GPU/OpenCL调用。SSH主机身份验证未通过；
   本地和登录机既有信任记录中，短名/FQDN/IP均无匹配。未关闭校验、未自动接受未知主机、未改宿主配置。
   因此仍未取得计算节点的具体GRES设备映射、AllowedDevicesFile及nvidia-container-cli可用性。

Singularity 4.3文档确认：旧`--nv`暴露设备，CUDA可见性变量只控制遵守它的CUDA程序；
`--contain --nv --nvccli`配合`NVIDIA_VISIBLE_DEVICES`可限定绑定的设备，但要求宿主安装并配置
root拥有的nvidia-container-cli，且会使用临时可写覆盖层。因此不能把它当作本集群已可用的替代。
OpenCL还需要vendor ICD；这是与设备隔离分开的两项前提。
[官方说明](https://docs.sylabs.io/guides/4.3/user-guide/gpu.html)

与本节点版本对应的Slurm 19.05.4源码，会按默认允许设备及job/step的GRES设备列表设置访问规则。
这支持向管理员核对实际设备映射/默认允许项，但不能从“9张卡”推断具体minor编号。
[对应版本源码](https://github.com/SchedMD/slurm/blob/slurm-19-05-4-1/src/plugins/task/cgroup/task_cgroup_devices.c)

## 外界仍需补充的最少事实

- gpu28上设备9的用途，以及受支持的“只暴露Slurm分配卡给OpenCL”的实际配置。
  最有用的是计算节点的GRES File映射/默认允许设备项，或管理员确认的nvccli路径和使用方式。
- checkpoint-100历史训练是否含预测指令前缀及head_frac。当前分支的模板不是历史权重的证据；
  没有记录时明确说明未知即可，不需要重传权重、重造记录或发送密钥。

这些问题先前已通过用户提出，本轮不重复索批。没有外部事实时，不重投失败遮蔽、不改Torch/镜像、
不退CPU、不重做G0；原13004负向结果保留。按实验工作规范固定预算与两臂差异，工程验证不替代效果证据。
