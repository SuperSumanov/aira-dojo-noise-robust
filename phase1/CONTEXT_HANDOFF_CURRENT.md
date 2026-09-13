# 当前短交接 — 2026-09-13，T1准备中

方向入口CURRENT_DIRECTION 0L198；当前目标是重要、独特、充分证明的同预算e2e主张，不是增加资产/审计数量。新问题及完整方案FORETS_CLAIM_PROGRAM_20260913.md。

## 正在做

T1三臂修复迁移：同一个旧失败状态，无外部经验/相关历史修复/随机历史修复；两任务各4个run，共24份新程序，每例一次生成+300秒执行。
只用旧32闭合开发run、157保存节点、11历史成功转换。全部9个经验来源run排除，目标与经验父/子AST相同也排除。
10:59 UTC选择完成：Leaf候选5run、Space7run，固定SHA排序各取4；不重选、不打开34–41/保护cohort。
根 /research/d7/spc/yzyang4/forets-repair-transfer-20260913-d151en61。
selection-public SHA48605345d740b81f50b387cae3368269a6d2449ff8c665e024c2aec7a1ba94ca；私有inputs SHA792a7a46a54c6196743ec2d569d4d4d5bb7dfd2d0d594327fa6916d61d77384c。
新worker/run/readout/test均在phase1；run_repair_transfer_20260913.py有prepare/activate/generate/gpu_prepare/submit/execute。
最后状态：8单元测试通过，尚未activate/API/GPU。10:56队列只有旧held12535，无活跃实验。不能根据计划写成在跑。
远端上传阶段 /research/d7/spc/yzyang4/forets-action-stage-20260913-egtJPLRg；等scp完成再运行。后续准备、账移交、调用和提交必须一次性，不盲重试已有claim。

## 预算与冻结读出

原100人民币/保守10USD累计帽。闭合前驱 /research/d7/spc/yzyang4/forets-wallclock-20260912-103zf3nb。
最后1755calls/held6302127386nUSD/settled4902127386nUSD/2旧未知；auth0b4e20837991c8ec3f9cb16116170c62b1e0897e732c9b1e62ffb1eaa8db5b4c。
T1新增最多24次×0.10USD预留=2.40USD；先生成后GPU，两份2h单卡分配，最多4GPUh。保留所有旧账和旧未知，移交封旧scope，不能重置。
固定Flash qwen/qwen3-coder-flash、OpenRouter Alibaba only/nofallback，8192输出，温度0；凭据仅远端aira-dojo/.env的OPENROUTER_API_KEY，不再索要或回显。
主要是有效执行配对差；错误/格式/超时算未修复，基础设施故障未知且不补跑。两block终态后一次完整读出；成功率非学习完整性或e2e质量证明。
相关经验对两对照均净改善、两任务不净退步、无技术未知才准备下一步；小样本门不是显著性保证。

## 必须保留的旧结论

34–37逐动作交付2胜6平，只修正我方bounded交付基线，不是critic/算法；未来Space41已出现action外部分数低于iteration，禁止泛称不退化。
38/39宽度二比四：1胜3负，API便宜但非质量保持。40/41三条错误消息：7技术合格、3可比对1胜2平，1不可比；不扩大这个配方。
32/33critic四对零胜一平三负；13227补齐16首候选只有1有效/14失败/1未知，critic选中了唯一有效解但未兑现e2e。
CV错位仅一个开发病例；157节点中52正常有效提交仅1缺分，不能包装成普遍方法。G0/8B验收12892、CV13232、上述6任务13233/34/39/40/42/43都已完成，不重跑。
原任务镜像不改，MLE只gpu27/gpu28 RTX3090，不用projgpu39、不升级Torch、不退CPU。旧kernel恢复补丁未部署，不恢复失修pool。

## 新颖性、语料、交付

错误记忆、可靠性/多样性、经验critic、门控再生成、类型条件修复已分别被ACL Findings memory/HASTE/CEB/MERIT/ReASearch覆盖。T1是强基线必要条件，不是新方法声明。
历史11转换根 /research/d7/spc/yzyang4/forets-repair-memory-inventory-20260913-vcg12_1y；只观察历史成功、非通用因果修复。私有码不复制本地/Git。
学长Drive0911已隔离 /research/d7/spc/yzyang4/senior-quarantine-0911-20260913，4配置不等于4验证run，不重下/不读未知归属outcomes。
学长branch最后be9335348b569086ef9b0af36a15b13e61fec45c，10:50fetch未见更新。qwen3.8-27b仅节点localhost服务，镜像/权重我方无读权限，不借用allocation/绕过。
first960/Target300/Target522仍封闭；不恢复HCE/多保真/Probe/score-channel/K≥1，不微调agent底座。
只push myfork HEAD:phase1-value-critic；不动学长分支/不强推/不新branch。此前公开99ef9bd53afd5a664193b1959ce9f4b136b68181。
SSH linux5；Python /research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf不可遗漏。
研究盘到期2026-09-29延期未知。本地无关untracked的codex_tmp/output/tmp/旧release保留。轻量交接，不制造无变化进展。
