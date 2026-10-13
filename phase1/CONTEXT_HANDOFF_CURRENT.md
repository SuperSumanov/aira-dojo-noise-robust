# 当前短交接：恢复先读本文件，不从旧心跳恢复任务

最后核验：2026-10-14 HK06:46；新四格v4 job18253于06:45:29在gpu29实际RUNNING，6卡服务启动中，adapter资格/正式搜索未开始。submit exec78194已exit0；绝不重复submit。18161已闭合，不重跑。
恢复顺序：fetch → CURRENT_DIRECTION → ROUTE_DECISIONS → 本文件 → 必要原始证据。
本次覆盖前的完整交接：Git 72167a42feccaec44f5793c3bc7d2f4e9132d581:phase1/CONTEXT_HANDOFF_CURRENT.md。

## 本轮四格权重×effort（18253）及已闭合18161
- 新授权32条=2任务×4搜索seed×原始/共享训练后权重×fast/medium；1800s/run、1960s/池、2服务+4执行，含启动/验收/失败/清理≤9000s=15GPUh。不训练/API、不自动补跑；每格一池非独立重复。主比较新medium−旧medium，fast为次要。所有格初始历史相同，后续不跨格共享。
- 新adapter已远端完整下载到/research/d7/spc/yzyang4/weight-effort-adapter-20261014-ynf9spm3/accepted_adapter，选Drive 1_GXBwH5jRXTnt-lW_-ur4l0rUPBav2ZK（online_thinking_score/step30）。archiveSHA b6958bb33821a0a1d7e3203bcc6eec18470c0d3e4c0218667ed2452dbf5d0d9e；weightsSHA c7666264904a3490958e46cfbb989a22bc52b9a81c9714631751c7bf8445b61f；configSHA f0a0264f243f57a126a9903499ee48984e660a6bf0ad7b3d351431ce4546198e。992有限BF16张量/rank128；496组形状全部对应（240dense/256int4）。base/revision字段空，不能称相邻日更因果；运行资格在本批9000秒预算内先测，通过才搜索，失败即闭合不重试。
- intake/形状/镜像源码/完整文件哈希检查均完成，不重下。冻结源码commit6b592cb150be38b9b3bd140cd77dd448d96add12，root=/research/d7/spc/yzyang4/scheduling-weight-effort-20261014-v4；18253已分配gpu29六卡，四格同机同3090，未升级镜像。既有真实任务沙箱每次启动已有CUDA算术/namespace门，不增G0。状态工具/tmp/long-effort-20261013-4iRdot/weight_effort_status_20261014.py只读结构；预计闭合HK09:00–09:15，Slurm硬上限09:15:29，未到搜索阶段不称32条开跑。
- v1/v2/v3均仅CPU准备、零GPU/真实模型调用。依次发现我方模型前缀断言漏openai/、测试混计prompt哈希事件、测试未按正式worker设置random.seed而软件包列表被原生shuffle。前两已修；v4只补测试seed，不改原算子。v1尝试重写exclusive plan被拒，保留原件，不再原地改。独立JS读出8合成测试通过；正式首提示必须同哈希，不能跳过门。
- v4前检32配置/24配对、4原生async角色/MCTS请求门通过，首Improve提示同SHA ef71abe51bc72d0d5af91c2a1d75656628838f922066392a04cb23bf8e929263。planSHA cba9bad500a106b8c44f18116c491a1744edb50c3744c7f7ef1f498e45cdbd4f；readerSHA 1f2ae31840a8d72d084fb487058712c581fcdf18abfdf44b296599edbde0c6c5。独立读出verify_weight_effort_20261014.cjs，pins在本地_codex_tmp/weight_effort_pins_20261014.json。仅完整闭合后读分，不中途选权重/模式/样本。
- 用户批准24条=2旧开发任务×4配对seed×fast/medium/xhigh；run1800秒、pool1960秒、2服务+4执行卡，allocation7500秒/12.5GPUh含失败，API/底座训练0。每臂一池，固定medium→xhigh→fast，不声称重复确认，不改旧17740。
- 共同代码输出32768、请求1500秒；Analyze仍medium/8192/600。相同warm父程序/greedy/镜像/数据/任务预算，候选自身执行300秒不延长。新目录/research/d7/spc/yzyang4/scheduling-long-effort-20261013-v1；临时源码/tmp/long-effort-20261013-4iRdot。不存在launch回执时不得说已跑。
- source=49dec91477e7d6dc8cfc1f7e86780a69205d499d；planSHA=cef33dddaf5973d067b8b7c1b415a1f1512e73b6fae5cdb23deb6a3ed410bd00，与18161 launch回执一致；不得重复submit。gpu3同一节点2+4 RTX3090，实际6201秒×6=37206GPU秒=10.335GPUh，低于12.5。
- 实际启动10/13 HK22:34:07、10/14 00:17:28退出0。24均budget_exhausted正常闭合、清理true，三池完整；无失败启动计费项。旧排队估计不再作现场。SSH正常；squeue已移除旧job，按sacct核完成，不能误报监控失败或实验失败。
- 前检六单测、24配置/16跨臂配对、三实际async/MCTS CPU门和镜像/六shard哈希此前均通过。闭合后28外部开发评分重算、12CPU配对、物理GPU/清理/预算检查通过；独立Node 9单测重过，真实矩阵/CSV/统计/成本及五文件传输哈希一致。
- 原quality=false、structural=true、actual_mode=true；去噪池最佳fast/medium/xhigh RMSE=0.01968566134361319/0.016646375501812607/0.04551226514614451。各四条的中位/SD分别0.04551226514614451/0.01291330190126566、0.019070756520558854/0.0022984008422853542、0.04551226514614451/0。xhigh Aerial也停起点，未过门；只一池/臂，不作独立seed显著性。
- 事后机制：fast/medium/xhigh code返回37/29/4，候选返回33/24/4，外部有效12/16/0；xhigh四返回均length/32768，其余五调用success=false且结束elapsed均约1800（四Improve、一Debug），不据此断言1500请求超时。返回调用延迟中位101.70844331290573/192.58446529414505/864.891065380536秒，只含返回且非GPU耗时。xhigh被截断不能推出自然完成长推理无用，不加长救本门。
- medium去噪4/4搜索改善起点、fast1/4，池最佳RMSE相对fast低15.43908425909526%，但只是单池开发探索，不称稳定或新机制；Aerial fast更高且近上限。停止xhigh配方扩大；优先同底座同谱系、事前日期固定的新旧checkpoint同archive对照，不自动恢复模型训练/新router。
- 本地证据sandbox_scheduling/long_effort_v1_closed；远端readout-20261014-v1；summarySHAa1deb9cd0c894521e965edd53f0878a1c8aead5d42b27577b6ca2f46e93cc1be，readerSHA09b873a4496b8239191f2adc03df65f34db6faa7000efb387c6b6c917538b77c，独立结果independent-verification.json。未改冻结GPU源码或原质量门。
- 新源码long_effort_{trial,policy,readout,native_cpu}_20261013.py与test_long_effort_20261013.py。改超时是新批共同改动，不改旧snapshot。finish_reason只记安全枚举；未完成不填造warm分数，完整质量门需胜两常数参照，不用生成数代替终分。

## 本轮用户要求与学长建议
- 用户转述学长建议补xhigh（可至几万长度）；学长当前重点是逐日用上一日轨迹/score训练新policy再采集，未来想用validation/D_search对抗去除score依赖。原话与边界已存ADVISOR_DIRECTIVES Y。
- 学长计划不记为已跑通/满分；我方不更新agent底座的禁令不因此解除。继续R14相关的推理成本/真实质量研究支持，不恢复旧critic/HCE/多保真/score-channel。
- 当前建议：旧/新日期固定checkpoint×fast/medium/xhigh，同最新archive、起点、可见历史、硬件及整池预算；版本效应和effort效应分别在另一轴固定时识别。先验证权重更新是否超出历史积累，能否降低推理成本；这是设计，不是新算法/新收益。
- 不用逐日累计最高分当学习证明：未训练旧模型也应获得同样最佳程序/历史。学长训练默认去掉proposal搜索记忆是明确设计，不先验判错；更需与上下文复用的廉价参照比较。
- 新旧checkpoint事前按日期选，不能用本轮结果挑最好点。训练/采集成本单列，部署收益与摊销后总成本收益分开；保护集未解除，当前仅开发证据，不能称独立test泛化。
- 最终E2E目标仍是同一初始archive下，“训练+搜索”胜“把同等新增总算力用于不训练的强搜索”。六格只是既有checkpoint的部署/机制读出；单程序发现与通用policy收益不能混同，不强加跨任务policy泛化为发现的必要条件。TTT-Discover v2直接覆盖单任务自举宽概念，不能称首次。
- 思路交付的优先顺序：冻结模型补fast/medium/xhigh强参照→日期固定旧/新checkpoint同历史比较→有收益才核整循环回本。同预算终分主读出，事前固定质量门槛的整池成本为辅；未达到按删失记录。只复现已有最佳程序不记新发现；新低effort胜旧xhigh不能单独证明压缩推理机制。
- validation/D_search若参与训练/搜索就不是最终封存集；“不用官方分数训练”和“部署不接收外部分数”不是一个问题。这里只澄清后续设想，不启动score-channel消融或analyzer。

## Git/材料最后观察
- 10/14 fetch成功：公开myfork/phase1-value-critic仍72167a42feccaec44f5793c3bc7d2f4e9132d581，本地HEAD a52d4ea2184c0c955070c530fd6a724fe7aee821含49dec实验及独立reader。学长myfork/dojo-reproduce新8d39164c5b4c2c1c304fc28801e60467e0ad5de5（10/14 HK00:26:32，sync verl），仅src/verl gitlink由08523dd4变51ff1b4c；没有新outcome文件，不能当训练收益。未修改学长分支。
- 四个新增/修改文件credential-shape scan为0后读取；新增use_metric_reward默认false，不证明生产启用。policy outcome最后修改仍13d28830c66a96988c180532495326dc144eb93b（10/9 HK20:15）；没有确认新训练效果。
- overview明确metric=内部验证、metric_info.score=官方评分；reward=1是gold阈值，不等于任务满分。实际日更训练所用字段未确认；同组标准化可抵消正仿射变换，不能仅凭阈值复用认定训练bug。
- selection.training_messages源码默认对draft/improve/crossover strip memory，debug/analysis不改；overview末尾仍有旧相反描述，以固定源码为准，不能据文档猜实际训练产物。
- 实验源码49dec914与独立读出/启动状态a52d4ea2均本地commit、未push；本次闭合证据及短状态另外保留，用户未跟踪报告仍不动。
- 10/13新Drive元数据：checkpoint/qwen3.8-27B-lora-adapter含v2_step665、grpo_v3_step50及online_thinking/grpo_v1_step30三份tar；comparison/1012含Chaii/Champs/Dog/OSIC/TGS五任务档。仅远端各读8MiB归档前缀，均未到配置；未保存/加载权重或读结果，不扩下载。文件名不证明底座兼容、训练日期、单一日更谱系或效果。安全ID/覆盖清单在本地_codex_tmp/long-effort-20261013-drive-metadata.json；原9B不能当27B干净前后对照。

## 实际effort语义：已查到什么，没查到什么
- 旧root=/research/d7/spc/yzyang4/scheduling-feedback-effort-20261012-v2。只读tokenizer模板及配置，合成固定提示的default=xhigh、medium≠xhigh；不是实际模型输出验证。
- 镜像内vLLM0.29.0的protocol接受xhigh且转发至chat_template_kwargs；protocol SHA8a1f1138f79557aa5b5add12e81b9745fd5e286fa35f0502a97f2a377d41665b。
- 旧四角色max_tokens8192、请求600秒、run1020秒，服务context131072、TP2/max_num_seqs6。上下文上限不能替代输出上限/时间预算；旧bounded适配器还硬拒绝timeout>600。新独立长推理设计必须说明共同调整，不静默改旧批。
- 模板SHA c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041；tokenizer_config SHA b11349aafa7cdc6a320767cf7ceb29ed82f7eda5d65e8e0819e76f0ce947bf27；service_entry SHA ec18d6804087e17354934d9dfe24f129d8378211b043c04bc9e519e6951ecfef。
- 冻结backend实际为async，SHA458683d335cbe5f558ef06288a40d670af4fd2ef9a64b448ca577d7d78138cb8；GenericLLM SHAde768c80238b0cf13b6359a64223f913ff30d133b9f23711d2ff643adc2949e8。工作树同名旧sync文件不能替代它。
- CPU脚本在本地_codex_tmp/effort_semantics_20261013.py、vllm_effort_source_20261013.py、effort_transport_20261013.py，前述静态检查已完成；无模型/HTTP/GPU。
- effort_wire_cpu_20261013.py已在SCP完整结束后通过：固定backend→LiteLLM1.65.7→实际序列化→假HTTP响应，medium/none/xhigh三例均保留正确reasoning_effort/enable_thinking、max_tokens8192；socket尝试0、真实HTTP/模型调用0。这是当前离线传输复验，不是历史抓包或xhigh质量/长度验收。先前SSH超时/banner中断均发生在测试前，未重启实验。

## 本轮文献与判断边界
- AREX-2同Qwen3.8-27B长轨迹训练及MLE相同skills/rounds参照已读；无正确性反馈实验是BrowseComp，不当MLE去score已解决。Guidance-TTT已训练小指导器配冻结执行器，不把这个拆分称新。
- RHI已有harness优化与高effort比较（合成研究任务/LLM judge，不是真执行MLE）；Ares/CoT-retry/LASER/InfraMind限制简单动态档位主张。When Agents Slow Down仅核摘要，不能声称已排除全文近邻。
- 优先问同预算最终质量—成本关系是否真改善，不开发新的复杂router救17740。暂无新方法阳性，引用和较细边界见ROUTE_DECISIONS。

## 最近真实实验17740：已闭合，不重跑
- 10/12 HK18:26:18 COMPLETED，48/48、6等预算池；2旧开发任务×4搜索seed×3臂×2反序重复。medium/fast/feedback_think，共享greedy，Analyze固定medium；1020秒/run、1180秒/池、2服务+4执行。
- 原quality=false、structure/mechanism=true。去噪两重复medium/fast/混合分别0.019929967149881492/0.014879316923648044/0.01841157291063107及0.016919910295110023/0.016424072925913014/0.014526227565536542。
- 混合比medium相对误差低7.618648981362969%/14.147136053465204%，但对fast一负一正；Aerial近天花板只作不退控制。混合去噪胜起点3/8，fast5/8，medium3/8；池内相关，只有2池重复，不能称普遍可靠性/新方法确认。
- 46评分重算、24CPU配对、固定物理GPU/清理、独立Node逐格CSV与统计核验通过；原门不变。成功code调用触8192计medium7/34、fast0/51、混合2/41，未记录finish_reason，不证明截断因果。
- source1cd338f86dac1381795c0295abcefefc8391df8d；planSHA4b33b157e65ba4b14668dfb9e3309ba2e9173ba62c0d542614ef9bad7befd0fc；summarySHAecf3dc4123e657c3f4221e7b061c7a0a7550be27f4febc21034367c7282e3b8a；结果sandbox_scheduling/feedback_effort_v2_closed。
- 旧批实际44166GPU秒；含17736入口失败1968秒，共46134秒=12.815GPUh≤13。17736零模型调用/零评分，旧48分母保留。旧17740 GPU/monitor/readout/SCP已闭合；本轮18161是独立新授权，不能混账或重开旧门。
- ABCCBA共享prefix-cache/两复用任务/条件暖起点限制保留。停止本角色混合配方自动扩大，不补seed、延上限或换任务救旧门。xhigh若做是独立新研究，不翻转旧门。

## 历史关闭与操作
- 17681硬预约质量门false且不完整；17675资源项改变选择0次、质量门false；17670请求时限复验质量门false。不改阈值/重命名重开；细节在前述Git交接和各closed目录。
- 2服务+4执行已真实跑通，不重复G0。跨节点交管理员；历史OpenBLAS EAGAIN根因未确认。旧Held12535不动，失败原件不删。
- first-960/Target-300/Target-522、D_val/官方test、16560数值导出继续关闭。不训练或RL更新agent底座，不恢复旧critic/HCE/多保真/Probe/score-channel/K≥1。
- 活跃checkout=C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001；detached HEAD有意。发布仅myfork/phase1-value-critic，需显式stage/安全guard/快进与ls-remote核；本轮未发布。
- 用户未跟踪phase1/reports/给学长_MLE沙箱资源调度进展_20261009.md与旧checkout dirty不动。凭据只远端，学长新材料先scan；不导出候选/预测/标签/权重。
- SSH linux5；PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。已知IP137.189.88.148可配HostKeyAlias=linux5.cse.cuhk.edu.hk和StrictHostKeyChecking=yes，不跳过hostkey。
- 本轮gpu3 RTX3090已有资格；优先gpu27/gpu28。现有MLE镜像不投projgpu39、不升级Torch/退CPU；排除projgpu7/8/33、gpu36/38；gpu24 cuInit999未解。
- 研究盘4TB至2027-08-30，不是实时剩余空间。Windows Python不可用；SCP必须等exit0再核SHA，不拿复制中缺文件当最终失败。长贵批次先矩阵/全成本/停止门，不复用旧失败预算。
