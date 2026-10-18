# 路线与机制索引：先查旧证据，再提新方向

2026-10-18 R15停止；源页面机会检查19344完整而原门false，停止该特征配方。方向/授权只读CURRENT_DIRECTION，现场只读CONTEXT_HANDOFF_CURRENT。
本次压缩前全文在Git b1603f953f1e20e8080e075ec2ebb6e1a4cc802f:phase1/ROUTE_DECISIONS.md。
旧细节在6c47086a603b4c7afcc25a3e80f9d5648c3bee63；更早R1–13在246e66a56151ebfb7b74b5808eeeec82b9de0d8c。
原结果/撤回/限制均留存；按机制检索历史，不每次全读。停止配方≠证明普遍无效。

## R14：同预算终分，非吞吐主张

quota已停止；矩阵、原门、边界见CURRENT_DIRECTION。不补救旧配方。
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
|19136修复配额|32启动31完整，借用0/11/9/0、峰值4；29676GPU秒；完整去噪差+.00790502349919136/−.0006739912365923625|原门false/incomplete，停止；generation_quota_19136_closed；不补缺失/改门/继续配方|
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
- 不从无效19004分数追选策略，不重复原读出；唯一实际quota批原32矩阵/原门/≤10GPUh。19118从未分配/执行已取消；v3只修排队有效期，汇报时刻不再误作启动截止，所有科学字段保持。
- 共享服务边界只读核验：18807/18997/19004共1185数值遥测，12个尾部间隔21采样均Running/Waiting=0；未观测到跨池持续忙碌。独立哈希/代数通过，非第二次原日志提取；不证明连续空闲/取消/缓存中性，不救19004。service-boundaries-independent-20261017.json。
- 已有输出互补性：18770/18807/18997全96条/24池，warm和及时有效CSV按字节去重；两向整图像重划分，经典greedy20去噪10/12双向正，较差方向median .00023015673995906843，仅2/12双向≥.001；Aerial2/12。全均值去噪0/12。不是新holdout/独立重复/同预算收益；extraCPU单记。独立Node只核代数，不是原始预测复提取。output_complementarity_20261017。
- 后续独立原始12去噪池+Gram实现复算maxdiff2.4424906541753444e-14；fit-only仿射校准并选单模型12/12双向正，greedy胜校准仅5/12。均离线访问fit标签，不能把校准当agent只见分数契约内的线上强基线；将来需公开train的OOF或有全成本的纯分数查询协议。勿把校准/集成改名成新方法；校准后结构优化与R12/LLaMEA-HPO等旧机制重叠，不自动恢复。
- 事后分解：12池首warm预测SHA/原分数均同一，校准库相对校准warm7/12双向增益≥.001；不是“全部搜索增益只是校准”。该描述不证明新调度/模型收益，不改变19118原门。
- 信息契约可行性仅有代数：令L0/L1/Lp是0/1/原预测的MSE，则E[y]=(1+L0−L1)/2、E[py]=(E[p²]+L0−Lp)/2；可由预测矩和这三个标量求OLS仿射系数（原p已评分时另需2查询）。3个纯合成例与直接OLS最大系数差1.5543122344752192e-15。
- 上式是已知二次损失恒等式，不是创新/真实接口验证；查询精度、常量预测可受理性、全查询/后处理成本、公开train-OOF及最终独立检验均未资格。没有在真实评分接口发常量预测，没有当前批次接线/额外GPU；不能因代数可行就把旧离线校准称线上收益。
- 更小信息的经典参照：相同样本/权重上的MSE单模型分数L_i与无标签预测差异D_ij即可确定凸组合损失：L(w)=sum(w_i L_i)−0.5 sum(w_i w_j D_ij)，sum(w)=1、w>=0；RMSE先平方，不能直接平均RMSE，也不能用于AUC/异样本评分。只需原分数，不需额外常量查询；是否可取全精度分数/预测及后处理成本仍须独立协议，不接入19136。
- 这是Krogh–Vedelsby NIPS1994的ambiguity decomposition/§4式14，不是新方法；纯合成4例二候选最优权重与直接平方误差最大差1.5449880957918438e-18，没有真实数据/接口查询。它只刻画已观测预测凸包，不能上界未生成候选的价值；同DEV优化不保证泛化，不能用于救旧质量门。原文https://papers.nips.cc/paper_files/paper/1994/hash/b8c37e33defde51cf91e1e03e51657da-Abstract.html 。
- 19136闭合：index26最后partitioned池Aerial在kernel readiness guard退出；四执行池与服务GPU全清理，底层ready失败原因未归因。原冻结读出33重评分、31/32完整，独立四池重放确认quota已生效；全16去噪结果仍反向一次，首轮Aerial也退。global质量比较无效，不删失败条作确认；明确停止配方，不把诊断脚本缺live_status依赖的补齐误写为实验修复/补跑。

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

- 10/18新增事实：旧去噪92train/36清页，11DEV参考全在train；四个只用public的模板检索均RMSE0，独立复算通过。旧提示强制CUDA，不能叫模板胜旧公平臂，或把CNN集中称生成器自由搜索缺陷。新grouped-public参照只问去除捷径后是否有候选空间，非创新/旧R12改名。
- Noise-Transfer2Clean已有背景噪声迁移，Noise-Space Domain Adaptation已有residual swap，未选择简单噪声转移增强为创新。https://pmc.ncbi.nlm.nih.gov/articles/PMC8963287/ / https://arxiv.org/abs/2406.18516
- CCTS用高低分概念对比引导父选择/编辑（§4），MLE-InsightForge组装任务/领域/改进经验并控制来源（§2–4）；不把“从差异提炼经验/概念”称空白。https://arxiv.org/html/2602.03132 / https://arxiv.org/html/2610.04927v1
- 10/18核CoMind v3附录J：去噪案例已使用公开pixel-patch/多尺度滤波特征、RF/XGBoost方案及社区讨论；换经典模型或给生成器这些知识不是新颖性。当前两种LightGBM只作机会参照，非复现其资源设置。https://arxiv.org/html/2506.20640v3
- Silent Failures §4.2–4.3已讨论高分与泄漏/方法错误并存，显式提示和专家差距；MLToolBench已有诊断观察干预，POPPER已有主动证伪。故不把本次重复页发现扩张成首个完整性审计/通用诊断方法；其发现只经本项目数据独立验证。https://arxiv.org/html/2610.14115 / https://arxiv.org/html/2609.36679 / https://proceedings.mlr.press/v267/huang25n.html
- 19344：2清页隔离fold×2seed×4程序，16合格/独立重评分16，四格CNN0<CNN1<multiscale<patch（RMSE）；多尺度未胜任一CNN，原机会门false。2423GPU秒，含19343失败总2755；不追加特征/调参/seed救门。旧CNN在新分组仍胜这三参照是资产事实，非新生成机制或跨任务确认；page_headroom_19344_closed。

### R15：输入身份寻址的数据随机流（已闭合停止，不预认创新）

- 相比R14改资源排队，本轮改训练数据比较的随机耦合；不更新模型、不复用权重，不是R4缓存。2任务×2已知程序的固定库，24选解+8共同部署执行，≤4GPUh。
- 101有效返回均见DataLoader且explicit-generator为0（有重复、仅固定AST拼写）；不是运行时噪声证明。CPU合成确认global与sampler/addressed的机制区别，尚无真实效果。
- 原代码/图像/300s/每程序2CPU+1GPU一致；global/sampler/addressed反序两选解seed。先封存选解再看新seed同库部署；完整分母及两个强参照，详CURRENT_DIRECTION。
- CRN经典：Pearce等KG-CRN已联合选择配置和seed、利用噪声相关性作昂贵优化；不是本项目首创。https://arxiv.org/html/1910.09259
- 事件/个体同步随机流已有医学模拟先例，不能仅换成样本/epoch称新方法。https://pmc.ncbi.nlm.nih.gov/articles/PMC2761656/
- 10/18香港01:11补核直接近邻：Buffalo/Pearson/Klein, Realizing Common Random Numbers（arXiv2603.11084，3/11），已读§2.3、3、4、5：stable event identity→hash/counter RNG、条件控制流不再错位、各event-class独立stream参照均已有。故R15不是新的随机数方法；只可能作为既有方法在自由MLE代码选解中的适用性检验。其事件身份需模型假设，我方raw-input+epoch也不是任意代码语义对齐证明。https://arxiv.org/html/2603.11084v1
- MetaFlow原文§4.2.2也用共享problem instances的CRN降低组内比较噪声（训练workflow policy，不是我方数据增强耦合；不引入底座训练），不能泛称“agent比较+CRN”创新。https://arxiv.org/html/2606.30704v1 。另只读核过旧tools/regrade_worker.py：原噪声实验确实重执行代码，不能误写为仅重评同一预测，更不能将重跑波动称本轮首次发现；未读取旧label/outcome文件。
- PyTorch官方显式generator/worker_init_fn是便宜强参照；此处num_workers=0。https://docs.pytorch.org/docs/stable/notes/randomness.html
- Net2Net/LEMONADE已有权重继承，HELIX已有工作流缓存；因此本轮未选择泛化“从父程序状态继续训练”作为新主张。https://arxiv.org/abs/1511.05641 / https://arxiv.org/abs/1804.09081 / https://arxiv.org/abs/1812.05762
- 潜在贡献必须另证自由代码修改下可自动对齐、胜标准隔离随机源及真实搜索终分；本小库试验不可能单独满足。无选解变化/不胜两强参照则停，不增加调度补丁。
- 19245仅首global块启动即盲态中止：轮转设备导致program×arm混杂，未读分数；不是CRN效果反证。独立v2固定每程序设备，原终分门/矩阵不变；unused loader单记。窗口含中止≤5GPUh，不再新增修复批。
- 事前解释边界：二候选库若global/sampler选不同，addressed必与其中一个相同，不可能严格胜两者；不因此临时扩库。通过也只筛资格：尚需“采样+增强各自独立stream”更强参照，才能区分普通随机源隔离与按样本寻址的价值；未执行、不由此救失败。
- 等执行数的高斯反例表明，降低排序差异噪声可提高所选程序新运行的均值，却降低已保留产物的期望max；假定随机性是产物真实质量差异，不是验证测量误差。纯CPU代数不构成实际MLE收益。MaxUCB已在AutoML讨论max而非mean（§1–2），故此目标区别不是新颖性，只用于避免错优化。https://arxiv.org/html/2505.05226v2
- 19249完整32/合格32、32重评分一致；三臂两任务选相同程序，新seed全部差0且都选中两程序库当次最优，原门false。实际12504GPU秒，含盲态中止总13360GPU秒；独立Node/10SHA和12顺序结构行复算通过。rng_selection_19249_closed。
- 次要同4次执行的最佳去噪产物addressed反比global/sampler差.00034283073454105875/.00031865843181138123，逐seed效果不稳；Aerial对sampler也一正一负。不能用局部正号救门；停止R15，不补seed/换库/添加增强stream重跑。仅否决此配方，不证明CRN一般无效。下一切口未确定。

1. 对应旧路线与原结果；未在当前窗口看到不等于没做过。
2. 实质改变哪个决策、信息或行动，而非模型/seed/名字微调。
3. 新事实为何值得测；观测重放不是新策略实测。
4. 直接近邻、强基线、全成本和可否证门；无独特性则按参照资格报告。

先缩小未知，再做一个有辨识力的最小实验；不同时制造多个主线，不另建审批流水线。
