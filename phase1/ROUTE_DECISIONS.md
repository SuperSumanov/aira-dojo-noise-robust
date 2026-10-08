# 路线裁决表：先排除重复，再提出新机制

更新：2026-10-08香港。当前状态见CURRENT_DIRECTION；本表是机制索引，不是运行授权。
“停止当前配方”不等于“所有变体不可能”。读原始证据后才解释历史数字，不汇总异质批次为总体胜率。

## 本次必须纠正的重复推荐

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

## R14（10/6新增候选方向）：MLE沙箱资源准入，不是已成立方法

- 10/8追加16996：12/12、2神经程序/2任务原seed重启，三配对中位1.3508923175938645；每程序训练步数及六份输出数值全同，独立审计通过。扩大了朴素并发的有限支持，不是新语义机制或live搜索收益。16994和16996是不同负载，不合并成跨任务平均。
- 10/8追加16997机制对照36/36：仅初始化并行约1.39倍，候选双并发对该强参照仍约1.32倍（精确值/三配对见CURRENT_DIRECTION），输出与训练量不变、独立验证通过。该有限正信号支持真实执行重叠，不是“复杂LLM调度必要”的证据；下一步测同类原程序争用，不恢复旧路线。
- 10/8新增16994小试验：36尝试/35完成，A/B各12/12、三次串行/双并发中位1.7852942816262258且输出数值全同。观测GPU clients≤1，不能称GPU训练共置；4小程序/3任务/原seed重启，不是语义新方法或E2E。C一次候选前超时保留，不重跑挑结论。该最新授权/结果覆盖下文历史“尚未获批/暂无效果”，详见CURRENT_DIRECTION与短交接。
- 学长autoresearch_project@d82dcd845e30e9771750510028d38a6d1d979c43修正版；改变硬件准入/共置而非预测解质量(R10)或复用执行状态(R4)。保留原候选算法、生成与搜索策略，先只测系统收益。
- 本轮读[SchedMate](https://arxiv.org/html/2510.03334) §3–4：源码/历史检索/免部分profile/干扰撤销已有；无匹配回退profile、无进度跳过对应撤销是明确限制，非我方优势证据。作者[2024 poster](https://wang-zerui.github.io/publication/schedmate/)还有版本差异跟踪，不把父子diff复用叫新。
- [ElastiCo](https://arxiv.org/html/2608.07971v1) §4已有画像与非侵入GPU共置；[AgentCgroup](https://arxiv.org/html/2602.09345)已有意图驱动CPU/内存。宽概念高度相邻，原文旧“没人做过”不采用。
- 只开放小资格研究：真实未知程序/阶段变化/不可便宜撤销条件是否常见且有成本；语义能否胜简单特征、telemetry与SchedMate式参照。用户已批准16624六次生命周期原语，6/6完成、159GPU秒；372MiB保留vs0额外显存，文件全同，不是生产泄漏/系统增益。factory上层本就close；必须用执行级借还整卡作强基线，再谈共享/语义。旧16370返回生成占77.37task-slot分钟（全4GPU池预留22.72%），不是可省百分比；尚未获新调度效果批次/付费/训练授权。
- 追加近邻：[Cortex](https://research.google/pubs/cortex-workflow-aware-resource-pooling-and-scheduling-for-agentic-serving/)已有阶段资源池；[SpecBox](https://arxiv.org/html/2607.23933)已有生成中沙箱预热/跨步预取；[Agentic CPU-GPU Scheduling](https://arxiv.org/html/2607.22242)已有19工具profile、三选、重测与交换。一次性未知程序可否省去重复测量而保留安全净收益仍是假说；宽泛阶段分离/LLM调度均不能称新。
- 10/7资格复核：旧16370无可识别的额外执行积压，不能由22.72%预留窗口估计加速。固定公开程序中空闲显存分支会改变batch的纯算式已复算，但无实际共置/训练效果；它是R14公平性检查，不是R13数值修复复活。资源—行为耦合已有[DetShare](https://arxiv.org/html/2603.15042v1)与[Pollux](https://www.usenix.org/conference/osdi21/presentation/qiao)近邻，不宣称宽概念原创。

## 已核近邻：检索入口，不是它们已替我们验证效果

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

旧检索可能不是论文最新版本；正式新颖性判断须重新核原文与实现。查不到词不等于排除了近邻。

## 新提案准入：不是新的工程审核流水线

在聊天中用四行就够：

1. 最近旧路线：本表ID＋原实验证据。
2. 机制差别：实际改变的决策/信息/行动是什么，不接受仅名称、模型、seed或提示微调。
3. 为什么现在值得做：新的事实能解决哪一处原来未识别的问题；未知不冒充正证据。
4. 最近论文与强参照：如何区分、全成本是否值得；尚未明确则只保留假说。

不同时把多个弱假说都命名为主线；新的原理也必须先有最小验证，不保证正结果或录用概率。
硬关闭方向、保护集和预算规则仍以CURRENT_DIRECTION及用户最新明确要求为准。
历史完整检索：`rg -n '机制关键词' phase1/CURRENT_DIRECTION_HISTORY_THROUGH_20261005.md`，再取附近段落；不整篇读入。
