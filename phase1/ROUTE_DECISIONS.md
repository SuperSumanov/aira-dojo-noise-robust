# 路线与机制索引：先查旧证据，再提新方向

2026-10-17收束。方向/授权只读CURRENT_DIRECTION，现场只读CONTEXT_HANDOFF_CURRENT。
本次压缩前全文在Git b1603f953f1e20e8080e075ec2ebb6e1a4cc802f:phase1/ROUTE_DECISIONS.md。
旧细节在6c47086a603b4c7afcc25a3e80f9d5648c3bee63；更早R1–13在246e66a56151ebfb7b74b5808eeeec82b9de0d8c。
原结果/撤回/限制均留存；按机制检索历史，不每次全读。停止配方≠证明普遍无效。

## R14：同预算终分，非吞吐主张

当前只保留一次quota强基线资格问题；矩阵、原门、边界见CURRENT_DIRECTION。
证据根目录phase1/sandbox_scheduling；表内目录与固定批次可直接检索。

| 机制 / 批次 | 证据与结论 | 恢复限制 |
|---|---|---|
|固定绑卡→共享FIFO18468/18510/18673|资格/信号接线/容器入口失败，零或不完整搜索|非方法反证，旧批封存|
|18770固定/共享FIFO|32完整、29评分，效果反序不稳定|停该配方；pooling_18770_closed|
|18807共享单/双许可|32完整、38评分，等待降但终分门false|停cap2；colocation_18807_closed|
|18812固定两程序|8有效，共置steps少且分数更差|仅已知DEV局部；clock_contention_18812_closed|
|18819固定四程序|16有效，去噪两次严格排序反转；Aerial区间重叠|新来源/E2E未证；clock_rank_18819_closed|
|18845新来源排序|16wrapper/11有效；4共置超时、1内核未就绪，停止门漏判|确认false，不救完整个例；clock_rank_confirmation_18845_closed|
|18859固定搭档|获卡时窗口不足，0worker/分，1GPU秒|未执行，不是反证；clock_pairing_18859_not_started.json|
|18987独立固定搭档|4wrapper/3有效，去噪原300s超时，733GPU秒|无完整比较，条件diverse不submit|
|18997静态任务准入|32完整、35评分；仅Aerial可共置，去噪两臂都独占；终分false|停止；selective_18997_closed|
|19004跨任务生成许可|32闭合但深层hook绕过，借用0；读出失败|无效干预不是方法负结果；generation_quota_19004_closed|
|18269 score step30|32完整，去噪两次best/median更差，Aerial一正一负|停该配方；weight_confirmation_18269_closed|
|18412 metric step30|48完整，两重复去噪未胜旧fast/medium|停配方，非纯reward消融；metric_deployment_18412_closed|
|18253新旧×effort|32完整但首提示漂移；质量也false|不归一化救门；weight_effort_18253_closed|
|18161 xhigh|24完整，4个代码返回均32768截断，无新有效解|预算条件失败非普遍无能力；long_effort_v1_closed|
|17740角色反馈effort|48完整，两次胜medium，对fast一负一正|不补seed/cap；feedback_effort_v2_closed|
|17681同父硬预约|不完整，完整首重复未过门；同父重叠有3次改善|停硬等待；feedback_parent_v1_closed|
|17675生成前联合资源项|48完整，资源项改变选择0次，质量false|增量未识别；generation_joint_v5_closed|
|17656/17670请求时限|生成/有效覆盖局部提升，终分确认失败|弱240s保护不是创新；image_deadline*_closed|
|17366/17368同卡共置|神经fixture局部吞吐，真实live质量未过门|非跨任务质量确认；neural_extension/live_twochild|
|17571/17576原factory容量|2+4固定程序/隔离已通|不重复G0，不当方法收益|
|17577–17580跨节点|空命令也失败，独立于模型/镜像|管理员事项；可用同节点2+4继续|

## 关键分析：仅保留能改变下一步的结论

- 18819严重干扰首32/128host steps速率已可见；普通监测未被证明无效，更没超过SchedMate。Aerial少steps反可更好，保工作量≠保质量。
- 18807真实20准入均candidate+candidate，仅3双侧CUDA终端trace；缺失与失败相关，不能从缺测声称廉价保护不可能。未核MPS。
- 18997独立AUC/RMSE35/35一致，maxerror1.1102230246251565e-16；全76返回及时，1未匹配评分比best差，未发现晚到好解/最终选择补救。
- 18997同首prompt/seed16对仅3对同代码（去噪0/8）；32匹配nativejournal。CPU4配置/12末端调用seed正确，不是实际HTTP抓包。
- vLLM官方默认不保证在线复现；仅支持服务非确定性这个备选解释，未定位其为本批原因。不临时换镜像/开关救比较。https://docs.vllm.ai/en/stable/usage/reproducibility/ / https://docs.vllm.ai/en/stable/features/batch_invariance/
- 三有效调度批96条/229返回/101有效，24任务池11池首尝试后仍改善；Debug产32有效。43新父后代返回3好/11差/29无效，但有截断，不能据此断言重启胜迭代。
- 全195Improve准入中76用新父：余时<300/300–600/600–900s为40/26/10；已联结3改善均最后组。父质量/存活/余时混杂，非因果阈值。
- 8谱系未解含2有效。精确child hash补查只解决3无效，2有效仍未知。原始时间独立重建，原谱系join未独立重提取。
- 3增益为去噪.000645643343539986、Aerial.00009086875878627776/.0002325171180705965；后者父AUC>.9997，不只数正号宣称值得成本。
- metric18412新权重3次新父改善仅首重复；30min与17min不混池比较。247返回Improve均含完整父代码，V1混入Analyze的错误解释已撤回。
- 新父自身许可wait median .015124320983886719s，54次生成完成median108.86853349208832s；晚到不是主要卡在该次申请。
- 18807每任务2许可有总active<4且排队的区间；服务采样Running≤4/Waiting0/KV≤13.3%不证明硬件空闲。借用是strong baseline，不是新算法。
- 18807发布链78Analyze/107生成：37有效发布/13新best；新best Analyze仅2次可借用wait，均<1s；Debug新best受阻仅1次9.184827327728271s。
- 长Debug借用wait主要无效92.26139163970947/未联结211.08816409111023请求秒；提前可否救活未知，不能用原结局当反事实。quota预期下降，不凭总等待扩跑。
- 19004修复过三层CPU门：selector、真实hook/事务、真实wrapper多进程竞争；8进程/条件，峰值4/4、借用0/4、全释放。模型body是stub，线上干预/终分未验。
- 上述入口：proposal_opportunities_crosscheck、admission-timing-independent、prompt_contract_crosscheck、opportunity_latency_crosscheck、quota-feedback-links-independent、quota-multiprocess-independent（均20261017）。精确SHA/长限制在原件及b1603f95。
- 不从无效19004分数追选策略，不重复原读出；唯一新root quota-v2/19118原32矩阵/原门/≤10GPUh。新三小时窗口仅此GPU批。
- 共享服务边界只读核验：18807/18997/19004共1185数值遥测，12个尾部间隔21采样均Running/Waiting=0；未观测到跨池持续忙碌。独立哈希/代数通过，非第二次原日志提取；不证明连续空闲/取消/缓存中性，不救19004。service-boundaries-independent-20261017.json。
- 已有输出互补性：18770/18807/18997全96条/24池，warm和及时有效CSV按字节去重；两向整图像重划分，经典greedy20去噪10/12双向正，较差方向median .00023015673995906843，仅2/12双向≥.001；Aerial2/12。全均值去噪0/12。不是新holdout/独立重复/同预算收益；extraCPU单记。独立Node只核代数，不是原始预测复提取。output_complementarity_20261017。
- 后续独立原始12去噪池+Gram实现复算maxdiff2.4424906541753444e-14；fit-only仿射校准并选单模型12/12双向正，greedy胜校准仅5/12。原“集成10/12”不可当胜廉价强参照；勿把校准/集成改名成新方法。校准后结构优化与R12/LLaMEA-HPO等旧机制重叠，不能仅据这一旧DEV诊断自动恢复路线。
- 事后分解：12池首warm预测SHA/原分数均同一，校准库相对校准warm7/12双向增益≥.001；不是“全部搜索增益只是校准”。该描述不证明新调度/模型收益，不改变19118原门。

## R1–13：历史机制，不自动恢复

| ID / 机制 | 已试边界 | 证据入口 |
|---|---|---|
|R1历史修复检索|未胜无经验/随机；有未知端点，不称全失败|FORETS_REPAIR_TRANSFER_RESULTS_20260913.md|
|R2定向事实/analyzer|人工规则局部正控，自动反馈未稳定胜强参照|reports/研究复盘与方向重定义_20261002.md|
|R3局部编辑/片段回收|已查85修改；可编译≠收益|历史R3/0L410/401|
|R4状态缓存×反馈|15272完整8条保留起点，无新终分收益|results/state_feedback_pizza_20261002|
|R5残差/错误样例|15282无改善候选|results/public_examples_20261003|
|R6主动取证/具体规格|人工规格恢复正控，自动无确认；来源失败非反证|results/opportunity_information_20261003|
|R7可执行诊断|15706局部信号；15829混杂；15950未稳定胜原报告|results/diagnostic_information_20261004/closed|
|R8修改收益预测|M-DESIGN近邻；旧68维不可重调追正|历史R8/0CU|
|R9 LoRA/角色分工|16307无完整质量配对；16309误否决分析非E2E|历史R9|
|R10 critic/scaling|任务内探索信号，干净scaling/搜索收益未确认|10/2复盘、9/20报告；不冒领学长贡献|
|R11想法/实现分离|16357来源失败；16370不完整，完整块未胜普通/HPO|results/implementation_reset_v2_20261005|
|R12调参后结构机会|16395已知正控；16403反馈未胜普通/HPO，有缺失|results/structural_agent_20261005|
|R13恢复父值/交互|16538严格挽救仅已知日期特征例，另有恢复更差|results/collateral_factorial_20261006|

## 直接近邻：不能靠换名字获得新颖性

- SchedMate源码/历史/日志语义、免profile/部分信息、干扰撤销/恢复均已有；目标JCT，不是本项目终分复现。https://arxiv.org/html/2510.03334
- HyperSched已优化截止前最好精度，假设中间进度、checkpoint/恢复及共同扩展规律；“质量非吞吐”不是新颖。核§3.1.1/4。https://arxiv.org/html/2001.02338
- Winning by Peeking已有机器争用改变AutoML比较/墙钟内trial数；Mosaic已有kernel干扰准入；RTCSA2020已有mandatory/optional质量调度。原文见clock_scheduling_neighbors_20261016.json。
- 调度MARS已有session准入、续轮优先、timeout分析。https://arxiv.org/html/2604.26963v1
- 另一MARS（Modular Agent with Reflective Search，ICML2026）§4.4已有归一化历史分×运行时惩罚、模块构造/跨分支记忆。补核最新版v3§4.4/6/A：因果lesson审查主要LLM+少量人工，不等于干预证明。24h/A100不与17min27B拼数字。https://arxiv.org/html/2602.02660v3 / https://proceedings.mlr.press/v306/chen26r.html
- Agentic CPU-GPU Scheduling有运行监测/换位复测；13构造场景、时延目标，非动态MLE终分；不据此CPU回退。核§2–4.4。https://arxiv.org/html/2607.22242
- SpecBox有流式意图预热/跨步预取；Latency-Aware Orchestration有依赖预测/仲裁/生命周期。阶段重叠本身非空白，未复现。https://arxiv.org/html/2607.23933 / https://arxiv.org/html/2609.03335
- Inference-Time Budget Control已有余预算、成本、价值代理和保守收尾；搜索问答场景，不由场景差别推出新颖。核§3–4.1/5.4–6。https://arxiv.org/html/2605.05701v1
- When Agents Slow Down已有best-so-far/token和session分配；MLS-Bench会话数统计不可区分。前缀分析假设agent不见总预算，我方不能照搬截断当反事实。核§6–7/附录E。https://arxiv.org/abs/2609.15309
- On the Clock已有时钟提示/clamp/refuse；守时不保证MLE终分，其质量表条件于及时有效子集，不与我方全分母warm fallback拼数；不引入RL。核§1–5/MLE附录。https://arxiv.org/html/2610.10833v1
- MCPP已有固定DAG模型/并发/截止成功率规划；SwarmX已有调用结构/时延预测/路由扩缩容。“反馈链调度”本身不足。https://arxiv.org/html/2605.06110v1 / https://arxiv.org/html/2606.21401v1
- OpenMLE已有Draft/Improve/Debug/Crossover、父收益/成本、经验板、异步多GPU；12h多组件改动非我方纯调度基线；不引入底座训练。核§4–6.1/附录C。https://arxiv.org/html/2607.28568v1
- CostAda v4有global-best收益/成本和预算预留；旧简化参照非完整复现。https://arxiv.org/html/2607.26828v4
- WU-UCT/P-UCT/PLAyBOOK已有pending处理；FlashEvolve有过时工作/反思重基/异步流控。https://arxiv.org/html/1810.11755v3 / https://proceedings.mlr.press/v97/alvi19a.html / https://arxiv.org/html/2605.08520v1
- CoT-retry已有失败后推理；Ares/LASER/InfraMind已有推理预算分配。https://arxiv.org/html/2410.08105v1 / https://arxiv.org/html/2603.07915v1
- Synergy/TGS/Salus/ElastiCo/DetShare/Pollux覆盖互补共置；Scepsy/PASTE/BAVT/ZEBRA/PeakBench限制资源分配宽主张；细节pooling_research_boundary_20261015.json。
- TTT-Discover/AREX-2/Guidance-TTT覆盖任务自举训练；M-DESIGN/REHEARSE覆盖收益预测/检索；MLE-STAR/PatchFusion覆盖精修/组合。
- MLE-STAR §3.3已有利用次优候选互补性及集成计划；DivBO已有性能/多样性代理与联合acquisition；Q(D)O-ES已有质量多样性集成选择且提醒过拟合。“为集成搜索互补候选”不是空白。https://arxiv.org/html/2506.15692v3 / https://arxiv.org/abs/2302.03255 / https://proceedings.mlr.press/v224/purucker23b.html
- Centaur/LLaMEA-HPO/TIDE/HT-AA覆盖结构×数值分工；GEVO已有编辑交互；GOME/Iris/AgentX/NSR-Boost/Beneath the Diff/RIPPLE覆盖反馈/残差/重复。原文与范围在旧Git。
- 未读/未复现不说不存在；新颖性定稿重核原文。场景不同、旧机制新名字或局部阳性都不自动成为方法贡献。

## 新提案只需四项

1. 对应旧路线与原结果；未在当前窗口看到不等于没做过。
2. 实质改变哪个决策、信息或行动，而非模型/seed/名字微调。
3. 新事实为何值得测；观测重放不是新策略实测。
4. 直接近邻、强基线、全成本和可否证门；无独特性则按参照资格报告。

先缩小未知，再做一个有辨识力的最小实验；不同时制造多个主线，不另建审批流水线。
