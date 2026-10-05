# 当前短交接
更新：2026-10-06香港。用户批准三原则六小时研究，窗口01:59:42—07:59:42香港；尚未完成该窗口。10/6本轮fetch确认myfork主分支9d97916e7c19b680cef22b7bc2280588bd56b973、学长dfff0efb9daf1d4a63c74492f138c19c1fd8440e未变。按CURRENT_DIRECTION最新10/6裁决，不重开旧失败门。

## 本窗口新事实与进行中工作
- 公开GOME4210对先按固定hash每任务2对冻结80对：80解析、46有唯一共同构造器、直接数值变化0。补同样本变量/字典绑定：76可比较，12对/10任务有设置变化。多数意图明确要求，不能报12个失误；三例“保持其余设置”附近需进一步核意图与执行。未读取score/feedback/scenario值，意图文本仅数字掩码审读但仍可能含历史定性信息，不称完全盲审。
- 远端/research/d7/spc/yzyang4/collateral-sample-20261006-v1；structure SHA82bcbbfcb7f1022b246fce0703e81de4a788c67d5fc5d1b3fc0285f77fc077d5；binding-supplement-v1/summary SHAd9aca8bb78365990143f149790f47089d8add255883992b596b43845173f3dfa。来源原文留远端。
- 已有开发85修改再查：83解析、80唯一对、43对有支持的数值变化；旧开发成绩曾分析，不是新确认集。v1只读脚本漏接原生generic Exception后停，失败目录保留；v2同分母修正完成。根collateral-local-20261006-v2；summary SHA4c96405a1d58dcddbf228b801cd7516085a56a2d1eae5d9bd601c2384eb452e4。没有新模型执行。
- 冻结四格反事实：85行中24合格、42无支持的数值变化（含2解析不支持）、16需静态外部模型依赖、2原时长>150秒、1只有排除槽。固定hash每任务4对，Pizza/Tweet共8对×P/C/CP/PC=32程序；2张3090×2小时≤4GPUh，240秒/程序。P父/C子/CP子恢复父参数/PC父换子参数。剩余改动不自动等于语义想法。
- 根/research/d7/spc/yzyang4/collateral-factorial-20261006-v1：selection SHA6610706263a4ed059f28d3e52e8172af9dddd9400095fdd9172626689960c295；源码ac327c54fa6e5d92d6ad0df5ed7adfdf2b7f0695；plan SHA57dbaec816abda184f99abe0f8738e0350d0d0cb18602f5c8822eea50aeabcce。首次prepare预检因Tweet目录不同命名误判失败；validate_collateral_factorial_20261006.py以精确双路径复核32配置/8四臂PASS，冻结实验文件未变；validator SHA5da2165c3161e52f5facf044899cef407733971ea514d148db5727dd6bbeb948。
- 02:49香港单卡调度修订：gpu27只剩1张可用，16536在PENDING且0启动时撤换，原launch/plan保留。新16538用同gpu27/3090单卡串行，6CPU/worker、最长4h，总≤4GPUh；不改32配置/代码/种子/单程序时限。serial_collateral_factorial_20261006.py与scheduling-amendment.json记录。02:50现场16538 RUNNING、1启动/0完成。旧12535不操作。全批闭合/预测hash冻结后才评分；readout已写但修订后版本仍须重传。5合成对照测试PASS，无LLM/API/底座更新。
- 预结果独立性核查：8条边只有3个不同父程序AST（case0–3共用，4–6共用，7另一个）；不能将其当8个独立起点。Tweet代码内会重新seed，wrapper种子不同不自动等于独立训练重复。
- 预结果代码核查：case6/7的MAX_LEN从字符变成词/token单位；case5 BiLSTM→Transformer，LR转移未必合适。保留分母但不能将数值恢复解释为语义等价或错误修复。LLaMEA-HPO §3.3已明确优化后参数保留、结构变异，故宽概念不新。

## 最新研究复算：方向仍待验证，不把局部线索当新方法
- 新本地证据：results/research_synthesis_20261006/diagnostic.json已随ac327c54提交，尚未push。源inner-grid SHA66d79e554d0e0ea8a56d5e87d5cdf941e38c8fc20e84efbda8ff6cd3b5023064与已有导出回执一致，JS/PowerShell独立复算。
- Spooky两内部划分：保留父解C30、ngram/min_df，仅换word→word+char，内部logloss改善0.020474526937451/0.02395703644034014；相同字符表示若改C0.1，相对父解反而恶化0.45166977560521926/0.4188737298411987。相关8格训练均收敛。这是事后单任务网格诊断，非实际agent恢复/E2E/独立确认。
- 必须保留反证：实际两个profile提案是word unigram+C0.1，不是上述好字符结构；对应网格即使恢复C30，logloss0.46169566840649595/0.5120765900259493仍差于父解0.4436022186964692/0.48126249849150526。数值匹配不证明程序语义等价，未补跑实际修改。Pizza的C0.1字符格仍可优于父解，不能制定通用锁C规则。
- 候选问题：搜索是否系统性丢失已优化设置、抵消真正有用的结构变化？它与R3/R11/R12重叠，不能称全新路线；MLE-STAR/PatchFusion/Implementation Lottery/FBNetV3/Centaur均是直接近邻。下一步先找真实候选的可挽救空间及反证，固定不看结果的抽样与干预，再决定是否值得干预；不先建控制器。
- 上一聊天20条thinking×feedback＋HPO矩阵仅提案未启动。16403只有单提案；ordinary/profile中位64.41/55.38秒，名义360秒，不是完整搜索对照。这个边界不撤回旧单提案结果，也不证明放宽次数会成功。
- 队列未重新查询；下文10/5队列均最后观察。保护集仍关闭，未改旧结果、实验代码或学长分支。

## 最新闭合：额外反馈单提案不扩大
- 根/research/d7/spc/yzyang4/structural-agent-20261005-v1；16403 COMPLETED，12启动/10有效端点，982秒×4GPU=1.0911111111111111 GPUh；10评分独立误差≤1.1102230246251565e-16，服务关闭。prepare/submit/analyze/supplement均已执行，禁止重复。源码24ceb8f5973afd9bc7268f4e79f900d5d8964e84；结果已发布38e7bb7068453e505ef4ba5c6f384ee3576f6d48并独立ls-remote确认；学长分支未改。18:24:34队列仅旧12535 JobHeldUser，不操作它；18:22短暂DNS失败已恢复。
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
