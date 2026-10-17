# 路线与机制索引：先查旧证据，再提新方向

更新：2026-10-17香港。当前方向/授权只读CURRENT_DIRECTION，现场只读CONTEXT_HANDOFF_CURRENT。
压缩前完整版本：Git 6c47086a603b4c7afcc25a3e80f9d5648c3bee63:phase1/ROUTE_DECISIONS.md。
旧长文、原批次和门均保留；按关键词检索该Git版本或历史文件，不每次整篇载入。
“停止一个配方”不是“所有变体无效”；工程失败、局部阳性、方法确认分开。

## R14：资源调度，当前只有强基线资格问题

- 18770固定/共享FIFO六卡32条完整，29评分重算及独立复核通过；质量门false，去噪一负一正/Aerial一正一负。
- 两shared池均实际迁卡且排队总时长较fixed低；减少等待不是稳定终分改善，不补seed/改门救当前配方。
- 唯一旋钮是执行GPU归属；原2任务/2反序比较/预算/质量门见CURRENT_DIRECTION。
- FIFO不是创新，下一方法必须超过合理共享池，不以弱固定绑卡参照证明论文主张。
- 两共享池不是32个独立处理重复；反序降低顺序混杂但不消除共享服务/复用任务限制。
- 18807事后结构覆盖：78及时返回中75含clock退出，38有效返回中37含；不含guard也不证明安全。一刀切禁共置几乎退回FIFO，不值得直接以新方法扩跑；计数是原轨迹条件覆盖、非新策略反事实。
- 同批静态退出作用域：Aerial35/35有epoch命名循环，去噪40/43有fold命名循环；全部78源码/AST不同不等于独立家族。支持继续查任务结构差异，但不证明这些分支都执行过或都造成质量损失；granularity结构回执。
- 18819首32/128步host速率：5→1折程序co/solo约0.20–0.22，3→2折约0.69–0.71。严重干扰早期可见，不能据此声称超过SchedMate；独立solo参照有成本，此表不是其在线profile/eviction复现。
- 18807真实20次准入均candidate+candidate，仅3次双侧终端CUDAtrace，均不足前后32/128步。缺失受超时/错误条件影响，不能据此声称普通监测无效；SchedMate原文已有部分信息回退。见online-observability/admission-kinds结构回执。
- 旧80终点/20任务池时序已验证：更多有效返回可以没有新pool-best。
- 删除所有观察到的等待仅是固定历史条件诊断，不是新轨迹、FIFO质量预测或普遍上界。
- 10/17：18987在首组因去噪program2原300秒超时，4wrapper/3有效，733GPU秒，配对未获比较；冻结diverse后续不启动。日志显示第二整折结束已287.6秒，不能说只因落盘慢。
- 独立selectiveFIFO改变“可否共置”而非伙伴tie-break：仅Aerial同类可共置、去噪独占，保持FIFO/CPU/生成器/预算。32真实搜索、2反序比较、原终分门；任务先验简单参照，不称创新，不是新来源确认，更未比SchedMate。候选失败不删分母。
- 18997该配方32完整/35重评分、独立复核和12传输SHA通过；去噪两次best更差，Aerial两次略高，原质量门false。实际共置3/4次且保护延迟各7次，不能说策略没执行；停止，不补seed/延时，不推断所有自适应保护普遍无效。selective_18997_closed。
- 18997补独立AUC（Mann-Whitney）/RMSE（逐像素ID）实现：35/35评分一致，maxerror1.1102230246251565e-16；不用生产scorer/pandas/sklearn。仅指标独立，不是源数据构建/最终选解溯源独立；independent-metrics-20261017.json。
- 19004 quota32闭合但干预绕过：实际worker仍旧每任务2FIFO，4池借用0；名义pooled全局顺序违例12/7，旧每任务规则违例0。冻结读出失败，独立13SHA/事件重放确认；不算方法负结果或正式A/A研究。上层hook与真实host绑定不一致，原CPU门测错层；CPU修复2反例/10场景通过，不是线上效果。generation_quota_19004_closed。
- 18997封存后首程序哈希诊断：16对首轮prompt/配置seed相同、均有程序尝试，仅3对raw/AST相同（去噪0/8）；32首程序均匹配原生journal代码、首日志成功Improve且adapter_attempts=1，故不是执行包装代码造成哈希差异。独立计数/传输SHA通过，原代码AST和journal提取未独立重做。首尝试不保证首transport响应，原因未分解，不指认为vLLM错误。原实验是固定反序ABBA配对seed，不是随机处理分配；配对seed不等于同提案，不以单轨迹归因纯执行干扰。first-program-pairing/origin回执。
- 10/17核vLLM官方Reproducibility/Batch Invariance：默认在线结果不保证可复现，专门不变性会影响性能，已测模型列表不能替代本项目27B量化镜像验收。仅支持保留服务非确定性这个备选解释，不证明18997差异由它造成；不临时改已冻结镜像/开关，更不把已知复现问题当新颖发现。https://docs.vllm.ai/en/stable/usage/reproducibility/ / https://docs.vllm.ai/en/stable/features/batch_invariance/
- 18997额外无网络CPU调用链：两任务×两条件4配置/12模拟末端调用均传递正确seed，配对prompt/采样参数一致（temperature=.6、top_p=.95）；4传输SHA及独立配对通过。排除已检查配置的客户端丢seed，不是线上HTTP抓包或服务确定性证明；seed-transport回执，不修改19004。
- 18997角色/终分联结：去噪selective两池Debug调用9/7，高于配对shared的7/5，而Improve为6/7对6/8；原终分门仍false。8任务池/179调用全分母及PowerShell独立聚合通过。只说明更多周转未转成更多Improve或稳定终分；Debug不等于无价值、Improve不等于新想法，角色计数不能证明因果。role-yield回执。
- 18997实际谱系补查：76返回/34有效，2谱系未解；新父程序后代12返回/3有效，Debug贡献12有效。8任务池中4池在首提案之后仍获更好解；去噪一个池靠Debug从warm .04551226514614451到.015583024642243782，不能把Debug全当浪费或推断无需迭代。仅Aerial一池最好解来自新父程序Improve。独立聚合/时间记录/原终点/SHA通过，原始journal/代码关联未独立重做；首提案子集不是重启/无反馈反事实，不据此宣称新策略收益。adaptation-lineage回执。
- 18997截止/选解排查：全76候选返回均及时，35外部评分产物中34匹配合法返回，另1未匹配产物比原池best低.0002458801708332681，不是晚到有效解；8任务池记录的native-selected最佳值均等于原pool-best。两传输SHA/独立聚合通过，未独立复做原始join或native选择溯源。没有观察到靠补计晚到好解/换最终选解器挽救该批的机会，不推断另一调度器的反事实。late-quality/score-receipt-coverage回执。
- 10/17只读18807发现每任务2个生成许可留下10.47%–24.33%的有队列/总active<4状态；独立积分通过。vLLM408采样最大Running4、Waiting0、KV13.3%，不证明硬件空闲。后续只测同总4许可的跨任务借用，执行仍单许可；这是work-conserving强基线资格，不是17675旧资源打分重命名，更不是新算法/MARS复现。
- 同批余时独立核算：≥300秒余时下每池仍有约96/118/123/168秒借用机会，主要为analysis/debug；不是全部截止尾巴，也不是额外完成数。证据quota-slack-20261017-v1.safe.json及quota-slack-independent.json，原质量门不改。
- 10/17只读“评分→共享归档”线索：原生_analyze先于parent wrapper发布；18807的38有效结果37发布/1截止前未发布，只有1次真实Improve准入处于更好有效父程序尚未发布窗口。仅源码+既有时间诊断，未独立复现原始join、未生成新子程序，不据此开早发布GPU新线或称收益。feedback-publication-20261017-v1.safe.json；本窗口两32条已闭合，不开第三GPU方案。
- 10/17跨三调度批实际谱系：96条/229返回/101有效，24任务池中11池在首尝试后仍改善，Debug产32有效；43个新父后代返回中3好/11差/29无效。返回分母有截断，不能据此推断重启胜迭代；adaptation_three_cohorts/parent_delta_crosscheck_20261017.json。
- 补全准入分母：195次Improve中76用新父，40次准入余时<300s、26次300–600s、10次600–900s；已联结3次改善都在最后组。保留8未解返回/其中2有效；独立原事件时间重建通过，但原代码谱系join未独立重做。父质量/剩余时间/选择存活混杂，不是时间因果效应、最优阈值或新方法；proposal_opportunities_crosscheck及admission-timing-independent回执。
- 这3次增益：去噪.000645643343539986，Aerial.00009086875878627776/.0002325171180705965（父AUC>.9997）；不能只数正号就声称值得成本。18412新metric的新父改善3次均首重复，第二重复未复现；30分钟与上述17分钟不合并比较。
- 输入诊断V1误把Analyze提示也要求含父代码，V2按operator角色分离后247/247返回Improve均含完整父代码；旧诊断保留并明确废除其“父代码缺失”解释，不改原批/原门。prompt_contract_crosscheck_20261017.json。
- quota修复另在新CPU目录跑生产门实际main，10/10通过，0GPU/模型/kernel；只读依赖原19004，不重开原readout。quota-gate-main-20261017.safe.json；线上借用仍未验证。
- 另补两条件各8进程真实安装后的MCTS._analyze许可竞争：峰值4/4、借用0/4、16请求全部释放，独立Node逐事件重建。仅阻塞model-body stub、非真实模型服务；quota-multiprocess-20261017.safe.json。与单次selector/执行信号测试覆盖不同，不重复旧绿色测试冒充进展。
- 对195次准入进一步分时：76新父自身许可等待median .015124320983886719s、p90 12.740118503570557s，只有13次>1s；54次完成代码生成median108.86853349208832s。原始时间读取+独立代数/全分母核验通过，非第二次原始提取。结合18807可借用等待主要为Debug/Analyze，只能提出“上游更早闭合→父更早可用”的待验证路径，不称删除等待能节省这些时间。opportunity-latency及opportunity_latency_crosscheck_20261017。
- 未解8返回另用精确child hash→parent_used→admitted串联：3个无效可定位Improve，2个有效仍未解；不靠时间邻近猜Debug父链，不覆盖原表或补失败。unresolved-parent-events-20261017.safe.json。
- 18807上游发布进一步收窄：78Analyze、107生成请求、74生成→发布有精确journal角色支持；37有效发布/13新best。新best的Analyze仅2次可借用等待（.6892881393432617/.05634474754333496s），Debug新best仅1次9.184827327728271s。长Debug等待主要无效92.26139163970947/未联结211.08816409111023请求秒；未知不能记失败，提前救活尚未被实测。quota-feedback-links-independent-20261017.json；降低quota预期，原资格门/一次限定投入不变。

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
| 共享FIFO→每卡双许可：18807 | 32完整，38重评分/独立统计/12传输SHA通过；去噪best差+0.002312806537356958/−0.004900952505611393，Aerial一正一负；两处理池等待近零 | 停该cap2配方，不启动条件新seed确认；colocation_18807_closed。不是共置普遍无效 |
| 2+4容量与原factory：17571/17576 | 固定程序执行/隔离已通过 | 不重复G0；容量不是新方法收益 |
| 固定代码负载机制：18812 | 8/8完整，两程序共置step少33.3%/34.1%，两次评分均较独占差且均值差超各臂repeat span；8重评分/独立统计通过 | 过事前16执行排序扩展门；已知DEV/2重复，不是显著性或E2E。clock_contention_18812_closed |
| 同任务候选排序：18819 | 16/16有效，Denoise两程序独占/共置优劣两次反转、跨重复区间分开；Aerial区间重叠 | 过333c5662事前新来源确认门；clock_rank_18819_closed，3618GPU秒；不是E2E/显著性 |
| 新来源排序确认：18845 | 16wrapper闭合/11有效；4去噪共置输出超时、1独占内核未就绪。设施停止门漏判后多执行index12 | 确认门false且有协议偏离；clock_rank_confirmation_18845_closed，3273GPU秒；不补跑/改门，不说排序反转不存在 |
| 固定四程序搭档干预：18859 | 同任务/跨任务匹配ABBA16次已冻结，因获卡时不足55分钟窗口，0worker/0分，1GPU秒 | 未执行，不是方法反证；clock_pairing_18859_not_started.json。不重开，未来也不能将已知程序探索冒充新来源/E2E |
| 跨节点：17577–17580 | 空命令也派发失败，独立于模型/镜像 | 管理员问题；本轮继续已通同节点2+4 |

## 更早相邻路线（索引，不恢复授权）

详细数值/原完整结论保存在Git246e66a56151ebfb7b74b5808eeeec82b9de0d8c的本文件；仅命中机制时取对应行，不每次全读。

| ID / 机制 | 已试边界与当前裁决 | 证据入口 |
|---|---|---|
| R1 历史修复检索/经验迁移 | 相关经验未优于无经验/随机；有未知端点，不称全失败。停单步配方 | FORETS_REPAIR_TRANSFER_RESULTS_20260913.md |
| R2 定向事实/analyzer反馈 | 人工规则有局部正控，自动额外反馈未稳定胜强参照 | reports/研究复盘与方向重定义_20261002.md |
| R3 局部编辑/改动拆分/片段回收 | 已查85修改；可编译不等于执行收益，不换名重开AST拆分 | 上述Git旧R3；历史0L410/401 |
| R4 状态缓存×反馈 | 15272完整8条均保留起点；有操作价值，无新终分收益 | results/state_feedback_pizza_20261002 |
| R5 残差/错误样例驱动 | 15282未获改善候选，停当前配方 | results/public_examples_20261003 |
| R6 自动方案/具体规格/主动取证 | 人工规格恢复已知正控，自动方案无确认；来源失败是未知，不算方法反证 | results/opportunity_information_20261003 |
| R7 可执行诊断/校正报告 | 15706局部审计信号；15829识别对象混杂；15950校正未稳定胜原报告 | results/diagnostic_information_20261004/closed |
| R8 edit-gain图/预测修改收益/迁移 | M-DESIGN直接近邻；旧68维不可重调追正，不称首创 | 上述Git旧R8；历史0CU |
| R9 现成LoRA/角色分工 | 16307无完整质量配对；16309小范围误否决分析非E2E | 上述Git旧R9；当前方向历史 |
| R10 代码critic/scaling | 有探索性任务内信号，干净scaling/稳定搜索收益未确认；学长贡献不冒领 | 10/2复盘、9/20报告 |
| R11 想法与实现分离/重做代码 | 16357来源失败；16370不完整，完整块未胜普通续改/HPO；不补seed，不否定所有重实现 | results/implementation_reset_v2_20261005 |
| R12 调参后结构机会/反馈单提案 | 16395有限网格有已知结构正控；16403反馈单提案未胜普通/HPO，部分端点缺失 | results/structural_agent_20261005及supplement-v1.json |
| R13 参数继承/恢复父值/四格交互 | 16538唯一严格挽救是已知日期特征例；另有恢复更差，不补边/seed | results/collateral_factorial_20261006 |

## 近邻边界：方法不能靠换名字获得新颖性

- SchedMate已有源码/历史/日志语义、部分免profile、干扰撤销及故障恢复；新调度必须比较合理廉价/语义参照。
  https://arxiv.org/html/2510.03334
- Agentic CPU-GPU Scheduling已有运行监测/换位复测来纠正静态资源先验（10/17读§2–4.4）：四工具DAG、CPU/GPU/排队放置、13构造场景，目标为时延；不等同动态生成MLE程序的终分确认。已有邻居，不能把“LLM+运行反馈调度”称首创，也不据此启用CPU回退。https://arxiv.org/html/2607.22242
- SpecBox已有流式意图预热、跨步预取、缓存与传输解耦（10/17核§2–3/5.1–5.2）；Latency-Aware Orchestration已有图依赖预测、共同仲裁、模型生命周期/放置（核§3.3–3.5）。阶段重叠/联合调度本身不是空白；不推断它们已解决本项目终分问题，也未复现。
  https://arxiv.org/html/2607.23933 / https://arxiv.org/html/2609.03335
- HyperSched已优化固定资源/截止时间下最终最好精度，假设中间训练进度、可checkpoint/恢复及共同扩展规律；不能把“质量而非吞吐”称新颖。18812只检验黑盒程序墙钟自停时，负载是否改变同源码反馈；此差别尚非方法贡献。
  https://arxiv.org/html/2001.02338 （2026-10-16核§3.1.1、§4；不恢复ASHA/多保真旧线）
- Winning by Peeking已有机器争用改变AutoML比较/有限墙钟内trial数；Mosaic已有kernel干扰准入；RTCSA2020已有mandatory/optional质量调度。不能把“争用改变排序”或“质量感知”本身称首创；原文阅读范围见clock_scheduling_neighbors_20261016.json。
- MARS已有session准入、续轮优先、timeout/任务完成分析；我方执行许可不同不构成创新。
  https://arxiv.org/html/2604.26963v1
- 注意另一个同名MARS（Modular Agent with Reflective Search，ICML2026，非上一行调度MARS）：§4.4已有历史min-max分数×执行时间比惩罚，§4.2–4.3已有模块化构造/跨分支经验；“收益/成本搜树”不新。24h/A100/Gemini设置不与我方17min直接拼数字。本轮核§3–6.1/附录C，未复现。https://arxiv.org/html/2602.02660v1 / https://proceedings.mlr.press/v306/chen26r.html
- Inference-Time Budget Control for LLM Search Agents（核§3–4.1、5.4–6）已有剩余预算、动作成本和固定价值代理控制，任务为搜索问答；不能把“价值/成本+余时门”单独称创新，也不从任务不同推出我方已填补其空白。https://arxiv.org/html/2605.05701v1
- Scepsy/PASTE/BAVT/ZEBRA/PeakBench等限制资源分配/端到端服务宽主张；详见pooling_research_boundary_20261015.json。
- Synergy/TGS/Salus/ElastiCo/DetShare/Pollux覆盖互补共置；GPU驻留PID、host optimizer包络不等于kernel并行。
- CostAda v4已用global-best收益/成本分配与预算预留；旧我方简化参照不是完整复现。
  https://arxiv.org/html/2607.26828v4
- WU-UCT/P-UCT/PLAyBOOK已有pending处理；FlashEvolve已有过时工作/反思重基/异步流控。
  https://arxiv.org/html/1810.11755v3 / https://proceedings.mlr.press/v97/alvi19a.html / https://arxiv.org/html/2605.08520v1
- CoT-retry已有先快写、失败后推理；Ares/LASER/InfraMind已有按历史或负载分配推理预算。
  https://arxiv.org/html/2410.08105v1 / https://arxiv.org/html/2603.07915v1
- When Agents Slow Down已有best-so-far/token及session分配；10/17核全文§6–7及附录E：拐点指导等额多会话，假设独立轨迹/共同Elo尺度，任务级拐点仍需测量。Polyomino正信号不能泛化到所有任务；MLS-Bench附录明确1/2/3会话统计不可区分。其前缀分析依赖agent不见总预算，我方显式墙钟预算轨迹不能照搬截断当反事实。不是我们的新方法，也不据此恢复旧停止/多保真线。
  https://arxiv.org/abs/2609.15309
- On the Clock（10/7提交，10/17读§1–5及MLE动作时长附录）已有剩余时间/生成开销提示与clamp/refuse；守时改善不保证MLE终分。使用OpenCode及不同任务/模型，表2质量条件于有效且及时子集，不与我方全分母warm fallback直接比较；不能把“提醒剩余预算”或“吞吐≠质量”当创新，不引入其RL。https://arxiv.org/html/2610.10833v1
- On Time and Within Budget/MCPP（10/17核§1–3.1）已有固定预给DAG的模型/并发组合与截止成功率规划；动态MLE程序和连续成绩是场景差别，尚非方法贡献。https://arxiv.org/html/2605.06110v1
- SwarmX（10/17核§2.2、3.1–3.3）已有调用结构/分布时延预测及路由扩缩容；“预测反馈链后调度”本身不足以立新颖性，本轮未复现其完整实验。https://arxiv.org/html/2606.21401v1
- Frontis-MA1/OpenMLE（10/17核§4–6.1、附录C）已有Draft/Improve/Debug/Crossover、父收益/成本信息、经验板和异步多GPU搜索；EvoMax还改变其他组件，不能拿其12h结果作我方17min纯调度参照。不引入底座训练。https://arxiv.org/html/2607.28568v1
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
