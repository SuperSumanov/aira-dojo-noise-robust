# G-reuse task-CI功效：异方差Monte Carlo校准

冻结于2026-09-04 22:00 UTC，在任何正式模拟读数前固定。

1. **问题**：检查0L30把不等任务大小压成`mean(1/n_task)`的非中心t近似是否偏差超过1个百分点。
2. **唯一输入**：既有公开结构回执中28个匿名任务的`local_pairs`计数；协议绑定整文件SHA-256。
3. **禁止输入**：label、prediction、accuracy、utility、任务/parent身份及first-960、Target-300、Target-522
   的任意保护内容。
4. **固定场景**：效应恒为+0.02；optimistic/reference/stress的paired discordance、任务间SD、三训练seed
   相关性及解析功效均在`g_reuse_power_mc_protocol_v1.json`中冻结。
5. **数据生成**：每次trial为28个独立Gaussian task means；三训练seed平均的方差因子为
   `(1+(S-1)rho)/S`，且每任务使用自己的真实pair数；不把任务大小压成一个平均值。
6. **判定统计量**：计算28个task means的等权样本均值、ddof=1样本SD及df27双侧95% t下界；下界严格
   大于0才计成功。
7. **重复与精度**：每场景用seed 20260905/20260906各250,000 trials、batch size 5,000；两次功效差
   不得超过0.01，每次Wilson 95%半宽不得超过0.005。
8. **解析近似校准门**：两次Monte Carlo功效均值与冻结解析值绝对差不得超过0.01；任一场景失败即降级
   0L30解析功效，不挑场景或改阈值。
9. **独立复核**：producer A/B必须逐字节一致；另一个不导入模拟器的stdlib verifier从成功次数重新计算
   功效、Wilson区间、所有门和总判定。
10. **解释边界与资源**：不模拟主协议的观测点差≥0.02、三seed同向或其他比较门，因此不是overall core
    power；GPU/API/model fit/protected read均为0，模拟仅用于设计校准，不能作为正效果。
11. **停止条件**：输入SHA/任务结构漂移、A/B不一致、测试失败、stderr非空、非有限值、独立复核失败均
    fail-closed；不得据结果修改+0.02门、场景或评测集。
