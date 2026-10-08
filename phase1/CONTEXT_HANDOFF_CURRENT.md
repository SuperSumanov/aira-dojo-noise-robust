# 当前短交接
更新：2026-10-08 12:10香港附近最后观察。旧全文完整保留于Git f507a53f759b41fee5e3f39906ff6db50ec69796；不要把旧状态恢复成现场。

## 方向、目标、授权
- 活跃checkout：C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001。fetch→CURRENT_DIRECTION→ROUTE_DECISIONS→本文件；旧aira-dojo-codex-20260813有用户dirty，不整体覆盖。
- 唯一活跃R14：MLE沙箱资源调度资格/朴素强参照。SchedMate已覆盖宽语义调度；暂无重要独特、强基线跨任务同预算成立的新方法。不扩旧R1–R13配方。
- 用户要求本轮约07:51–13:51香港完整六小时在会话内研究；tool goal active，尚未满六小时，不提前完成。用户最新明确“批准所有操作、不用问”；自主合理推进，但不解除保护集、底座、凭据和学长分支边界。
- 本窗口新增GPU自限≤3 GPUh（含资格/失败/整池空闲）；无API/agent底座训练。新三策略小试验计划1×3090/6CPU、最多90分钟≤1.5GPUh；候选源码不改，不以旧批次余额补跑。
- 不读first-960/Target-300/Target-522、D_val、官方test；不恢复HCE/多保真/Probe/TD/score-channel/K≥1。不操作旧12535 Held作业，不改学长分支。

## Git及远端
- 公开己方及本地HEAD f507a53f759b41fee5e3f39906ff6db50ec69796（push+ls-remote核实，13文件credential/敏感文件名扫描0命中）；只读首返回延迟分析/交接待提交。16996执行源码3bed6f7f、16997为3857ffbb、16999为9426f910、17005为0e61e2d2、17014为f334fa7f、17017为5f44b1af。不含原始预测/标签/凭据，学长分支未改；不改变冻结运行协议。
- dojo-reproduce最后fresh fetch=dfff0efb9daf1d4a63c74492f138c19c1fd8440e；学长autoresearch HEAD=d82dcd845e30e9771750510028d38a6d1d979c43，无新更新；未改学长分支。
- SSH linux5/yzyang4；Python /research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。原MLE镜像只投已兼容gpu27/gpu28 RTX3090，不投projgpu39。
- 研究盘/research/d7/spc/yzyang4总授权4TB至2027-08-30，不等于空闲容量。镜像SHA801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda。
- Windows SSH内层引号会丢失；远端格式参数不用管道符，复杂逻辑上传脚本。Git附属sh可能报NtCreateDirectoryObject警告，不能据此声称hook通过；commit本身成功要另核SHA。

## 本轮已经结束：不重开
- 16987：原批准两程序入口复验，FAILED1:0，37单GPU秒；2 worker尝试/候选开始0。记录器错读冻结ExecutionResult不存在的timeout_phase；是我方接口错误，不是候选失败。
- 16987 root /research/d7/spc/yzyang4/scheduling-entry-20261007-v1；plan SHA96d7e9e7ed7f7dcf9d85eea1ca98edca5f00ab6a45edd58b1c76425e5a8d2495；closed SHAcfc0627e6e5ddab1304bcd1c3ad8d6d4dc5bd9cc84949b5a3400827c31d9fc8e。
- 16989：独立限定v2，FAILED1:0，43单GPU秒；2原程序真执行/1完成。CatB GPU59轮、512行输出；XGB RuntimeError为“所需稀有类别不在映射中”。记录器已修、不是CUDA不兼容。无调度/质量效果结论。
- 16989 root /research/d7/spc/yzyang4/scheduling-entry-20261008-v2；source69bc9b88；plan SHA6b68c0d0cb8526e375b5f5a2e1dec8f3ffaee0b035836b380c318272ba510762；closed SHA8002aec68145137863971df2d7ee2bb33f49676b5c3c1556b4a0c2bfe3515396；runs SHA8ba2741b0ab8db5c499db1487b1a7fbcd638e73030b2fccb30d578ac6d0c85c0。
- 公开train只读核3,600,000行：类别5全文件仅1行（索引1381253），原4096训练样本漏掉它；其他类计数与source SHA7829557bb65fcc4400ebb5a653fd68e226f15b1dbc9b664a45d7ec2d353c797a已由check_dec_fixture.py打印。不读隐藏标签，不将输入契约错误当模型/调度反证。

- 16992新池v1已FAILED1:0/100单GPU秒，36槽/4尝试/3完成/32未启动，0对照。XGB在第一个fit报Invalid classes；补全类别仍未满足每折覆盖：另一稀有类仅1行，KFold训练折缺类。是开发输入预检不足，不是共享无效。CatB GPU142轮完成；Spooky/Petfinder完成。readout-v1已写一次，不重开。
- 16992 root /research/d7/spc/yzyang4/scheduling-pool-20261008-v1；source51af1543；plan SHA5cbc51b2f5adaa28fce5d3f11fd4e0c937f26f15638942d4aa0ac841060f04cf；closed SHAcd090ba3ab7514eca18c3d4e16525066d41c49b32df7f732931b4cd60d9ba7d9；runs SHA532f52b0600c967347a05ffab6d2be57257a3f9c5bf6046f6f1881af0fe9f0b7。

## 最新已闭合：有限的朴素并发收益，不是新方法
- 16994已FAILED1:0/566单GPU秒，36尝试/35完成；serial及share2各12/12，one_gpu 11/12。root /research/d7/spc/yzyang4/scheduling-pool-20261008-v2；source6e36a61d；plan SHA429339013cca8e2858cb2cc2edfefe017f096b0c4afbc0172987d897becf7a56；preflight SHAab96d6b2c2aded76eeba2458e346f563e818c00ba7550bf31832669fc57be799。临时目录/tmp/r14-pool-v2-20261008.RafNX9。不重开/补跑。
- 完整A/B三配对serial/share2=1.8423276573417586、1.7307638813016224、1.7852942816262258；中位1.7852942816262258，样本标准差0.05578656742353592。四程序6份A/B输出各15两两比较数值全同，形状/原完成回执哈希独立核验通过；60比较非60独立样本。
- 独立时间审计SHA d21cd09c38e87c3dfa5ccdb0b6d8451a034cd51f01e894399c911394ad0d353d；独立输出审计SHA fdf14b788c7ef930b67225be03e279845cae12c105779d88741fea6a2e06ecc7；readout SHA b8347a0e529feb84d646765f5f09eae07a56716569d75ae7b529a2d332d2069f。证据本地sandbox_scheduling/pool_v2_closed。所有观察块max resident GPU clients=1；只能称启动/CPU/候选阶段并行，未证同时GPU训练共置。
- slot17 one_gpu/program4在candidate开始前cell0 TimeoutError，外层ValueError；不是候选OOM或策略因果反证。保留失败，C只有2完整比较，不报告删失败的C胜负。closed SHA f15cab21c26e8967ae0bf8f1002476323dcaa925539bf8d2fe47fcae4ff918a5；runs SHA ee08a68c8c130a690b6a951fb6d5827ae9879fc54d9f18ce3e99f992b25c832f。
- 本窗口闭合实耗6877单GPU秒=1.9102777777777777GPUh（含17005的1989秒、17014的157秒；已打印），尚余3923秒。17004排队取消0秒/空AllocTRES。确认上限2700秒可容纳；若确认实际≤2123秒才再容纳强对照重试1800秒上限，否则不提交。只认实际sacct且前批全闭合，未分配CANCELLED仅特许已核17004/0秒/空TRES/无step或执行回执。原样重启非独立训练seed。
- 保持4份原源码，公开输入非5类至少5行，唯一类5按原程序加入每个训练折；CPU已核所有训练折均含7类，不复制/重标/使用query。SSH准备阶段曾断开，PID145097继续写完preflight；不是重复prepare。旧16992及入口批次均不改。
- 矩阵：原programs 0(XGB)/1(Spooky TFIDF)/4(CatB)/3(Petfinder LGB)，共3任务；serial/share2/one_gpu ×3原样重启=36槽，另1次warmup，所有开销含于单3090/6CPU/90分钟。不是跨训练seed。
- 新GPU输入只替换末端超出最低覆盖的类行，补最早独立公开训练行；排除旧train/query IDs、query不变；两GPU程序及所有臂共用新输入，旧文件不改。属于新开发小样本系统试验，不称全MLE-bench。
- 三臂Latin次序，每重复同一旋转FIFO；one_gpu仅手工核验的CPU/GPU代码提示，最多1GPU程序+另1CPU程序。无LLM/学习调度器，不能把朴素基线叫方法创新。
- 首serial四程序须全完成且两GPU fit有回执，否则整批停止。后续共置失败保留分母、不重试；只有进程释放/隔离/遥测安全时才继续既定其他臂，不以失败臂缺失时间作加速分母。
- 预注册读数：每臂3块完整、完整makespan/全分配成本、3重复离散度、候选重叠、GPU训练和输出差异；探索门为median改善≥5%且无未解释输出漂移。A/B过限定门，但仅4小程序/3任务/原源码seed42重启，harness130701未覆盖源码自身seed，不是跨训练seed；不读质量分数、不推live E2E或语义增量。
- 本地相关30测试通过；远端新增8测试通过。新记录器还在实际冻结旧ExecutionResult上纯CPU验证；不把mock当GPU成功。当前源码fixed_pool_trial.py/readout.py及tests，原throughput_pilot.py未改（SHAb30eed3f…）。

## 研究核验与边界
- **新发现的测量风险**：preparation_overlap_audit.py只读mtime/块时钟，16999 block6/7/11与新准备重叠，17005首serial/share2块各重叠24.523789882659912/66.60744571685791s。只证已知准备区间重叠，未测物理I/O/因果，且该区间只是preflight的保守子集。16994/16996/16997没有已记录重叠；不推全系统无干扰。保留主分析全部块，16999/17005耗时标有混杂，不当干净确认。后续overlap批次期间不得另做大镜像哈希/数据构建。NVML旧采样另显示Cactus单执行训练包络整卡约2–3%，不称GPU重负载/CPU瓶颈已证。
- 16996已COMPLETED/12尝试12完成/1444单GPU秒；root /research/d7/spc/yzyang4/scheduling-neural-20261008-v1；临时/tmp/r14-neural-20261008.63G0Qp；source3bed6f7f。plan SHA8da0e849c3203efc2c47c13f134fe9d841ede0f9c3d667789e41ab2aefb95edc；fixture SHAa02145bfaca50c15767948a62767e28ae9e9fc356d77239a4714fc7c1aa2d712。三配对加速中位1.3508923175938645、样本std0.09956925293864344；Cactus六次各150步、DnCNN六次各640步，六份输出/程序数值全同；两并发块max GPU clients=2，非kernel并发证明。readout SHA8bd34bf9fab08dccc33f38c63376bbf3a83fbc8a347bdcc86f5d10c5620e5104、runs SHAb022efb4d519291b8bdb481ab3fe94fdc27c2d31bb539a897c8d7dbeaae7f13c、独立audit SHAde1078c9f0b6c3b7b2c5808c1ac14375ddff98ff20fffb8ce3587a9ecf41227c。readout-v1/audit-v1均已写一次，不重跑writer。
- 输入仅公开train：cactus首64字典序ID作query、其余train，原程序内部用20%子集；DnCNN首31数字ID配对输入（内部16训练/15验证）、后2仅noisy作query，query clean不挂载。原源码/超参不改；每episode空私有缓存，readonly输入固定symlink→/workspace/input_cache。仅开发fixture、非完整MLE-bench。原镜像依赖/被动Adam记录器CPU等价与真实GPU资格均通过；不是跨训练seed。
- 16997已36/36完成、488单GPU秒；pipeline root /research/d7/spc/yzyang4/scheduling-pipeline-20261008-v1；tmp /tmp/r14-pipeline-20261008.lSnlbY；source3857ffbb；plan SHAe2496978a3d0d58870ac05d0d3283f238ada8963219b7b2252eab0f488f46094。四个16994原程序/原输入×serial/pipeline/share2×3原seed重启；pipeline只并行初始化，候选至close FIFO串行。中位serial/pipeline=1.3895209144462672、pipeline/share2=1.3177936445362894、serial/share2=1.8311018300075441；四程序各9份输出数值全同，GPU fit轮数相同，独立GPU/CPU身份/屏障/输出审计通过。仍只小程序系统证据；单次2.09含时长波动，不称理想固定服务时间加速。readout SHAfd6a6009a331cde091cc4c0e5772a5f37ffbaacbc5085066195017c908ac6bb4；runs SHA f2a5ab36b71af9b6f12a29c97b63c06d06b66a3c8d35e26e0cca992d5bac92b3；audit SHA292cd12473e69b7626ddb601efdcfa6192a9a887e735958874b3a0700079608f。两writer已完成，不重复。
- 16999已FAILED/24尝试23完成/2053单GPU秒；root /research/d7/spc/yzyang4/scheduling-homogeneous-20261008-v1；tmp /tmp/r14-homogeneous-20261008.jgBdf3；source9426f910；plan SHA1015a7039bdb3436f9d0c0fb2711c045b9c4b48513224bff4c70aa66b381388a。slot7/share2/DnCNN在cell0初始化120.05572430416942s超时，候选未开始，非OOM证据，不补跑。Cactus12/12、三配对中位2.2346668327601384/std0.1387986902704743，步数150且12份输出数值全同；>2含单程序时长波动，不能当固定服务时间线性理论收益。DnCNN11/12未过门；仅两个完整块描述性中位1.1360276669511111，单程序约2倍耗时、第一实例响应约1.70–1.82倍，不能藏在吞吐里。独立源/input/GPU/CPU/数值审计通过。readout SHA318297c96892accd8732e398d699d80ef418861e1c740833f32fa3adfa590168；audit SHA5c0ecf2a9b750255bc9892a5040643bdc1d49a59d995744daeaabaf985cf3498；本地homogeneous_v1_closed三文件已取回。两writer已完成，不重跑。
- 新神经门事前固定：12完整/3完整比较、median speedup≥1.05、每程序step数一致；cross-arm maxdiff≤within-arm maxdiff+1e-6且≤1e-5。数值容差不是质量保证，不读score；失败保留不补。计划与源文件hash绑定，明确全池计费。
- SchedMate§3–4：代码/历史/日志语义与干扰撤销已覆盖；无历史fallback profile、无progress跳过撤销是适用条件，不是我方优势已证。
- 新补AgentCgroup v3（工具级CPU/RAM及双向资源意图）、MARS系统v2 2604.26963（生成GPU/工具CPU联动准入）、Cortex（阶段资源池）。不要混淆这个MARS与R1经验论文。
- Regression Language Models for Code已有代码预测资源；VeritasEst已有CPU动态分析估计GPU显存；ATLAS已有提交时非clairvoyant预测/调度benchmark；“廉价资源预测”本身不新。
- DetShare/Pollux已有资源—执行/训练配置耦合；Substrate-Aware AI Agents 2609.05232已有事前资源约束提示；异步评价耗时偏差及按父选择频率修正也有旧工作。只换到MLE不足以宣称原创。
- 固定公开158程序/40任务/80相关父子对，source-only计时筛查20命中；13程序/6任务含clock条件与break，7未见break。含debug路径，未证可达性/真实训练效应/生产占比。
- 该screen root /research/d7/spc/yzyang4/scheduling-branch-screen-20261008-v1；summary.json、branches.json、review-v1/structures.json/summary.json。review结构SHA1797cba7a4230634f8f192d55e58d8e06f052e2b9568b5a0318b928c5576e730；必须逐例核，不能把语法命中称改善。
- clock-contracts-v1/summary.json已写一次，SHA cc37ab924fdc7caa78bdc02a221d3ecec9ea07aa9f5698ee6ef65ba4ee588608；13源码含debug-only分支、显式None调用及3000–3300s限制。配置本身可有3300，不能由fit调用None断言整程序时间门关闭；未证共享触发，不改时钟造阳性。
- 旧4份batch随free-VRAM变化仅纯算式；旧16370全池22.72%生成预留窗口不是节省、无ready backlog证据；生产factory本就close。16624只证生命周期原语，不是生产泄漏或调度加速。

## 历史与收尾
- 另一节点复验17004已在PENDING时限定state/user/name取消，sacct=CANCELLED by7542/0秒/空AllocTRES；预计16:27开跑超本窗口，未有GPU/候选结果，跨节点复现仍未完成。root /research/d7/spc/yzyang4/scheduling-neural-gpu28-20261008-v2；source6e8d8636，plan SHAcdec2fb419281c5d1275fde6431480b4a02fe43cd719673b56f7e7e549a48e5c；tmp /tmp/r14-neural-gpu28-20261008.pi9MTM。保留，不重submit或当零收益。v1时限模板5350s误认5360s而prepare失败，0GPU/0候选，目录保留。
- full-input v2=17005已COMPLETED/12尝试12完成/1989单GPU秒；root /research/d7/spc/yzyang4/scheduling-neural-full-input-20261008-v2；tmp /tmp/r14-neural-full-input-20261008.sHZh7W；source0e61e2d2969a18552024b923d0dc05bd08633bc1；plan SHAe836f8c49b13ce52ef02c138b873bc1464cdb147dc06254f656b707ff93afade。三配对中位1.602670906461665/std0.03902198324710583；Cactus150步、DnCNN3920步各六次一致/输出数值全同，独立审计通过。计时有上述准备重叠，非干净确认；全部块保留。readout SHAec02d12afecd94524f8cb2b142967eec8bcf1cde98edc387747f9c5c74d68a18，audit SHAec8245f112bdda512ca241a67d53b65095bf351fd414155c00bdd65037462faf，runs SHA42bc7d8c49594b13e5502cd34497c45b7b13c01117383a548da62fccf16dfa1a；三文件和limitations.json在full_input_v2_closed。两个writer已执行，不重复。实际输入DnCNN113公开配对/98内部train/15内部val，同2noisy query且无clean；以plan.input_scale_receipt/full-input-fixture.json为准，不用旧fixtures.json描述当前规模。
- full-input v1留存未submit：source6685eabf，plan SHA08d445f61423a4368c866156ccd5189503b921d54f12ba1a8f71980e46f2f22f；原预算解析不支持CANCELLED by7542/空TRES的真实未分配状态。v2仅修严格核算/root，不据候选结果改门，不重开失败样本。
- 神经启动强对照17014已FAILED/157单GPU秒，正式12槽0尝试0完成：预热wait_for_ready触发120秒deadline。root /research/d7/spc/yzyang4/scheduling-neural-overlap-20261008-v1；tmp /tmp/r14-neural-overlap-20261008.KnZYH8；sourcef334fa7f；plan SHAbd21f54108693bb539a8fb35521c69ea0a6e54ed53cbd5aab67cced20b9b51f6。预热completed.json误写complete=true但无output/exec指标，closed.returncode=1被controller拦住；监控现需交叉核退出码/输出，未修或声称解决内核就绪偶发超时。readout/audit均已写一次，audit SHA0c487a7211a71809669de70ccdf401c8b8a51bbd78ea2f8c7495b6ed4c27ebb3；本地overlap_v1_closed含12槽及limits。无策略对照，不重开旧root或抹掉失败；全部重准备曾在开跑前完成。
- 大输入独立确认17017已RUNNING且预热通过、正式候选0开始（12:09轻量核实）；root /research/d7/spc/yzyang4/scheduling-neural-full-confirmation-20261008-v1；tmp /tmp/r14-neural-confirmation-20261008.eJVICI；source5f44b1af605f4f7b6034d3556c4c1a2f62b7232b；plan SHAb8bf8619c61a98db5af35bb2b68f4b9838354c9ccfef166d8dd788ca0b16df7f。原17005两程序/输入/12槽，gpu27/6CPU≤45min/.75GPUh，450s/525s/550s不变；不替换受干扰块、不据速度符号选样本。9远端相关测试通过；下述重试全部准备及17014审计已在本批submit前完成。预算门6877+2700≤10800通过；运行中不再重准备/镜像哈希/全输出审计。新版monitor tmp/neural_status.py --kind confirmation；结束后冻结root neural_full_confirmation.py readout/audit各一次并传上述plan SHA。不重submit。
- 强对照基础设施重试已PREPARED未submit：root /research/d7/spc/yzyang4/scheduling-neural-overlap-retry-20261008-v2；tmp /tmp/r14-overlap-retry-20261008.jTdpZ1；sourcef507a53f759b41fee5e3f39906ff6db50ec69796；plan SHA528026478eff9138b06ff53023d5793139ea3bd9246fc3082cc3d749c8c25dfc。明确重试17014零候选失败，非独立科学复现；旧12槽及157秒保留。仍2原程序/小输入/pipeline-share2/3原seed重启=12，原worker/450s/525s/550s不变；总限缩为gpu27/6CPU/30min≤.5GPUh，不给失败候选重试。21本地/16远端相关测试通过，全部重准备已在17017开跑前完成。须17017闭合及审计完成且累计actual+1800≤10800，才由冻结root neural_overlap_retry.py submit；预算不够不启动。monitor tmp/neural_status.py --kind overlap-retry。结束后同脚本readout/audit各一次传上述plan SHA，另取pipeline-contract.json。
- 只读feedback_latency.py已对16996/16999/17005补首个成功程序关闭返回/平均返回时间，3本地+远端边界测试通过，三结果目录各有feedback_latency.json。比值>1表示share2更快；不把返回提前当质量或搜索效用，也不去掉16999缺失块。16996首返回强烈受FIFO原先先短/长的次序影响；16999 DnCNN两个完整块首返回更晚。纯事后机制描述，不替换原吞吐主指标；已知准备干扰说明继续适用。
- 16846已封闭：36槽/6尝试/2完成/4失败/30未启动，362单GPU秒，0共置比较；证据sandbox_scheduling/throughput_readout_v1。不得改分母或用新输入改写它。
- R11/R12/R13与16582失败界限见ROUTE_DECISIONS；16560数值导出仍有旧审查边界，不能借新任务绕过。
- 暂未创建新的自动化；本轮是在会话内持续研究。结束前核实际时钟和goal，不能声称六小时完成。新结果用轻量交接+结构回执；用户没要求不新写长报告。
