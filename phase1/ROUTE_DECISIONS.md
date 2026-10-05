# 路线裁决表：先排除重复，再提出新机制

更新：2026-10-06香港。当前状态见CURRENT_DIRECTION；本表是机制索引，不是运行授权。
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
- **TIDE**：10/6核§3.2、§4及D.6，已明确提出结构逻辑与数值优化耦合会掩盖有潜力的程序，并用嵌套差分变异调参；含800次执行配平及耗时/token表。不能把这条宽假说或“先结构后调参”称新；其组合优化实验不替代我方MLE证据。https://arxiv.org/html/2601.21239v1
- **Self-Healing Harness**：10/6核主文及附录，固定底座、外部规则持久化、局部改进伴随旧案例退步、回放准入都已有。对象是操作规则跨案例保留，不是MLE代码数值bundle；作者未执行关键准入消融且开销增加，不能冒称已有我方同预算答案。https://arxiv.org/html/2609.24130v1
- **GEVO编辑交互分析**：非LLM的GPU程序演化已用原程序/全编辑/单加/单去分离独立与相互作用编辑；四顶点相互作用计算不是新方法。新价值必须来自实际MLE机制及可部署收益。https://doi.org/10.1145/3703920
- **When Models Edit Too Much / RECAP**：10/6核原文；前者已研究已知最小函数修复中的过度编辑及保留提示，后者已研究仓库补丁生成后精修，并显示单纯缩小改动会损害正确性。不能把“少改/保留提示/去掉多余修改”叫新机制；当前MLE数值反事实须以实际质量和全成本区分。https://arxiv.org/html/2609.04061v1 / https://arxiv.org/html/2608.13292v1
- **EvoTrace / EvoReplay**：10/6核原文§4–6，已做跨框架轨迹、参数重调、组件移除、模型/上下文回放；数学任务中24次BO重调中间程序是强近邻。回放分解和结构/调参贡献本身不新。其域主要数学与竞技编程，不能直接推我方MLE结论；同样不能把换到MLE当作已成立创新。https://arxiv.org/html/2605.20086v1
- **遗传编程的非活跃代码 / 中性变异**：当前未影响输出的组件可能保留后续搜索价值，不能从case0推“冻结/删掉非活跃组件必然更好”。该概念已有长期研究，需区别执行路径事实与未来可演化性。https://doi.org/10.1109/TEVC.2006.871253
- **CostAda / EvoPINN**：10/6核原文，局部分支进步与全局进步的区别、按收益/成本分配，以及按模块演化并给诊断已有相邻方法。CostAda成本排除确定性执行，不直接回答MLE全成本；EvoPINN的固定接口不等于任意自然代码可安全拆分。https://arxiv.org/html/2607.26828v1 / https://arxiv.org/html/2607.26490v1

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
