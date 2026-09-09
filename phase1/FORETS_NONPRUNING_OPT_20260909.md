# ForeTS：不需要筛选时跳过critic（默认关闭）

2026-09-09；这是精确选择语义下的可选省调用优化，不是新颖性主张，也不是模型质量实验。
0016基于source-v4；新tree为2ff5277ba17327c6c03326a018b59f704402af6b。
只部署到/research/d7/spc/yzyang4/forets-nonpruning-20260909-Wmfn3x/source-v5，未修改生产/学长分支/12892验收入口。

## 为什么这次有实际用途

当前代码用min(num_children, remaining_steps)决定候选数，不是每批恒定4个。
既有4执行步、top-2选1配置，在无debug的完整路径上会形成以下批次：

|剩余执行步|候选数|原critic调用|启用优化后调用|是否筛掉候选|
|---:|---:|---:|---:|---|
|4|4|4|4|是|
|3|3|3|3|是|
|2|2|2|0|否|
|1|1|1|0|否|

生成仍为10个、执行仍为4次；仅critic调用由10减到7。debug、生成失败、提前停止会改变这张条件表，不能外推为所有run省30%。
短pilot后半段没有筛选作用，所以4步首先适合真实接入筛查，不能当充分的搜索收益测量。

## 精确适用条件与实现

开关solver.skip_redundant_critic默认false。仅当requested policy为critic_topk_random、开关为true且count<=top_k时启用。
现有choose_slots先按分数取top-k，再把候选槽位排回原顺序，随机源身份不含policy。
当top-k包含全池时，对任意完整有限分数向量（含并列），原算法的eligible就是range(count)；
调用同一随机选择函数在相同task/step/seed上会得到逐槽位完全相同的结果，而不只是分布相同。

保留台账requested policy=critic_topk_random，另记score_bypass=full_pool_no_pruning及实际top_k；
不调用critic，不生成假分数，不把未知分数填0。候选仍从generated进入实际执行状态，未选候选保持未执行。
台账拒绝count>top_k、布尔top_k、未知bypass原因，并禁止在bypass批次发起评分；所有需真正筛选的批次仍照常评分。
这不是“critic报错后回退随机”，启用条件在任何critic请求之前、仅由结构决定，不能掩盖已发生的模型失败。

## 已验证与尚未验证

实际ForeTS batch_runtime、CandidateLedger、Journal和selector；生成器、critic返回、task执行返回为人工替身。
5项定向检查通过：默认关闭；seed6/7四批轨迹开关前后选中槽位完全一致且10→7；随机臂不变；非法bypass拒绝；无假预测。
原始回执results/forets_bounds_20260909/nonpruning_checks.json，实际远端退出0。没有真实GPU、模型/API推理或程序执行。

等价性限定于同一候选池、task/step/seed；真实运行节省的时间会改变后续prompt的剩余时间，外部API也非确定性，
因此不主张整个真实agent轨迹逐字节一致。尚未测量整轮加速、显存节省或质量收益，不能把调用减少30%写成整轮快30%。
当前计划与所有默认配置均未启用。后续若采用，必须在真实运行前给两臂相同的开关设置并记录实际source/config，
与同预算/同生成器规则一起冻结；不得在看到哪臂成绩好之后为某臂单独切换。

## 请求预算的澄清

当前run_budget的max_output_tokens是每次请求的上限，不是整run的输出token总额。
例如40次请求、每次8192输出token，条件上界为327680输出token，而非8192；这组数仍只是已有测试配置，未获真实8run预算批准。
共享请求次数仍由持久计数器限制，输入token及真实供应商账单另计；免费路由不等于计算/时间免费。
