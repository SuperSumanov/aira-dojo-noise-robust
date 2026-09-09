# ForeTS：现成8B critic真实GPU验收完成

2026-09-09 11:22 UTC独立复核。该结果解除模型推理接入阻塞，**不代表critic已有端到端收益或干净scaling成立**。

## 实际跑了什么

- 真实Slurm作业12892，projgpu39，1张RTX PRO 6000 Blackwell Server Edition，6CPU，主存申报--mem=0。
- 调度记录：香港时间19:14:24启动、19:19:31结束；allocation/step/batch均COMPLETED、退出0:0。
- 实际分配307秒，即0.08527777777777777 GPU·h；外层进程303.34536765899975秒。不是原计划20分钟全部消耗。
- 现成Qwen3-8B奖励模型、BF16、batch1、SDPA，代码版本e3a66a71c63377cfc139957081a72c5aa42ef4d6。
- 固定人工短代码16编码token、人工长代码16384编码token；seed6/7，每形状每seed一次暖机、两次测量。
- 共8条计时观测、2次实际本机HTTP评分；没有生成器API、任务代码执行、训练或保护数据读取。

模型加载104.44614779495168秒。按原入口检查，模型全部参数实际在单GPU上以BF16运行；没有CPU fallback。
本轮未重新执行验收，也未加GPU作业。独立复核仅重算已生成记录并核调度/日志，不冒充第二次独立模型复现。

## 实测

|输入|测量数|中位秒数|样本标准差（秒）|
|---|---:|---:|---:|
|16-token人工短输入|4|0.03131592302815989|0.007455975607529184|
|16384-token人工长输入|4|1.1678589479997754|0.003712193004087962|

这两组都是同一个人工输入的重复，不是8个独立任务；逐seed两次的计时分解保留在independent JSON中。
最大allocated显存18.01268482208252 GiB，最大reserved显存18.814453125 GiB。
reserved包含缓存历史，尤其短输入第二seed复用长输入后的缓存，不能把它当单条短输入净需要的显存。
8条观测均无sigmoid端点饱和；只说明这两个人工输入，不推出真实候选排序有区分力或评分正确。

日志有TensorFlow重复CUDA插件注册提示和torch_dtype弃用警告，但无traceback/OOM；最终PASS与全链退出0相符。
不因警告重投GPU，也不把正常退出解释成这些第三方警告已经被修复。

## 证据与边界

- 原始安全结果：`results/forets_bounds_20260909/gpu_acceptance_finished.json`。
- 进程结果：`results/forets_bounds_20260909/gpu_acceptance_process.json`。
- 独立复核：`results/forets_bounds_20260909/gpu_acceptance_independent.json`。
- 原始输出根：`/research/d7/spc/yzyang4/forets-8b-acceptance-20260909-yhg2vq1o`。
- 模型SHA256：bb0c6a1801cf0a753bb1f8aa1c923f9fcc7fff81fd654ae9d3a932ee280dfb74。
- finished文件SHA256：c879ea05d18a48931585c952740c43446d893eaee8a15dff621d29b47538e220。
- process文件SHA256：2af25f24e425955c1d65011f18a974fc8329b63e5f64981df1d13581311f31a4。

runtime的task_cond=true、head_frac=0.25仍是当前推理默认，不是训练元数据获证。模型是学长现成旧模型，不能称RL最佳模型。
本机评分服务通过，不等于跨进程/节点整条ForeTS搜索链或OpenRouter端点通过。

## 下一步

1. 不再重跑G0、下载模型或重复本次8B验收；保留原模型与隔离入口。
2. OpenRouter映射已经明确，但11:22 UTC两处远端.env仍没有OpenRouter形状凭据。需用户/学长直接安装远端OPENROUTER_API_KEY；不再次索要平台/模型、不搬运聊天密钥。
3. 安装后才做公开人工输入的有界端点连接检查；后续两任务×两seed×两臂的8run GPU/API矩阵仍需明确预算，不能以本次成功自动扩跑。
4. 等待期间已补只读真实结果汇总入口，10项本地人工测试及实际JsonLogger对接通过；保留8run/4pair分母和失败，不把它算额外真实e2e结果。

当前最有价值的推进仍是让现成critic在同生成器、同预算真实任务中对比随机选解；无需先重训或改top-k。
本次验证说明长上下文critic推理可运行且已有实测代价，下一步才测它是否改善最终有效提交和选中解质量。
