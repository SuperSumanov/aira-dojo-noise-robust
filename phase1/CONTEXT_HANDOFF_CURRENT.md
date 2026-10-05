# 当前短交接
更新：2026-10-05 18:20香港。用户17:36批准继续、一小时反馈，目标18:36；本批已闭合。先fetch并读CURRENT_DIRECTION.md、ROUTE_DECISIONS.md。

## 最新闭合：额外反馈单提案不扩大
- 根/research/d7/spc/yzyang4/structural-agent-20261005-v1；16403 COMPLETED，12启动/10有效端点，982秒×4GPU=1.0911111111111111 GPUh；10评分独立误差≤1.1102230246251565e-16，服务关闭。prepare/submit/analyze/supplement均已执行，禁止重复。源码24ceb8f5973afd9bc7268f4e79f900d5d8964e84；尚在准备push，不能声称已发布。
- 2任务×2seed×普通agent/加训练内28点调参记录/open word+char 56点HPO，每条360秒，共同训练内HPO父解。两agent均可改结构、无字符提示；内选点、全闭合才外部开发评分；仅单提案不是完整MCTS/从零E2E。
- 原完整三臂主分析2/4块：profile对ordinary为Pizza AUC−0.052260224826596424、Spooky平；对HPO分别−0.06218607988519487、−0.03124022410581795（收益方向）。另2HPO端点kernel-readiness超时，不当作方法失败，仍保留missing。门false，补齐缺失也不能救全胜条件，不补跑/补seed救门。
- 见结构缺失、未读外部成绩前增加的完整双方敏感性：profile对ordinary四对三平一负，原主分析/门不改。普通4/4保留父解；profile1/4接受新案，内部AUC+0.006976744186046435、外部−0.052260224826596424；单例不证明噪声/分布偏移。
- 18:17远端AST/实发prompt核对：Spooky两profile28行都送达、lower-is-better正确，最佳C30与父解一致；生成代码两次C0.1，内部logloss更差。7保留父解及2成功HPO预测均与16395对应产物哈希一致，不能算新独立阳性。
- plan 28c36271e38ab3f8d88508ce2235b229bf5c39bb9622096769a2d418a3492823；summary 302ec93194c8fd773f19f5609e83cc5fd3bd7bbe75f2139caa416c074d985f61；phase1/results/structural_agent_20261005共8个汇总文件，哈希、独立算术、凭据扫描通过。停止本反馈配方，不用新名称重复R2/R6/R12；保护集关闭、付费API0、底座训练0。

## 之前已闭合：结构收益存在性，不是自动方法
- 用户17:00批准小实验并要求约一小时反馈。16395在gpu27完成，8/8有效、232分类器fit/464二元fit、171秒×2GPU=0.095GPUh；无生成器/API/底座训练。
- 2任务×2内部划分×word/word+char，各28训练内调参＋1refit，总5万特征上限。全部预测封存后评分；8独立复算最大误差1.1102230246251565e-16。
- Spooky两配对logloss降低0.03860950703389854、0.03124022410581795；双方最佳C=30非边界；两个内部划分各28/28同参数组合改善。中位从0.44259890708216754降至0.40767404151230935。
- Pizza两配对AUC增加0.00466395599138969、0.009925855058598443，但事后条件区间跨0。Spooky条件区间在正侧，也不是反复开发选择校正或独立任务确认。
- 两内部划分共用同一开发集；Pizza纯词预测重复。相同调参次数不等于相同实耗时，字符臂更慢。未胜开放相同结构空间的AutoML/无约束agent；已知字符特征不是新算法或LLM发现。数值资格true不自动扩大。
- 源码95ed61276a1dee051a8e42bf21df33672c841992；plan fed6f8c812fc49db8acc459b460a10bbe962cbe10b8a2172f5dff06c7686a624；summary cb357d80931ca8c752b9be1ec358d9ac72c06803ac3a021de93b1799c22cb316。
- 结果已发布于5833d1c903c7fdb3f6999e01db887d931861a6cd；phase1/results/matched_representation_20261005。14文件凭据扫描0命中，10结果索引原字节一致；学长分支未改。后续仅交接收尾，最新head看Git。
- 远端根/research/d7/spc/yzyang4/matched-representation-20261005-v1；prepare/submit/analyze/supplement全部已执行，禁止重跑。最后17:31队列只剩旧12535 JobHeldUser，不操作它。

## 相邻证据与下一科学缺口
- R11/v2/16370仍incomplete；同想法重做未过扩大门，不补seed救结果。其continue提示限制word-TFIDF/LR，不能称无约束普通agent。原证据及撤回边界见CURRENT_DIRECTION。
- 当前局部阳性仅解决“存在改善空间”。还需agent自己提出有效结构，并在总成本相同、对手也可用相同结构时胜强参照；尚未解决自动发现、新颖性或确认收益。
- Centaur已有LLM/HPO状态共享，MLE-STAR已有组件消融和定向修改；宽概念不称首创。新提案先查ROUTE_DECISIONS，不能更名重复旧路线。

## 恢复边界
- first-960/Target-300/Target-522、D_val及官方test关闭；不恢复旧critic/HCE/多保真/Probe/K≥1，不更新agent底座。密钥仅远端，不导出原始候选/预测/标签/权重。
- SSH linux5；Python /research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。任务镜像用gpu27/gpu28的3090，不投projgpu39。
- 研究盘4TB至2027-08-30，不等于实际余量。最后学长dojo-reproduce为dfff0efb9daf1d4a63c74492f138c19c1fd8440e，内容是来源清单/筛选，不是新效果；当前执行仍固定旧b8e75052。
- 活跃本地checkout C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001。旧aira-dojo-codex-20260813有用户dirty不可重置；其phase1/memory/MEMORY.md与OPERATING_RULES.md是经验索引。
