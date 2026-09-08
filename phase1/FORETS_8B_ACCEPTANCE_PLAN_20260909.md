# ForeTS 8B：待批准的一次 GPU 接入验收

状态：仅准备入口，**未提交、未加载真实模型、未做8B前向**。API对应关系继续等学长，不重复索要。
本项不需要生成器API；但这是独立GPU预算，不用较早G0批准或“9GPUh条件规划”冒充批准。

## 唯一问题与范围

已收到的现成critic，在我方单卡环境中能否严格离线加载、处理完整16K输入，并通过本机评分服务返回有限值？
它不是准确率、clean scaling、跨seed搜索收益或论文正结果的实验，也不选择/重训checkpoint。
使用两段固定人工代码（不执行）：短print和重复赋值构成的长输入，后者必须在实际encoder后恰为16384 tokens。

## 一次矩阵和资源边界

| 项 | 待批准设置 |
|---|---|
| 作业/卡 | 1 allocation，projgpu39，1 GPU；运行时要求至少80GiB显存，否则退出 |
| CPU/主存 | 6核、80GiB主存；不写新checkpoint，不下载权重 |
| 时间 | allocation20分钟；step19分钟；外层进程1050秒，TERM等待及最终wait各5秒；0自动重试 |
| GPU小时 | 名义0.3333333333333333；另计已观测KillWait300秒为0.4166666666666667 |
| 模型 | Qwen3-8B_reward_seed1/checkpoint-100，现成探索critic；不声称RL胜者或最优checkpoint |
| 上下文/批量 | 16384、batch1、BF16、仅cuda:0，无CPU fallback |
| 输入/seed | 固定人工short/16K × seed6/7；每形状每seed单独warmup，随后2次测量 |
| 服务 | 同一个已加载模型，本机HTTP短/长各1请求，无生成器API |
| 输出 | 加载/前向/HTTP成功标记、显存峰值、耗时中位数和样本标准差、分数饱和标记；不发布人工分值 |

集群只读配置为KillWait300秒、OverTimeLimit0，time按分钟取整；不可中断IO、节点故障不由上述数字保证结束。
官方说明：[Slurm srun 时间参数](https://slurm.schedmd.com/srun.html)。提交前复核集群配置与实际资源，不自动扩大卡数/时限。
两个seed这里只是重复性/计时检查，不是独立任务样本，不能据此报模型效果置信区间。

## 固定输入与入口

- 入口：`phase1/forets_8b_acceptance.py`，默认不执行；`--describe`只用标准库输出方案。
- 待批准批脚本：`phase1/scripts/prepare_forets_8b_acceptance_20260909.sbatch`，只准备不提交。
  应从新输出父目录调用并保留Slurm日志；FORETS_ACCEPTANCE_APPROVED开关不是预算授权。
- GPU Python固定`/research/d7/spc/yzyang4/venvs/exp/bin/python`；只读包元数据确认torch2.11.0+cu128、
  transformers4.57.1、accelerate1.11.0、safetensors0.5.3；入口强制核对，未加载这些包或申请GPU来查询版本。
- 模型：`/research/d7/spc/yzyang4/forets-critic-incoming-20260908-3lcjjcwq/unpacked/Qwen3-8B_reward_seed1/checkpoint-100`。
- 本地base config/tokenizer：同一incoming根下`base-metadata`；固定revision49e3418fbbbca6ecbdf9608b4d22e5a407081db4。
- 模型SHA256：bb0c6a1801cf0a753bb1f8aa1c923f9fcc7fff81fd654ae9d3a932ee280dfb74；只在真正验收时检查文件身份，不提前重复读取15GB。
- 固定loader/server在tree059328196ca359965732308eebf7e57eb9c9ecd8的`src/mle_critic/src/evaluation/`，
  blob分别14687d0596d529e6235ccddce08c671227a81feb、fca0f2e6d6bd6bc6e11cf32876f67f5dceacea7f。
  可用已部署critic-offline-v1中的相同两个文件，执行时必须核对blob；不再下载底座权重。
- 入口的`--execute-approved-gpu`只是防误触开关，不是授权凭据。必须在预算获批、有确切Slurm限时及新输出目录后使用。
  输出目录排他创建；缺Slurm/节点不符/多GPU/身份变化/新增rm_meta sidecar均停止，不自动改配置。
- 本次仅对新入口做无GPU的解析、方案核算和未授权路径拒绝检查，不重跑旧tiny loader或G0。

## 验收标准与后续判据

严格加载、全部参数单卡BF16、eval模式、长输入真正16384、每次输出有限、本机HTTP成功，才称“8B接入通过”。
显存或时限不够必须记录失败，不自动缩短上下文后仍称16K通过；饱和标记仅提示可能的排序精度问题，不预言现有模型有此缺陷。
task_cond/head_frac仍按现有server默认运行（true/0.25），不是训练配置来源重新获证；该限定写入实际回执。
任何真实模型效果仍需另行冻结生成器路由、费用上限和两臂e2e矩阵。

## 与现行预检清单的对应

记录实际source/blob、模型/配置身份、Slurm分配、GPU名称/容量与依赖版本；从产物确认16K和单卡，计时排除形状warmup。
只读人工输入，不涉及训练、测试配平、语料扩容或checkpoint选择，相关去重/功效条款不适用而非“已通过”。
无底座更新、无模型保存、无保护集、无API key/env导出；发布前扫描。shell外层必须单独保存退出码，超时不记成成功。
远端断线后先查原作业和输出，不重投。该方案不能替代实际GPU预检、执行回执或批准。
