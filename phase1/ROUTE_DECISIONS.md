# 路线裁决表：先排除重复，再提出新机制

更新：2026-10-15香港。当前状态见CURRENT_DIRECTION；本表是机制索引，不是运行授权。
压缩前全文：Git 96e129c8b67bf8e0918abd5f4e69fe4e5ecc3f13:phase1/ROUTE_DECISIONS.md；旧实验证据/近邻细节不删除。
“停止当前配方”不等于“所有变体不可能”。读原始证据后才解释历史数字，不汇总异质批次为总体胜率。

## 本次必须纠正的重复推荐

10/15新切口仅“固定GPU归属造成可避免等待→强共享FIFO参照能否改善同预算终分”，不是新调度算法。闭合18412/18269的10池均有局部排队+他卡空闲，262已知请求/5取消缺时长；24固定配对×10池及0/5/15/30秒开销的280格独立回放复核。开销可抹去优势，反馈更快不等于终分提高；不做GPU利用率→共置/提速推断。Scepsy https://arxiv.org/html/2604.15186v1 已做TP/replica/GPU分配；MARS https://arxiv.org/html/2604.26963v1 做生成/工具双压力；Libra https://arxiv.org/html/2606.03077v3 有反馈routing/资源重分；https://arxiv.org/html/2610.04578v1 更覆盖动作改变后续GPU负载。用户批准的新32条只作强基线资格；若未过原终分门，不加语义调度补救。未提交现场以短交接为准。
10/15 18412 metric-step30独立48条闭合：真实首输入48同配、77评分重算、6池结构及独立统计通过；去噪两反序重复的池best均不胜旧fast/旧medium，median也均差于旧medium，Aerial一优一退，原质量门false。停止扩大本metric部署配方，不以更多历史、改阈值/seed/换日更点救结论；score/metric不同训练数据仍不能解释为reward因果。只有部署无稳定增益的局部结论，不是所有学习无效；新机制必须有额外证据而非重命名，证据metric_deployment_18412_closed。

10/14晚：学长确认score与metric各自采集训练；HK22:51 metric step30已新可见，未下载。新产物可另问固定历史下部署收益，但两线对比不是固定数据reward消融，同名step不证明同祖先/成本；旧score的18269结果不能转移到metric。8项合成源码检查限定了仿射不变的适用范围：缺失地板/绝对spread门/可选clip可破坏它；不是实际训练故障或新方法。先内容身份和新批预算，不自动试遍日更点；证据lineage_intake_20261014.safe.json、reward_contract_20261014.safe.json。

10/14 18269完成32/32真实输入配平的新旧medium反序两池确认；去噪两重复best与median均新权重更差，Aerial一正一负，原门false。停止扩此step30部署配方，不用训练信用猜想救结论；两旧开发任务/单服务不证明policy训练普遍无效。Drive对应day0包的转换报告只证明27B/65536准备设置，实际训练配置未取得。证据weight_confirmation_18269_closed及drive_training_config_20261014.safe.json；不把旧队列/准备当当前工作。

10/14：长Debug链多导出训练条目已在10/5的sft-target-semantics.safe.json验证（纯合成、不是实际损失/梯度），不当新发现重跑。真实step30采样/损失配置未取得，更多条目与广播终分不自动是错误；一律按链长降权没有效果依据。新增闭合18253的101返回/46有效来源核对中，8任务×臂格有4格最佳终步为Debug；这是关联，不是删Debug反事实，不能重开17740混合档位。来源数据与独立安全导出复核见sandbox_scheduling/role_origin_20261014_cpu及verify_closed_role_origin_20261014.cjs。

10/13新增：学长建议xhigh与每日policy自举，不是我方新方法确认或训练授权。旧17740混合配方停扩；新问题只保留“固定archive后，日更新权重是否改善同预算质量—推理成本关系”。版本×effort只是识别设计，不包装成新算法；不把参数学习、历史起点积累、延长预算合成一个未经分解的正结论。

聊天提案“学习修改在何种条件有用 / 可迁移修改经验 / 受控验证后形成经验库”不能列作全新优先突破。
它重叠下面R1/R3/R4/R6/R8及10月2日既有复盘。尚未跑完“完整适用性验证库”不构成独特性或优先级证据。
上一条推荐忽略已有结果与查重，是记忆检索失误；撤回该推荐，但不虚构该完整变体已经做过或被否定。

## 已试的相邻路线与边界

| ID / 同义机制 | 已做及主要结果 | 当前裁决 / 证据 |
|---|---|---|
| R1 历史修复检索、经验迁移、成功补丁示例 | 2026-09-13：8个不同旧开发run×无经验/相关经验/随机经验=24干预；20已知未成功、4未知；相关对各对照6已知配对全平 | 停当前单步配方，不称0/24全失败或记忆普遍无效。[原报告](FORETS_REPAIR_TRANSFER_RESULTS_20260913.md) |
| R2 任务内事实、定向证据、analyzer反馈 | 2026-10-01至02：部分普通改进和人工规则有局部收益；额外事实/证据没有稳定胜强参照 | 人工正确答案是可实现性控制，不是自动发现。[复盘](reports/研究复盘与方向重定义_20261002.md) |
| R3 局部编辑、拆分改动、回收有效片段 | 已检查85修改及依赖；10/2追加26条中18重复旧覆盖，25可解析、24多块、304语法中间版本 | 可编译不等于可执行/有收益；不把新一轮AST拆分当新路线。历史0L410、0L401；近邻PatchFusion/MLE-STAR |
| R4 执行状态复用、缓存×反馈 | 15272：Pizza 2seed×4条件=8轨迹，全部保留起点；6有效新解0改善，5更低、1相同；固定配对差/交互均0 | 有缓存操作价值，无新增终分收益；反馈实际被使用仍可无增益。[结果目录](results/state_feedback_pizza_20261002)、历史0L411 |
| R5 错误/正确样例、残差驱动修改 | 15282：2任务×2seed×uniform/contrast=8条，没有改善候选，未过门 | 不用“错误例子更具体”重新开同配方。[结果目录](results/public_examples_20261003)、历史0L412 |
| R6 自动修改方案、具体规格、主动取证 | 15301中人工具体要求在Spooky恢复已知CV成员选择收益；事实B跨任务门false。15389自动方案B四条均无新候选；另有V4/V6止于来源失败 | 保留局部正控；来源失败的批次效果未知，不合并为方法零收益。[信息结果](results/opportunity_information_20261003)、历史0L415–419 |
| R7 可执行诊断、前提反证、校正报告 | 15706：18条未过自动B扩大门，有固定审计局部信号。15829：4范围干预证实诊断对象混杂。15950：12条，校正C未稳定胜原报告B，两任务C−B中位不正 | 测量纠正不自动成为E2E机制；不再用“验证诊断”重命名。[结果](results/diagnostic_information_20261004/closed)、历史0L421–423 |
| R8 预测父子修改收益、edit-gain图、跨任务修改复用 | 2026-08-21查重已明确M-DESIGN直接覆盖修改增益图、预测修改收益及迁移的宽主张 | 不能再把上述概念称首创；旧68维结果不可重调追正。历史0CU |
| R9 现成LoRA全角色搜索 / 角色分工 | 16307：8条1有效、0完整质量配对、0Improve；16309同22观察88判断，小范围误否决改善 | 前者无收益证据，后者非端到端，不据角色阳性自动扩跑。CURRENT_DIRECTION最新证据 |
| R10 旧代码critic/scaling、覆盖与修复次序 | 存探索性任务内信号、同池局部好例及反例；干净scaling和稳定完整搜索收益未确认 | 不能把学长结果归为我方，不能因新模型到位自动恢复。10/2复盘及9/20报告 |
| R11 想法与实现分离、同想法独立实现、保留想法重做代码 | 16357：4新起点0有效，12续跑0启动，效果未知。修复v2/16370：2固定人工起点＋16四臂续跑、267评分复算；4硬截止缺finished，主分析1/4完整。完整Pizza块重做输续改/HPO；Spooky完整双方两seed重做−续改中位−0.0019279244953428754 | 停本重做配方、不补seed救门；主分析incomplete不改。真实开发改善来自普通续改/HPO，不是重做优势或独立确认。宽概念已被Implementation Lottery/MLE-Ideator覆盖。[旧v1](results/implementation_reset_20261005/summary.json)、[v2](results/implementation_reset_v2_20261005/summary.json) |
| R12 调参后结构改善空间与反馈引导单提案 | 16395：已知word+char有限网格阳性，Spooky两划分同参28/28改善，非新方法。新16403：12启动10有效端点，普通/附28点调参反馈/open word+char HPO；profile对ordinary四完整双方三平一负，对HPO两个完整块均负；原完整三臂仅2/4块，2HPO端点kernel-readiness超时。Spooky实际提示方向正确、最佳C30，新提案两次C0.1更差 | 停额外反馈单提案配方，不补seed救门；不否定所有结构发现。HPO两有效输出与16395相同，不称新独立正结果；保留已知结构参照。R2/R6/Centaur附近，不能更名加反馈。[空间](results/matched_representation_20261005/summary.json)、[新对照](results/structural_agent_20261005/summary.json)、[完整双方/机制](results/structural_agent_20261005/supplement-v1.json) |
| R13 自然修改中参数继承、恢复父数值、四格交互 | 16538：2任务8边×4版本=32执行，26有效、5完整四格、3不同父程序。仅1严格挽救且为已知日期特征例，CP−P条件区间跨0；其他无新挽救，1例恢复反而更差。Tweet3对C/CP同样代码错误。参数效应随结构变化的单例符号翻转存在但Pizza交互区间跨0 | 停简单恢复数值配方，不补边/seed救结果；不否定所有编辑因果分析。LLaMEA-HPO/GEVO/MLE-STAR直接近邻；不能把合成网格或旧例包装成自动方法。[四格](results/collateral_factorial_20261006/summary.json)、[独立审计](results/collateral_factorial_20261006/audit.json)、[条件区间](results/collateral_factorial_20261006/bootstrap.json) |

## R14（2026-10-06起）：MLE沙箱资源调度，尚非已成立方法

- 10/14等待期复盘：已闭合104条只逐批描述，不混成总体胜率；更多改善/更高第二名不能替代原pool-best门，删除best也不是共享archive反事实。学长8d39164c的to_grpo组内中心化使“同组终分减同一父分”在无clip/失败floor同移时等价，不能包装为新训练目标；debug链逐call同advantage的行数差是待核实际sampler/loss与生产manifest的问题，不是已确认偏差或训练授权。查重再核CostAda v4§4.3/B.3已只给global-best改善分配信用；When Agents Slow Down原摘要及作者代码README已有best-so-far/token与长短session分配（全文仍未核），不以重启/曲线/尾部目标更名为创新。
- 10/14：共同真实public预览/首请求前置拒绝通过新32配置及16配对组CPU门，用户批准两反序池确认≤15GPUh后唯一提交18269（现场见短交接），不补跑。旧首提案不支持“新权重只因较慢才输去噪”的单一解释（新旧medium各2/4首有效，中位新更差）；不是新质量结论或训练普遍无效证明。此次只识别同历史的既有adapter部署增量，不把修控制漏洞/更多改善次数称创新；无fast强参照，未知训练成本不称整循环回本。
- 10/14：18253四格32/32闭合，原质量门false；新medium Aerial开发AUC1.0是局部信号，去噪新fast/new-medium均未胜同档旧模型，不能称整体部署收益，更不是日更训练因果。实际提示另有随机harness回执文件名和episode25预览超时差异；mock preview前检不等于生产输入一致，不删样本/归一化救门/复用余款重跑。证据weight_effort_18253_closed及CURRENT_DIRECTION；先冻结真实public-data preview才谈未来独立对照，不把控制修复称方法创新。

- 18161于10/14 HK00:17闭合24/24，28评分重算/独立统计通过，质量门false、结构/实际档位true，成本10.335GPUh。去噪池最佳fast/medium/xhigh RMSE=0.01968566134361319/0.016646375501812607/0.04551226514614451，xhigh两任务无新有效评分；4/4返回code均被32768长度上限截断。这是固定预算配方失败，不是自然完成长推理的能力比较，不能事后延上限救门。medium去噪4/4搜索改善、fast1/4只是单共享池探索线索；不按它训练任务router或称少想更好。保留fast、medium与CoT-retry参照；下一识别重点是同archive/历史下日期固定旧新权重的部署增量，再谈含训练与采集的总成本回本。Ares已覆盖历史条件化effort，当前仅问题差别不能替代新颖性/收益证据。原件long_effort_v1_closed；不自动开下一GPU批。
- 17740闭合48/48，原完整胜出门false：混合两重复均胜medium（去噪RMSE相对降低7.618648981362969%/14.147136053465204%，Aerial近天花板无退步），却未重复胜fast（去噪有向差-0.003532255986983028/+0.0018978453603764722）。因此停本角色混合配方自动扩跑；已知策略资格的局部阳性不改写为创新确认。固定fast和CoT-retry式混合均应进入后续强参照，不能只胜medium就声称新控制器有效；也不能事后按这两任务选臂称事前策略。静态混合对照、token上限解释、独立任务和缓存时序边界仍未解决，不为追正结果重开本批。证据feedback_effort_v2_closed，含失败12.815GPUh。
- 10/12揭读前补核[Where does output diversity collapse in post-training? §4.2–4.3](https://arxiv.org/html/2604.16027v1)：Olmo3中关CoT未恢复答案多样性，且需区分错误花样与正确解多样性；其抑制CoT属分布外干预，不能直接推Qwen或MLE。故不预设“少想→探索更广”，也不从生成数/源码差异推出有用探索；本轮仍只按真实外部质量与全成本判断，不新增训练或多样性配方。
- 10/12补核[LASER §4–5](https://arxiv.org/html/2606.31580v1)与[Queueing-Aware Optimization of Reasoning Tokens](https://arxiv.org/html/2601.10274v1)：前者已有负载感知推理预算/退出，服务指标采用实测单请求成本后的离散事件模拟；后者在Poisson异质请求/MG1下联合精度与等待优化固定类型预算。因此“拥塞时少想、空闲时多想”本身不是创新。MLE生成—执行—修复的内生工作量或最终best目标只是可检验的问题差别，不能据此宣布原创；若两种模式无质量—执行需求差异，不开发新的队列effort控制器。
- 同日补核[InfraMind §3–5](https://arxiv.org/html/2606.11440v1)：已有实时queue/KV/latency条件化模型与推理深度、剩余预算/EDF、多agent拓扑的联合控制。不能将“资源状态决定推理投入”称空白；本文主要异质模型服务和推理基准，我方原程序执行反馈是待检验差别，不是创新充分条件。不因其训练controller而借机更新agent底座。
- 17740揭读前补充解释边界：反馈模式若胜两常数模式，也未分离“快慢混用”与“按反馈选择”的价值。进一步的方法主张还须胜在独立开发批固定比例、但不看角色/反馈/资源状态的混合参照；不能拿两个纯模式端点替代这个检验。真实执行压力、最终best而非返回数、跨池重复须同时核；事后最佳混合或反事实回放不冒充线上强基线。当前48条矩阵和质量门不变，不因此自动扩跑。
- 10/12又核[FlashEvolve §3.2–3.4](https://arxiv.org/html/2605.08520v1)：已有版本差过滤、反思重基、异步队列及worker流量平衡；因此“修复过时工作/压队列”不是新的宽主张。[Scepsy](https://arxiv.org/html/2604.15186v1)已优化多LLM的GPU份额/TP/replica；[Shadow Price of Intelligence](https://arxiv.org/html/2608.23986v1)以理论/数值模型分析降质量引发重试和拥塞，不能再把“便宜调用反而贵”当未知。可检验的剩余问题是本地生成模式是否真实改变下游执行压力及最终质量，当前尚无证据；需要超过固定mode、CoT-retry和合理队列控制，而非仅添加等待罚项。
- 17736的48条资格批止于记录器不支持冻结源码的异步接口，0模型调用/0评分；不是CoT-retry负效果。零结果时显式追加一个独立入口修正v2，源/分母/费用均分开，窗口不超13GPUh；若再入口失败本窗不重提。不得把CPU修复或已有文献策略资格当论文创新。
- 10/12提交前进一步查到直接先例[What Makes LLMs Reason in (Multi-Turn) Code Generation? §5.2/D.3，CoT-retry](https://arxiv.org/html/2410.08105v1)：先无推理生成、失败后增加推理已有。故feedback-effort降格为已知策略在MLE整池同预算下的参照资格检验，不能称方法创新；已冻结矩阵/门不改，不靠改名字或“我们是MLE”主张首创。若阳性也只是更强实用参照，仍需新机制超过它。
- 10/12 HK15:29后：停硬等待，不向其调阈值。闭合17681 greedy/pending的12次Debug中0次已落后于当时共享incumbent，暂拒绝“放弃过时修复”干预；分析角色不是成本主项。新资格实验改的是推理开销时机，不是等待或父排序：fast-Improve/medium-Debug对两常数代码模式，同共享greedy。必须核实际template/request mode与最终质量，不能从cheap更多推收益；[Ares](https://arxiv.org/html/2603.07915v1)已有按步骤动态推理强近邻，角色分配本身不叫首创。区别R9模型换角色、R11重写同想法，但未知是否值得做；source feedback_effort_*，48固定/cap13GPUh，不训练底座或恢复多保真。
- 10/12反馈硬预约17681：48分配/40启动/39正常，执行队列截止临时文件错误使第5池失败、第6池未开始；不以该失败推断模型效果。已完整首轮去噪硬等待0.04551226514614451，差于greedy0.013749410741741694及pending-UCB0.02482337877709754；Aerial也未满足对greedy不退步。两方法池真实发生空闲许可等待且各完成非起点父解修改，因此不是旧“旋钮没介入”。停止当前硬预约，不修阈值追正；第二重复不填补、不复跑。首轮同父重叠调用中3次真实改善反驳“同父=无效重复”的无条件前提，不能以此声称异步普遍更优、机制新颖或胜SOTA。原始独立读出/事后诊断与全成本见sandbox_scheduling/feedback_parent_v1_closed。
- 10/12新假说区别：不再给已选父解的生成请求加等待罚项，而是在LLM调用前共同选父程序；新处理只硬预约同父code直到首个外部反馈，允许无就绪新父时闲置生成器。强实用参照greedy共享最好父程序，直接近邻[WU-UCT/P-UCT Eq4](https://arxiv.org/html/1810.11755v3)的在途计数只改探索bonus，本文只做明确archive适配；它并非未考虑pending，不能用弱无pending对照冒充突破。CostAda已有跨frontier高分交换，BaSE已有bandit算力分配；共享/多样性/父选择本身不新。实测须证明额外等待胜两个共同archive参照；若不胜停此硬预约，不调并发/阈值追正。新source feedback_parent_*_20261012；尚无新质量结论。
- 10/12生成前联合准入17675已闭合：48正常/有效、45外部分数重算，原质量门false。两joint池15次稀缺选择中资源项改选0次；去噪一池停起点0.04551226514614451、另一池0.013718285978365746胜两参照；不把后者挑作方法确认。Aerial起点近1.0且不足0.001改善空间，须在新设计前检查可达到的效应上界。次要全外部有效终点不翻转；停当前等待惩罚配方、不补seed、不以新名字继续。保留普通续改可改善去噪的事实，不推联合控制普遍无效；本批未识别资源项增量。证据sandbox_scheduling/generation_joint_v5_closed，完整成本含两次入口失败13.658333333333333GPUh。
- 10/12机会筛查：17592/17656/17670三批80run、40队列分别核；候选稀缺准入选择均0，仅2次preview/preview竞争。journal Improve1/0/0且均无accepted Improve；不在这组负载扩候选排序器，也不推普遍无效。原件/独立复核在sandbox_scheduling/opportunity_screen_20261012，未运行新GPU或改旧效果门。
- 生成前“搜索链进展×当前资源占用”的联合准入只是候选假说，不是已成立新主线算法；近邻CostAda v4已有收益/成本、剩余预算与测试预留（但预算排除确定性执行），MARS已有续轮/资源准入，SAGA已有工作流原子调度。须超过它们的合理组合及廉价续轮优先，而非换MLE任务或把token换秒便称创新。要检验的额外项是并发状态造成的边际完成代价变化，不使用未来耗时/结果；保留每任务预算，不以省钱为由训练底座。
- 10/12揭读前补核[CostAda v4 §B.3 / D.1](https://arxiv.org/html/2607.26828v4)：跨frontier分配只给global-best改善记功，局部改善仅能通过探索项继续获机会；其账本排除确定性执行。17675的cost参照用各链自身改善频率/整轮耗时，没有复现上述global credit与完整探索控制。因此即使本批joint胜出，也只是该资源项相对明确廉价参照的探索信号，不是胜过CostAda或证明创新；后续强参照应区分同任务portfolio best改善与链内追赶，不能静默改正在跑的批次。
- 用户将重点转到学长 autoresearch_project@d82dcd845e30e9771750510028d38a6d1d979c43 的 shared_sandbox 修正版；硬件准入/共置不是R10解质量预测或R4执行状态复用。当前现场/授权只看CURRENT_DIRECTION与短交接。
- 10/10：17366两新源码变体12/12、同任务家族有限系统阳性，但CNN时序漂移未排除。旧17128/17017等不同负载或对照不拼总体平均；固定查询不变不是全任务质量或GPU kernel并行证明。原回执见各sandbox_scheduling闭合目录。
- 两轮文本live（17279/17368）均未过冻结质量门；17368虽两任务都有Improve、两臂各4，仍只有3/8双方有效成绩对且全负。执行卡采样负荷低，不能代表持续GPU训练共置，也不豁免原失败。先核机会与强参照，停止扩大这一文本配方。
- 17308宽度批不完整、条件live2/4未启动；17322/17326握手诊断没证明根治，17376/17380反序批也没有有效配对。不围绕失败无限补跑；详情保存在原件/短交接，不把旧待授权当现状。
- [SchedMate](https://arxiv.org/html/2510.03334)已有源码/历史/日志、免部分profile、干扰撤销；[2024 poster](https://wang-zerui.github.io/publication/schedmate/)还含版本跟踪。[Synergy](https://www.usenix.org/system/files/osdi22-mohan.pdf)、TGS/Salus、ElastiCo、DetShare/Pollux覆盖资源互补/透明共享/行为耦合。对象接口不同不能直接称创新。
- [MARS调度](https://arxiv.org/html/2604.26963v1)、Cortex/SpecBox、SAGA、AgentSysBench、Agentic CPU-GPU Scheduling覆盖阶段管理、续轮优先、准入与工具放置；不是下文同名记忆论文。MARS公开实现的session入口控制不等于我方执行许可，删KV/内层功能不能冒称完整复现。
- OpenMLE、DSec已有MLE共享后端或沙箱生命周期；Latency-Aware Orchestration、Aragog、VenusRL、SJF-BSBF限制广义关键路径/质量约束/资源增长/首返权衡；AgBench、On the Clock、SWEET已有吞吐/成功率/搜索偏差讨论。详细原文、版本和适用限制见sandbox_scheduling/README及本次压缩前Git；不能凭一个限定不完全相同就忽视强近邻。
- 10/11再核SchedMate§3.3：已有首错误定位、基础设施/框架/应用分类、诊断后恢复；本窗就绪/内核生命周期修复不能称新的故障处理方法。其日志语义也不替我们提供历史EAGAIN的现场线程/cgroup证据；错误信息分类不等于根因已获干预验证。
- 10/12补核[MARS §6.3/Fig11–12、§7](https://arxiv.org/html/2604.26963v1)：真实OpenHands对照已有框架timeout截断及任务完成率分析。因此“请求超时会损害任务完成”不是我方新发现；17656的240/600秒只诊断我方小预算保护设置，不包装成新调度方法。真正增量仍须在可靠强基线下兑现同预算外部质量收益，不能把8条run当8个独立池重复。
- 10/12的17656已闭合：600/240有效原生终点3/8对1/8（denoising2对0、aerial各1），首生成失败0对3，原探索门通过；但0/8完整质量分对，仅固定顺序单池对且lane部分换卡/到达顺序变化。有效完成率是局部正信号，不是方法胜出；我方240s保护并非学长后端默认，不能以弱请求基线宣称新调度收益。旧17592未过门仍保留。证据sandbox_scheduling/image_deadline_v1_closed。
- 10/12新32条ABBA/固定物理lane复验17670：600/240原生有效终点4/16对1/16，正常16/3，首生成失败0/13；只有1/4池任务终分对可比，aerial差-0.0001309579170742925，0/16同seed分对，冻结质量门false。36030GPU秒，结构/6评分重算/独立统计通过。停止当前确认配方，不从覆盖收益推出终分或调度创新；缺失不填零、不改门、不补seed。源与结果见sandbox_scheduling/image_deadline_replication_v1_closed。
- 同批只读查到1个外部有效exit0提交被冻结MCTS的LLM is_bug条件否决；journal有该节点，并非导出漏记。是旧分析器/来源一致性的具体问题（本地同名代码已修），不称全新方法，不改已冻结终点，不直接推断取消否决会改善完整搜索。恢复时先核实际snapshot源码与评分→节点→终点链，不能只看工作树或哈希通过就假定语义已修。
- 原AIRA-dojo的策略结果依赖算子条件且主实验24h；我方旧600s/root5无Improve只说明本轮覆盖不足，不解释原论文，也不是新发现。旧16370的22.72%预留窗口、16624释放原语、AST显存选参都不是已兑现的调度收益。
- 接口公平性：先跨独立run共享、保留run内返回/调试顺序；同源码仍可能随资源改变batch等行为。先测代表性真实GPU开发负载与廉价阶段准入；只有重要剩余损失才研究语义方法，不预设LLM调度必要。硬边界与预算不因本索引整理改变。

## 已核近邻：检索入口，不是它们已替我们验证效果

- 10/9 v7事后覆盖诊断：16条600s原生MCTS全部未完成首批5Draft、完成Improve=0，18有效返回均有journal。应先确保负载确实暴露所声称的搜索阶段，再谈调度质量收益；不能将增预算/减分支数量本身称新方法，不能由Debug存在否认反馈已被部分使用。17322空内核复现一次握手故障，不是候选/训练负载缺陷，亦不解除17308完整门。

- **M-DESIGN**：edit-gain图、任务相似度及预测修改；旧裁决0CU。https://arxiv.org/abs/2507.15336
- **MLE-STAR / PatchFusion**：组件精修、局部编辑组合；10/2复盘第九节。https://arxiv.org/abs/2506.15692 / https://arxiv.org/abs/2607.01597
- **MARS / CONTRAMEM**：比较经验、跨分支利用、成功失败对比形成程序经验。https://arxiv.org/abs/2602.02660 / https://arxiv.org/abs/2608.22533
- **CBR-R&D-Agent / VERDI / QCR**：可执行案例、响应指纹与目标侧验证、目标绑定复用；10/4本地EXPERIMENT_LESSONS已记录。https://arxiv.org/abs/2606.05250 / https://arxiv.org/abs/2608.09537 / https://arxiv.org/abs/2608.12847
- **Repo-To-Skill/DisCo / Skill-Pro**：经验证操作知识及可执行技能；10/2复盘第五节。https://arxiv.org/abs/2609.02749 / https://arxiv.org/abs/2602.01869
- **GOME / Iris / AgentX-Model**：反馈定向改进、主动证据、诊断选择；并非“再加analyzer”空白。https://arxiv.org/abs/2603.01692 / https://arxiv.org/abs/2608.02143 / https://arxiv.org/abs/2609.30001
- **Component-Aware Feedback / MARICL / NSR-Boost**：组件变化与指标记忆、误差样例、可执行修正；历史0L412/404。https://arxiv.org/abs/2609.38639 / https://arxiv.org/abs/2605.22897 / https://arxiv.org/abs/2601.10457
- **OpenMLE / Matryoshka / SCVD**：父解收益过滤、角色互换、学生状态后的验证/恢复蒸馏；历史0L425。https://arxiv.org/abs/2607.28568 / https://arxiv.org/abs/2607.25090 / https://arxiv.org/abs/2609.38812
- **Implementation Lottery / MLE-Ideator**：前者同想法多次实现、实现噪声分解及追加实现建议（§8）；后者分离想法/实现。前者不评E2E搜索（§7）。前者已在旧0L424出现，本次是补读，不是首次发现。https://arxiv.org/html/2607.26587v1 / https://aclanthology.org/2026.eacl-short.32/
- **Recovering Wasted Compute / Ideation Diversity**：跨分支debug约束、调参、TS回溯；想法多样性与AIRA受控消融。不能把复用错误/多样化/重启叫新机制。https://arxiv.org/html/2608.10424v1 / https://arxiv.org/html/2511.15593v1
- **Centaur / LLM与传统HPO混合**：10/5核原文§4–5，CMA-ES向LLM共享均值/步长/协方差，部分trial由LLM提议；混合宽主张已有。作者单一autoresearch训练场景且预算排除LLM推理，不等于我方MLE全成本收益或可迁移结论。https://arxiv.org/html/2603.24647v1
- **LLaMEA-HPO**：10/6核§3.3，已把优化后程序/参数反馈给LLM，结构变异时保留参数，再交HPO。结构搜索和调参分工、保留已优化参数本身不新；当前四格只核自然修改机制。https://arxiv.org/html/2410.16309v1
- **TIDE**：10/6补核最新版v2的§3.2、§4及D.6，已明确提出结构逻辑与数值优化耦合会掩盖有潜力的程序，并用嵌套差分变异调参；含800次执行配平及耗时/token表。§3.2.2只对与精英有竞争力的后代启动精修，且每个后代使用自己的局部参数种群，不是把不兼容结构的参数向量盲混。不能凭摘要推断实现有该错误，也不能把宽假说或“先结构后调参”称新；其组合优化实验不替代我方MLE证据。https://arxiv.org/html/2601.21239v2
- **Self-Healing Harness**：10/6核主文及附录，固定底座、外部规则持久化、局部改进伴随旧案例退步、回放准入都已有。对象是操作规则跨案例保留，不是MLE代码数值bundle；作者未执行关键准入消融且开销增加，不能冒称已有我方同预算答案。https://arxiv.org/html/2609.24130v1
- **GEVO编辑交互分析**：非LLM的GPU程序演化已用原程序/全编辑/单加/单去分离独立与相互作用编辑；四顶点相互作用计算不是新方法。新价值必须来自实际MLE机制及可部署收益。https://doi.org/10.1145/3703920
- **When Models Edit Too Much / RECAP**：10/6核原文；前者已研究已知最小函数修复中的过度编辑及保留提示，后者已研究仓库补丁生成后精修，并显示单纯缩小改动会损害正确性。不能把“少改/保留提示/去掉多余修改”叫新机制；当前MLE数值反事实须以实际质量和全成本区分。https://arxiv.org/html/2609.04061v1 / https://arxiv.org/html/2608.13292v1
- **EvoTrace / EvoReplay**：10/6核原文§4–6，已做跨框架轨迹、参数重调、组件移除、模型/上下文回放；数学任务中24次BO重调中间程序是强近邻。回放分解和结构/调参贡献本身不新。其域主要数学与竞技编程，不能直接推我方MLE结论；同样不能把换到MLE当作已成立创新。https://arxiv.org/html/2605.20086v1
- **遗传编程的非活跃代码 / 中性变异**：当前未影响输出的组件可能保留后续搜索价值，不能从case0推“冻结/删掉非活跃组件必然更好”。该概念已有长期研究，需区别执行路径事实与未来可演化性。https://doi.org/10.1109/TEVC.2006.871253
- **CostAda / EvoPINN**：10/6核原文，局部分支进步与全局进步的区别、按收益/成本分配，以及按模块演化并给诊断已有相邻方法。CostAda成本排除确定性执行，不直接回答MLE全成本；EvoPINN的固定接口不等于任意自然代码可安全拆分。https://arxiv.org/html/2607.26828v1 / https://arxiv.org/html/2607.26490v1
- **RPG**：10/6核§4.2与C.3，基于耗时的reward-rate训练已直接用于MLE；其均值奖励/时间目标与我方最终best-so-far不同，不能据此声称成本意识本身新，也不能把目标区别叫原创（CostAda已明确best-so-far）。我方不更新agent底座。https://arxiv.org/html/2609.36393v1
- **GI-Agent / 编辑表示**：大学作者摘要及检索到的§3.2.3明确用diff作为演化节点、应用到原程序；“从整程序重写换成局部补丁”可作实现参照，不足以称新方法。https://discovery.ucl.ac.uk/id/eprint/10222371/
- **NSR-Boost（补读§3–4）**：10/6核原文，已冻结父模型、按残差定位区域、由LLM产生局部修正，内层TPE且冻结继承参数，再训练上下文聚合器。“不要求新程序单独胜父解，只要补足错误”不是新概念；其表格数据结果不证明我方MLE全成本收益。旧R5与旧集成上界仍须保留，未获新证据不重开。https://arxiv.org/html/2601.10457v1
- **Evolutionary Ensemble Search（EES）**：10/6核§3–6，已将父条件修改、相对父解信用、程序内部选择、预测级组合与跨run记忆统一；架构存在不等于受控效果成立，作者明确其开发ledger不是盲评/组件收益确认，核心引擎未公开。不能把它当我方成功证据，也不能忽视它对宽方法概念的覆盖。https://arxiv.org/html/2609.17590v1
- **Mutation Without Variation**：10/6核§3与讨论，无选择压力的LLM修改在受限DSL中出现结构收缩；作者明确仅基因型而非行为分析，未证明真实MLE预测坍缩。我们已有预测重复诊断不能更名为新发现；跨域机制需要新的实证，不能以近邻局限代替我方正证据。https://arxiv.org/html/2606.05408v1
- **Hyperparameter Transfer Across Developer Adjustments（HT-AA）**：10/6补核§3–6全文，已有算法/搜索空间/架构变化后的HPO迁移；仅优化新增参数、冻结旧最优的简单策略在其实验常不佳，best-first/T2PE还会继续优化旧维度。§6也提到源码分析映射参数。100seed的表格/代理任务验证不等于我方MLE全成本或最终test收益；“修改后迁移调参经验/语义映射参数”不能自动称新。https://arxiv.org/html/2010.13117 / https://github.com/hp-transfer/htaa_experiments
- **Beneath the Diff / DAPS**：10/6核§3–4及限制，已有“源码编辑多样而机制趋同”的诊断，以及类别重加权、语义记忆去重和验证回退；明确区分循环评分、可影响决策的audit及最终blind，并设置匹配audit访问的参照。对象主要是四个小规模NLP研究循环，不是我方MLE全成本效果证据；不能把语法新颖但行为重复、更丰富提案或多一层验证当空白。https://arxiv.org/html/2609.00077v1
- **RIPPLE / Local Edits, Global Ripples**：10/6核§2–3，固定底座、预定义分段提示和补丁库，分别判断改哪里、合成既有修改后能否保留；明确局部有益改动组合后可变坏，并在当前前缀上回放。其对象是工作流prompt-policy而非MLE候选代码，固定补丁库也不等于自动发现新算法；但“局部性不等于效果局部、交互感知回放准入”已有直接近邻，不能更名为我方新方法。https://arxiv.org/html/2609.12127v1

- **Auto Research with Specialist Agents**：10/6核§3–5及附录D–H，已有固定角色拆分、共享实测谱系、失败/预算边界反馈及同200提交数的通用多agent/单agent/no-lineage参照。其no-lineage同时去掉历史假说/分数/失败/差异工具等，只留当前最优代码/分数，不能把打包消融说成某一类反馈单独有效；正文也有具体资源边界案例。提交数相同不等于总耗时/token相同，附录GPU数是上限核算且另有前期成本；轨迹不等于跨seed确认。我方不能把“角色分工+约束反馈+经验库”更名重开；这篇也不替代我方收益证据。https://arxiv.org/html/2605.05724v1
- **Rehearse**：早在8/23历史0EB已读，本次仅补回短索引，非新发现。执行前同父提案判断、按候选检索既有修改及结果、深层判断退化及收益均已有；训练run数预算不等于全推理/执行成本配平。不能把这些机制重命名为新critic或记忆路线，历史score-channel授权也不因此复活。https://arxiv.org/html/2607.27687v1
- **优化时钟／预算适配**：AdamW的学习率、衰减、数据量、batch耦合已有理论与实验；Budgeted Training已有按预算调整学习率。10/6固定80公开对的只读检查没有确认训练时钟错配：八对支持设置变化不是八个错误；Quest还包含debug时钟修正，唯一OneCycle父子均在batch内step。暂不为此新开GPU或把已知调度器修正当方法。https://arxiv.org/html/2405.13698v3 / https://www.cs.cmu.edu/~mengtial/proj/budgetnn/ ；证据：results/research_synthesis_20261006/clock_hypothesis_screen.json。

- **PLAyBOOK / delayed-feedback BO**：10/12补核ICML原文主页；已有在途查询避让、异步与同步效率比较及随机延迟反馈下的探索。等待/避重本身不是新方法；当前MLE父程序会随真实反馈产生新可修改对象，但这个问题差异也不等于创新已成立。只做硬预约vs共享greedy/pending-UCB的整体效果验证；阳性仍须排除固定低并发参照。https://proceedings.mlr.press/v97/alvi19a.html / https://proceedings.mlr.press/v162/verma22a.html

旧检索可能不是论文最新版本；正式新颖性判断须重新核原文与实现。查不到词不等于排除了近邻。

- **AREX-2（9/29，10/13补读§2–3）**：已有Qwen3.8-27B长轨迹训练、保留失败上下文/只监督有用决策，以及MLE相同skills与rounds的模型对照；不能称训练搜索能力/减少所需轮数首创。无正确性反馈扩展在BrowseComp，不是MLE日更循环或去官方score依赖的同预算证明。https://arxiv.org/html/2609.38288v1
- **TTT-Discover v2（10/13补读§2–3/4.5）**：已有针对单个问题的权重更新、archive复用、偏重最优发现的entropic目标；“只用本任务经验自举”不是空白。其目标是一个最佳程序，不要求产出可泛化policy；采样配平消融不是我方全池服务/执行/训练预算验证，也不授权读取MLE隐藏集。https://arxiv.org/html/2601.16175v2
- **Guidance-TTT（10/5，10/13补读§3–4、A/B）**：已训练小型父条件指导器、固定更强执行器并用group-relative验证反馈；“只学短战略/不训大执行器”不是新机制。四任务与单轨迹规模分析不能替代我方跨任务重复；部分成本比较训练配置/调用数不同，不能搬成严格同成本因果结论。https://arxiv.org/html/2610.06269v1
- **Recursive Harness Self-Improvement（RHI）**：10/13核原文，已有harness改进与高effort参照、模型—harness共同演化设想；主任务为合成ML研究设计/LLM评判，不是真实执行MLE质量，也未实现每日底座训练闭环。固定底座加harness超过更高档位的宽主张并非空白。https://arxiv.org/html/2607.15524v1
- **When Agents Slow Down**：10/13仅核原始摘要（HTML不可用），已有best-so-far/token曲线、独立采样参照与分配长短session；简单画成本曲线/平台期重启不构成原创。尚未核全文，不能断言其未计执行成本或无相关消融。https://arxiv.org/abs/2609.15309
- **FACTOR / How Much, Then Where**：10/14核摘要、§2–3.1，已有动作信用与动作内词元分配分离、信用守恒和action-mean归一化；长度无关性针对行为策略处、裁剪前的标量目标，不是完整梯度或任意训练状态保证。任务是ALFWorld/WebShop/ScienceWorld，不替代MLE效果；通用“把终分合理分配给步骤”不是空白，不因此授权我方训练agent或恢复TD。https://arxiv.org/html/2608.07118v1
- **TRACE / Turn-level Reward Assignment via Credit Estimation**：10/14仅核摘要/引言，使用冻结参考模型对gold-answer的概率构造回合信用，不额外训练critic不等于不训练agent。不能把MLE未来最好程序当作无代价gold-answer，或把修复/创新信用分离直接宣称原创。公共verl的agg_loss已有token/sequence多种归一化，但不能用其默认实现推断学长私有51ff1b4c的实际训练。https://arxiv.org/html/2607.13988v1 / https://verl.readthedocs.io/en/latest/_modules/verl/trainer/ppo/core_algos.html

## 新提案准入：不是新的工程审核流水线

在聊天中用四行就够：

1. 最近旧路线：本表ID＋原实验证据。
2. 机制差别：实际改变的决策/信息/行动是什么，不接受仅名称、模型、seed或提示微调。
3. 为什么现在值得做：新的事实能解决哪一处原来未识别的问题；未知不冒充正证据。
4. 最近论文与强参照：如何区分、全成本是否值得；尚未明确则只保留假说。

不同时把多个弱假说都命名为主线；新的原理也必须先有最小验证，不保证正结果或录用概率。
硬关闭方向、保护集和预算规则仍以CURRENT_DIRECTION及用户最新明确要求为准。
历史完整检索：`rg -n '机制关键词' phase1/CURRENT_DIRECTION_HISTORY_THROUGH_20261005.md`，再取附近段落；不整篇读入。
