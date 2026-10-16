# 路线与机制索引：先查旧证据，再提新方向

更新：2026-10-16香港。当前方向/授权只读CURRENT_DIRECTION，现场只读CONTEXT_HANDOFF_CURRENT。
压缩前完整版本：Git 6c47086a603b4c7afcc25a3e80f9d5648c3bee63:phase1/ROUTE_DECISIONS.md。
旧长文、原批次和门均保留；按关键词检索该Git版本或历史文件，不每次整篇载入。
“停止一个配方”不是“所有变体无效”；工程失败、局部阳性、方法确认分开。

## R14：资源调度，当前只有强基线资格问题

- 18770固定/共享FIFO六卡32条完整，29评分重算及独立复核通过；质量门false，去噪一负一正/Aerial一正一负。
- 两shared池均实际迁卡且排队总时长较fixed低；减少等待不是稳定终分改善，不补seed/改门救当前配方。
- 唯一旋钮是执行GPU归属；原2任务/2反序比较/预算/质量门见CURRENT_DIRECTION。
- FIFO不是创新，下一方法必须超过合理共享池，不以弱固定绑卡参照证明论文主张。
- 两共享池不是32个独立处理重复；反序降低顺序混杂但不消除共享服务/复用任务限制。
- 旧80终点/20任务池时序已验证：更多有效返回可以没有新pool-best。
- 删除所有观察到的等待仅是固定历史条件诊断，不是新轨迹、FIFO质量预测或普遍上界。

## R14已试机制及禁止偷换

| 机制 / 批次 | 已观察结论 | 决策与证据目录（sandbox_scheduling） |
|---|---|---|
| 固定绑卡→共享FIFO：18468/18510/18673 | 前两为我方资格/信号接线错误，18673容器入口缺失，均非方法反证 | 各pooling_*_closed保留；18770为独立新root，不重开旧批 |
| score step30部署：18269 | 32完整，去噪两重复best/median更差，Aerial一正一负 | 停该配方；weight_confirmation_18269_closed |
| metric step30部署：18412 | 48完整，新metric两重复去噪不胜旧fast/medium | 停该配方；metric_deployment_18412_closed；不同训练数据不是reward消融 |
| 新旧×effort：18253 | 32完整但首次真实提示漂移；质量门也false | weight_effort_18253_closed；不归一化救门、不将历史累积当权重收益 |
| xhigh：18161 | 24完整；xhigh四个代码返回均32768截断，无新有效解 | long_effort_v1_closed；固定预算失败不等于自然长推理无能力 |
| 角色反馈effort：17740 | 48完整，两次胜medium但对fast一负一正 | feedback_effort_v2_closed；CoT-retry已有，不补seed/改cap |
| 同父硬预约：17681 | 不完整且完整首重复未过门；同父重叠3次真实改善 | feedback_parent_v1_closed；同父不等于无效重复，停硬等待 |
| 生成前联合资源项：17675 | 48完整，资源项改变选择0次，质量门false | generation_joint_v5_closed；未识别资源增量，不换名重开 |
| 请求时限：17656/17670 | 生成/有效覆盖局部提升，终分完整确认失败 | image_deadline*_closed；弱240秒保护参照不作创新 |
| 同卡共置：17366/17368 | 神经fixture局部吞吐阳性但时序漂移；真实live质量门未过 | neural_extension/live_twochild；不是跨任务质量确认 |
| 2+4容量与原factory：17571/17576 | 固定程序执行/隔离已通过 | 不重复G0；容量不是新方法收益 |
| 固定代码负载机制：18812 | 8/8完整，两程序共置step少33.3%/34.1%，两次评分均较独占差且均值差超各臂repeat span；8重评分/独立统计通过 | 过事前16执行排序扩展门；已知DEV/2重复，不是显著性或E2E。clock_contention_18812_closed |
| 跨节点：17577–17580 | 空命令也派发失败，独立于模型/镜像 | 管理员问题；本轮继续已通同节点2+4 |

## 更早相邻路线（索引，不恢复授权）

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

## 近邻边界：方法不能靠换名字获得新颖性

- SchedMate已有源码/历史/日志语义、部分免profile、干扰撤销及故障恢复；新调度必须比较合理廉价/语义参照。
  https://arxiv.org/html/2510.03334
- HyperSched已优化固定资源/截止时间下最终最好精度，假设中间训练进度、可checkpoint/恢复及共同扩展规律；不能把“质量而非吞吐”称新颖。18812只检验黑盒程序墙钟自停时，负载是否改变同源码反馈；此差别尚非方法贡献。
  https://arxiv.org/html/2001.02338 （2026-10-16核§3.1.1、§4；不恢复ASHA/多保真旧线）
- Winning by Peeking已有机器争用改变AutoML比较/有限墙钟内trial数；Mosaic已有kernel干扰准入；RTCSA2020已有mandatory/optional质量调度。不能把“争用改变排序”或“质量感知”本身称首创；原文阅读范围见clock_scheduling_neighbors_20261016.json。
- MARS已有session准入、续轮优先、timeout/任务完成分析；我方执行许可不同不构成创新。
  https://arxiv.org/html/2604.26963v1
- Scepsy/PASTE/BAVT/ZEBRA/PeakBench等限制资源分配/端到端服务宽主张；详见pooling_research_boundary_20261015.json。
- Synergy/TGS/Salus/ElastiCo/DetShare/Pollux覆盖互补共置；GPU驻留PID、host optimizer包络不等于kernel并行。
- CostAda v4已用global-best收益/成本分配与预算预留；旧我方简化参照不是完整复现。
  https://arxiv.org/html/2607.26828v4
- WU-UCT/P-UCT/PLAyBOOK已有pending处理；FlashEvolve已有过时工作/反思重基/异步流控。
  https://arxiv.org/html/1810.11755v3 / https://proceedings.mlr.press/v97/alvi19a.html / https://arxiv.org/html/2605.08520v1
- CoT-retry已有先快写、失败后推理；Ares/LASER/InfraMind已有按历史或负载分配推理预算。
  https://arxiv.org/html/2410.08105v1 / https://arxiv.org/html/2603.07915v1
- When Agents Slow Down已有best-so-far/token及session分配（前次仅摘要/README，全文未核）。
  https://arxiv.org/abs/2609.15309
- TTT-Discover/AREX-2/Guidance-TTT覆盖本任务自举、轨迹训练、固定执行器学指导；我方不训练agent底座。
- M-DESIGN/REHEARSE覆盖修改增益预测与检索；MLE-STAR/PatchFusion覆盖精修与编辑组合。
- Centaur/LLaMEA-HPO/TIDE/HT-AA覆盖结构×数值优化分工/迁移；四格编辑相互作用不是新方法（GEVO）。
- GOME/Iris/AgentX/NSR-Boost/Beneath the Diff/RIPPLE覆盖反馈、残差、语义重复及交互验证。
- 上述每篇原文链接、章节和限制均在压缩前Git版本；新颖性定稿时重核当前原文，检索不到词不证明空白。

## 提案只需四项，不另建审批流水线

1. 对应旧路线和原结果；未见于当前窗口不代表没做过。
2. 实质改变哪个决策、信息或行动，而非模型/seed/名字微调。
3. 新事实为什么使它值得测；反事实模拟不冒充实测。
4. 直接近邻、强基线、固定全成本及可否证门；没有独特性就按参照资格报告。

优先用已有证据缩小未知，再做一个有辨识力的最小实验；不同时制造多个“主线”。
完整旧机制检索：git show 6c47086a603b4c7afcc25a3e80f9d5648c3bee63:phase1/ROUTE_DECISIONS.md，再rg关键词。
更早历史：CURRENT_DIRECTION_HISTORY_THROUGH_20261005.md；只取相关片段。
