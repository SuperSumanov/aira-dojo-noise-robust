# seed13基础设施失败与新seed14修复矩阵

2026-09-12 01:19 UTC，覆盖此前seed14“同版本重复”门；该门没有通过，不能执行原重复计划。

13123在Leaf critic最后一个宽1池失败：真实配置skip_redundant_critic=false，裁判入口只接受宽3/4。
早先计划误称已启用跳过冗余裁判，我的预检也只验证类型/导入/部分纯函数，没验证真实配置×全部宽度的接线；对此明确更正。
此前宽4、3池的双序裁判确实跑通，但这不能替代末端小池检查，也不能作为效果结论。
01:17:52 UTC主动取消整组，保留失败/取消/未开始四槽；没有读最终分，没有修改旧包、补旧槽或将缺失赋零。

最小修复：新包两个臂均明确skip_redundant_critic=true，并使package validator要求true。
原batch_runtime在该开关为true时，会为n≤2记录full_pool_no_pruning、跳过打分、走同一common-priority选择。
保留原Borda/原slot平分，不加入人工平分分析的建议；两模型、任务、候选生成、硬件/镜像、6step/300秒/3540秒均不变。
这不是把缺失分填0，而是按完整候选池无需剪枝的既有规则不产生分数。

新seed14，两原任务×random/contextual critic共4run；gpu28单RTX3090/6CPU顺序，280分钟分配、新增最多5GPUh。
来源task tree除累计预算常量外保持5950c7d3acf1e03173ba2ea7081d8ba6593279d9；科学行为修复明确来自配置开关及对应验证。
两臂同一修复版本；不与失败seed13合并作效果平均，也不称其跨seed确认。

API全部旧行和未知责任逐行继承，不重置原100人民币/10USD。新窗口最多另3.50USD责任且累计≤10USD；
每run共同4USD/100全部API调用限制不变，Flash预留0.70、Plus2.60USD。
取消时尚未收到usage的请求继续全额预留，不能因为主动取消就按免费处理。

新提交前必须检查实际生产config中的true值、package validator与typed config、两臂归一，以及两臂×宽1/2/3/4的真实batch接线。
要求小池0裁判调用且选择等价全池随机，大池完整生成后才排名，生成/评分/执行尾部不变。
原镜像GPU已在这次作业实际执行，不重复G0。全4run终态后统一读取合法final、原始submission数值和实际选择。
