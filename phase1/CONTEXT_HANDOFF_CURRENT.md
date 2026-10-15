# 当前短交接：恢复先读本文件，不从旧心跳恢复任务
当前10/16 HK00:50：用户明确批准新独立保护接线批32条=2任务×4seed×fixed/shared×2反序池，每条1020s、SLOT1180s、2服务+4执行、含失败启动清理≤6000s/10GPUh，无训练/API/自动补跑。新root=/research/d7/spc/yzyang4/scheduling-pooling-20261016-v1，CPU临时目录/tmp/pooling-guard-20261016-afjIZw；修改仅install_hooks接已有protect，追加真实入口信号测试/来源配置一致性门。19本地回归通过；真实入口CPU/准备/提交尚未完成，不能称开跑。旧18510/18468/12535不动，旧结果不重读救门。学长c394ca17仅新增1012报告及bigjournal生产入口，未独立核验其效果。六小时复查automation更新至10/16 HK06:44一次，不读旧日期提示。
最后观察10/15 HK13:52：18510于13:39:00 FAILED闭合（12:55:53启动），2587s×6=15522GPU秒=4.3116666666666665GPUh；32计划/16启动/15完成，index9失败、后16未启动，已启动16个worker清理与service gpu_clean=true，shared池最终GPU扫描因审计先失败未形成，不把service回执替代它。root=/research/d7/spc/yzyang4/scheduling-pooling-20261015-v2，source=b275812f48761ae2cadf507b749ae948e1f41ab0，planSHA=c31091ff71f19a15ce6cdb12583f1d7a16cbc5f53a96b97d26b03782003bce64，冻结readout-20261015-v1已存在，不覆盖。4GPU真实资格/16实际首输入过；shared_pool漏接既有protect，截止中断状态提交后残留392字节tmp，清理FileExistsError、队列审计失配；原件留存不修状态。冻结读出复算14开发评分，独立Node全分母/CSV/成本及4文件SHA通过，证据pooling_18510_closed；完整质量门未满足、无收益判断。真实Linux跨线程SIGALRM24CPU测试通过，其中候选guard申请路径40次及释放/取消，旧错可复现；只在fixture套guard，生产入口尚未接、没有新准备/提交。下一独立GPU批需新明确授权，先接实际入口并测试接线；不重开18510/18468或复用余款，不改32条/1020s/1180s/质量门。队列仅旧12535Held不动。本轮未push；操作教训已记memory/OPERATING_RULES。
最后核验：2026-10-15香港06:38:58，18412已于05:07:45完成退出0（01:45:52启动，12113秒×6GPU=72678GPU秒=20.188333333333333GPUh≤22.5），不再运行。48/48完成、48真实首输入一致、77外部开发评分重算、24CPU配对/6池物理卡与清理、原模式/预算、独立Node统计及六文件传输SHA均通过；原质量门false。去噪重复0/1 best（旧fast/旧medium/新metric）=0.009738903630219946/0.014217226114657332/0.016851028985227796、0.013387899427844734/0.01314423284656948/0.01356582535832205；新metric两轮均差于两参照，median两轮也差于旧medium，Aerial一优一退。停止扩大此配方，不补seed/改门/换点救结果，不将历史积累当权重收益。证据sandbox_scheduling/metric_deployment_18412_closed，summarySHAc68e4c4caafb3b63ad22443c5e7e2f330a0f22a3ddd47887dc06b10820e366e9；远端root=/research/d7/spc/yzyang4/scheduling-metric-deployment-20261015-v2，readout-20261015-v1已存在，禁止覆盖重跑；source63623208e8918bf3b1351c595382d0108aecdb31，planSHAe3baf5d2fa704cdd0c3fc458549aa21449fdbf3209bac87337b370e2a416e154，readout pins见metric_deployment_20261015_cpu/pins.json。两旧开发任务/共享服务/条件暖起点，非48独立重复、固定数据reward消融、训练回本或泛化；正式确认0。v1仅CPU零GPU封存，旧Held12535及18269不动，不重复G0/下载/提交；无新GPU/API/训练，本窗口未push。
恢复顺序：fetch → CURRENT_DIRECTION → ROUTE_DECISIONS → 本文件 → 必要原始证据；本轮还未push。
本次覆盖前的完整交接：Git 72167a42feccaec44f5793c3bc7d2f4e9132d581:phase1/CONTEXT_HANDOFF_CURRENT.md。

## 本轮18269确认及已闭合18253/18161
- 10/14用户指向Drive后已核：checkpoint/online_thinking_score仅step30归档（内仅权重+adapter_config）；policy_training_data/online_thinking_score/day0完整tar目录仅train.parquet、val.parquet和conversion_report.json，未解析/保存训练行。报告scan0、Qwen/Qwen3.8-27B/max_length65536仅是转换设置，实际训练配置未补齐。GRPO_OFFLINE_TRAINING.md@64fd78e明确普通逐行shuffle和episode advantage广播，但示例9B，不证明27B step30启用；私有verl gitlink51ff1b4c仍不可读。证据drive_training_config_20261014.safe.json及manifest脚本；不重下权重、不用公共默认替代实跑。长链多行10/5已验证、非新发现或梯度bug；同组减同父常数可被标准化抵消的旧代数检查仍保留。
- 闭合root=/research/d7/spc/yzyang4/scheduling-weight-confirmation-20261014-v1，顺序旧/新/新/旧；seed214501..508、214601..608，共同warm不跨池传历史。source c9d2953f0857106bf4e26724d1dc2646b78c2544；planSHA316381bce41c9ceb9c34fb165e94996eeeb8c9968eff3cb4e63642fbfa549626；readerSHA83d18a0646c57ed9e9879dae8ec7a1d8c612c856b22a69b2a9b0594930b62d0a。去噪两重复旧/新best=0.013654153292274094/0.015045886425786793、0.01543541427703299/0.01844707231236221；旧/新median=0.017496977748638058/0.03366372877911196、0.018188728444833158/0.03332520917522325（各n4，SD见原表）。旧门false不改；两池重复/单服务不是32独立样本，无fast/训练成本、来源不全，不推普遍训练无效。readout-20261014-v1与本地independent-verification已存在，不覆盖重跑。真实matrixSHAd404be9491a103824bd6992c0d869e45cd803f6fb4a85bcc3756c809cedc2746。
- 10/14新增闭合18253来源分析：101候选返回、46有效均code-hash关联原生角色，7未匹配均无效；8任务×臂格中4格最佳终步Debug（包括旧fast去噪）。32终点逐值复现，4CPU单测及独立Node安全导出统计复核通过；后者未独立重算原始join。证据sandbox_scheduling/role_origin_20261014_cpu/result.json，SHAc5cc1cbedb89acf823158170949260164369766b160967626654b19af10c8bd2，复现closed_role_origin_20261014.py。只支持不能先验把Debug当浪费；不是移除Debug反事实或角色因果，不恢复已失败混合档位。旧首步新/旧medium各2/4改善的diagnostic仍保留；原输入差异、共享池、训练来源未知不解除。
- 已核32/32、46外部评分重算、16CPU配对、4池物理卡/清理/模式、独立CSV统计/五文件哈希，13.931666666666667GPUh≤15。质量门false；去噪best旧fast/旧medium/新fast/新medium=0.010427187690454438/0.013598094008495543/0.022176433381460952/0.017121281517189432；对应中位0.03253226552125881/0.019368611681579734/0.03583616059994125/0.020786268184847655。新medium Aerial best1.0、median0.9999184853781478仅局部开发阳性；不能称整体或日更训练收益。
- 证据sandbox_scheduling/weight_effort_18253_closed；summarySHA bdcfbf37e185f92204584d94c503a72b7ece274d83d01a32b8d15589da5058c0。远端readout-20261014-v1；独立verification与final-assessment保留原门false，不覆盖。源仍6b592cb150be38b9b3bd140cd77dd448d96add12，plan/reader SHA见下。两次监测读取问题独立复核后正常；一次仅exec返回running session，不能当作业失败。
- 实际首次提示8组都不全同：24对比中23只差data preview内随机kernel守护回执文件名，episode25旧medium去噪的预览被内核就绪超时替代。原始提示哈希失败不改，32条全保留，没按分数删样本。mock preview CPU门不代表生产输入一致；下次先冻结真实public-data preview、隔离harness回执、禁止preview错误进入生成，需独立新批而非复用余款。未声称这些差异造成了质量差距。
- 新授权32条=2任务×4搜索seed×原始/共享训练后权重×fast/medium；1800s/run、1960s/池、2服务+4执行，含启动/验收/失败/清理≤9000s=15GPUh。不训练/API、不自动补跑；每格一池非独立重复。主比较新medium−旧medium，fast为次要。所有格初始历史相同，后续不跨格共享。
- 新adapter已远端完整下载到/research/d7/spc/yzyang4/weight-effort-adapter-20261014-ynf9spm3/accepted_adapter，选Drive 1_GXBwH5jRXTnt-lW_-ur4l0rUPBav2ZK（online_thinking_score/step30）。archiveSHA b6958bb33821a0a1d7e3203bcc6eec18470c0d3e4c0218667ed2452dbf5d0d9e；weightsSHA c7666264904a3490958e46cfbb989a22bc52b9a81c9714631751c7bf8445b61f；configSHA f0a0264f243f57a126a9903499ee48984e660a6bf0ad7b3d351431ce4546198e。992有限BF16张量/rank128；496组形状全部对应（240dense/256int4）。base/revision字段空，不能称相邻日更因果；运行资格在本批9000秒预算内先测，通过才搜索，失败即闭合不重试。
- intake/形状/镜像源码/完整文件哈希检查均完成，不重下。冻结源码commit6b592cb150be38b9b3bd140cd77dd448d96add12，root=/research/d7/spc/yzyang4/scheduling-weight-effort-20261014-v4；18253曾用gpu29六卡、四格同机同3090，未升级镜像。任务CUDA/namespace门通过，不增G0；作业现已闭合，旧预计时间不再当现场。状态工具/tmp/long-effort-20261013-4iRdot/weight_effort_status_20261014.py只读结构。
- v1/v2/v3均仅CPU准备、零GPU/真实模型调用。依次发现我方模型前缀断言漏openai/、测试混计prompt哈希事件、测试未按正式worker设置random.seed而软件包列表被原生shuffle。前两已修；v4只补测试seed，不改原算子。v1尝试重写exclusive plan被拒，保留原件，不再原地改。独立JS读出8合成测试通过；正式首提示必须同哈希，不能跳过门。
- v4前检32配置/24配对、4原生async角色/MCTS请求门通过，首Improve提示同SHA ef71abe51bc72d0d5af91c2a1d75656628838f922066392a04cb23bf8e929263。planSHA cba9bad500a106b8c44f18116c491a1744edb50c3744c7f7ef1f498e45cdbd4f；readerSHA 1f2ae31840a8d72d084fb487058712c581fcdf18abfdf44b296599edbde0c6c5。独立读出verify_weight_effort_20261014.cjs，pins在本地_codex_tmp/weight_effort_pins_20261014.json。仅完整闭合后读分，不中途选权重/模式/样本。
- 只读weight_effort_runtime_prompts_20261014.py已纳入sandbox_scheduling（远端仍/tmp/long-effort-20261013-4iRdot）；闭合后核8组同seed四格首次实际返回提示哈希，首次失败则未验证，不以后续成功替代。5项合成测试本地/远端均过；不改冻结GPU源码/质量门、不读提示正文/中间成绩。主要medium内比较不变；即使过门，若仍输旧fast则不能称超过强参照。
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
- 用户最新确认score/metric两谱系每天用各自生成数据更新，非同数据reward消融；原话与边界存ADVISOR Z。新metric仅部署资格待核，下一对照保留旧fast/medium同期参照、同起点/历史/整池预算；先新产物内容/兼容及独立矩阵预算，不自动提交或试遍日更点。奖励尺度/缺失地板风险仅合成验证，不认定实际故障、不改学长训练。先前xhigh/未来validation–D_search建议仍见Y。
- 学长计划不记为已跑通/满分；我方不更新agent底座的禁令不因此解除。继续R14相关的推理成本/真实质量研究支持，不恢复旧critic/HCE/多保真/score-channel。
- 当前建议：旧/新日期固定checkpoint×fast/medium/xhigh，同最新archive、起点、可见历史、硬件及整池预算；版本效应和effort效应分别在另一轴固定时识别。先验证权重更新是否超出历史积累，能否降低推理成本；这是设计，不是新算法/新收益。
- 不用逐日累计最高分当学习证明：未训练旧模型也应获得同样最佳程序/历史。学长训练默认去掉proposal搜索记忆是明确设计，不先验判错；更需与上下文复用的廉价参照比较。
- 新旧checkpoint事前按日期选，不能用本轮结果挑最好点。训练/采集成本单列，部署收益与摊销后总成本收益分开；保护集未解除，当前仅开发证据，不能称独立test泛化。
- 最终E2E目标仍是同一初始archive下，“训练+搜索”胜“把同等新增总算力用于不训练的强搜索”。六格只是既有checkpoint的部署/机制读出；单程序发现与通用policy收益不能混同，不强加跨任务policy泛化为发现的必要条件。TTT-Discover v2直接覆盖单任务自举宽概念，不能称首次。
- 思路交付的优先顺序：冻结模型补fast/medium/xhigh强参照→日期固定旧/新checkpoint同历史比较→有收益才核整循环回本。同预算终分主读出，事前固定质量门槛的整池成本为辅；未达到按删失记录。只复现已有最佳程序不记新发现；新低effort胜旧xhigh不能单独证明压缩推理机制。
- validation/D_search若参与训练/搜索就不是最终封存集；“不用官方分数训练”和“部署不接收外部分数”不是一个问题。这里只澄清后续设想，不启动score-channel消融或analyzer。

## Git/材料最后观察
- 10/14 HK22:46窗口fetch成功：公开myfork/phase1-value-critic仍72167a42feccaec44f5793c3bc7d2f4e9132d581；本轮编辑前本地HEAD3ce0fb5fce21bf5a733e7c3fbb1224063f31cdfd，冻结18269源码另为c9d2953f。学长myfork/dojo-reproduce=8d39164c5b4c2c1c304fc28801e60467e0ad5de5，未见新outcome。最新Drive/源码检查不等于模型收益；未修改学长分支，本轮未push。
- 四个新增/修改文件credential-shape scan为0后读取；新增use_metric_reward默认false，不证明生产启用。policy outcome最后修改仍13d28830c66a96988c180532495326dc144eb93b（10/9 HK20:15）；没有确认新训练效果。
- 精确journal/to_grpo源码确认metric=内部验证经分析器提取、score=metric_info.score；两者都用official median/gold阈值映射，reward1是gold不是满分。学长已确认两线预期字段，实际命令/损失归一化未取得。8项纯合成首遍AST检查：全有效且无clip/过门才有标准化正仿射不变；缺失min−1地板可翻转较差有效样本advantage符号，绝对spread门/可选clip另有限制。证据reward_contract_20261014.safe.json；无真实训练行/损失/梯度，不认定失败原因或新方法。
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
- 10/14补核FACTOR摘要/§2–3.1已有动作/词元信用与长度归一化；TRACE仅摘要/引言，已有TD回合信用但依赖gold-answer。通用信用分配不是空白，不能以未来最好MLE程序充当无代价gold。公共verl agg_loss多种归一化不证明私有训练配置；不恢复底座训练/TD，不开发router救17740。暂无新方法阳性，链接/边界见ROUTE_DECISIONS。

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
- 研究盘4TB至2027-08-30，不是实时剩余空间。系统Python此前不可用，本轮应用自带C:/Users/yanze/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe（3.12.14）已跑纯CPU检查；不等于远端训练环境。SCP等exit0再核SHA；长贵批次先矩阵/全成本/停止门，不复用旧失败预算。
