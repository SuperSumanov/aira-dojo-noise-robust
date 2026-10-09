# 当前短交接
更新：2026-10-09香港；旧79行完整留在Git 2b634744a92d17e5732419f11be30f6c0e9da04a。原实验与授权不因压缩改变。

## 当前六小时窗口
- 18:22新诊断已提交17326：readiness_gateway_trial.py，source548669e800fe97242851d2f89bb3aff621cbb813，plan72b42e1e39b4a444def1d831b5ade208a3bc6d1e04065571b660b435c6c60d0b；root=scheduling-readiness-gateway-20261009-v1，stage=scheduling-gateway-20261009.8CUa7r。远端5测试通过、prepare完整exit0后提交；28257须等退出，不重投。当前状态尚待现场核。
- 新独立阶段覆盖资格已事前说明：live_exposure_trial.py，4新run=Pizza/Spooky各2seed174901–174904，原生root5不改，share2单臂，每条3000s；3GPU/18物理核/65min≤3.25GPUh含模型启动/失败/闲置。不是v7同预算A/B，不比较其前600秒作反事实（提示预算也变了）。全4清理且两任务各有已完成Improve及外部反馈才支持阶段资格，不自动放行live2/4。4本地测试过，尚未prepare/提交；需17326结束后无重叠。原模型/任务镜像、合法dev输入固定，不接新数据或官方test。
- 18:18最新：17322已COMPLETED18:01:08–18:06:55，347GPU秒；48尝试/观察/清理，47 pass，parallel4 index24握手120.00046924222261s失败。收到3status/发送120info/0匹配回复、socket/thread活；不是候选失败，尚不能判根因。原一次读出readout-v1已写，transport_v1_closed两原件hash一致；窗口合计18610GPU秒=5.169444444444444GPUh。当前无本轮GPU任务，旧记录动态仅历史。
- 下一限定空内核诊断入口readiness_gateway_trial.py；固定同48矩阵，单3090/6物理核≤900秒/0.25GPUh，仅增加Gateway消息类型计数；无数据/模型/API、候选仍只有pass、既有120s上限不变。计数额外I/O使其不适合作速度比较；不修改旧root/门/镜像，不自动启动live2/4。5个本地测试通过；尚未prepare/提交。
- v7 root-exposure-v1远近SHA一致b10b9c44a95796dd7564db4343d65109f35fff614541d98a0b5f4c9e44883be7：16条num_children5/600s均只完成1–3Draft、0–2Debug，Improve总0。原生expand源码SHA f75a93f69fd79029ae4d3ce5b9dad81520480cbf36b56b05d8719a8b84c2a63d；3AST测试过；此前feedback-progress-v1 18有效返回全在journal。未完成内容未知，不能宣称调度已测到充分Improve搜索。
- 18:12 fetch己方624f41af/学长a5519bc8无变；新source e362774d未push。短期重点是诊断传输原因和负载阶段覆盖，不再无门槛扩大质量实验；20:11前持续研究，不因空内核COMPLETED冒称全部pass。
- 17:42最新：17308已FAILED，17:05:19–17:27:24，1325GPU秒；36/24尝试/20完成/4失败/12未开始。episode21 cell0内核就绪120.00047089718282秒超时，20/22/23在共同屏障被阻断，四个均未开始候选。原门false，f13dfb条件live2/4不准启动，不重开root/复用余额。下面17:08 RUNNING仅历史观察；当前无本轮GPU任务。
- width_v1_closed四文件远近端hash一致；summary c1dd1c6f746dd5502478a8eda32d30cf7b6c1796d280c307cc2bd45c631d8620，closed59e7d1d8092b90a473d7a2f1b010b44f51fd9498b8e5e9f6a38f592d563248d2。冻结readout一次闭合；独立diagnostics-v1 4f974ebb3578250cee3cd71311cc5e5486843ebd3b940838859a55f00fa2a7a8，20已观察输出Decimal完全相同、步数150/640均保留。原摘要equivalence=false因缺覆盖，不能说数值不一致；4个CPU诊断测试通过。
- width两完整2/4配对整批比1.5013821747034244/1.7927649723239687；四并发首返晚53.94527316093445/57.63973832130432秒，末返早56.63110280036926/114.33188581466675秒，第三配对missing。描述性权衡而非门通过/独特方法/live收益。窗口实耗18263GPU秒=5.073055555555555GPUh，包含v5/CPUprobe/v6/v7/17308，不含14:11之前v4。
- 用户14:11授权持续自主推进至约20:11香港；尚未完成窗口，不提前宣称六小时研究。主线R14沙箱资源调度，不恢复旧critic/HCE/Probe/TD/score-channel/K≥1。
- 活跃checkout：C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001。fetch→CURRENT_DIRECTION→ROUTE_DECISIONS→本交接；旧aira-dojo-codex-20260813的用户dirty保留。
- 14:52独立CPU诊断17267完成：服务12物理核/执行6，物理和逻辑CPU集合均不重叠，36GPU秒。标准Slurm nomultithread hint有效，不叠加冲突cpu-bind；不是科学收益。先前session92814连接超时未提交，现场核无intent后才成功新提交。
- v5/17262已CANCELLED：14:37:37–14:42:56，319×3=957GPU秒（0.2658333333333333GPUh）；16条0启动、服务未ready。服务实际9物理核违背12核契约，候选前停止；旧root不重开。operator_stop.json是取消回执，非合成完成结果。
- v6/17273已FAILED：15:12:42–15:12:56，42GPU秒，0搜索。包装入口缺host导出，生成容器shim发生ImportError；我方接线遗漏，非节点GPU失败。readout-v1一次闭合/本地live_v6_closed，旧root不重开；plan9bd8dc3b786c69f3a98fb892f49722c5a4c545532346e46be0e392108ae5ad9a。
- v7/17279已COMPLETED：15:30:54–16:59:15，5301秒×3=15903GPU秒/4.4175GPUh；全16正常闭合、四块1320秒预算/资源结构通过，0晚返回。正式readout-v1一次写出，本地live_v7_closed独立PowerShell复算及8文件远/近端hash匹配；summary f662677995ab85a61766dbf271cf2b93db89f9937c57a7048414d324e96eb859，closed b67209d7b90af8f562a12dbe846ab04dcc357a534134786b1f9303ee829c47ad。
- v7原feedback/quality门均false：块有效返回6/6/5/1，两个配对差0/+4，有效终点3/3/2/1；仅3/8双方有效质量配对（1改善2更差）。排队任务秒两配对减少0.7276678148458893/0.6315286955435901；无逐字节重复有效提交。这是机制/有限计数信号，不是稳定终分收益；首块一次kernel-ready失败，另存事后诊断不删慢时段/样本。当前窗含前置失败合计16938GPU秒/4.705GPUh，尚不含17308。
- v7 root=/research/d7/spc/yzyang4/scheduling-live-search-20261009-v7；stage=/research/d7/spc/yzyang4/scheduling-entry-fix-20261009.yAyBZB；入口live_entry_fix_trial.py；source44fcf9b433d0ed26c7799f82e5052a82d888f5a1。prepare会话36436断线但原PID1454405继续；最终preflight完整且PID退出才提交，不把传输退出码当进程成功码。
- 本地37测试/34通过/3Linux跳过，远端12通过，含实际shim导入和入口不重复初始化的反例；纯工程测试不计科学样本。生成服务在模型加载前核12物理核，执行在候选前核6核且逻辑/物理/GPU集合分离。
- v7矩阵保持v6所有任务/种子/预算，仅修入口（未见候选结果，不换种子）；不是新科学复制。Pizza/Spooky既有合法dev；4独立run/块，ABBA四块共16条600s；种子142901–142904、143001–143004。同27B/2GPU12物理核生成＋1GPU6物理核执行，只变FIFO许可1/2，保留run内顺序。
- 每块固定1320秒，包含服务启动、搜索、清理与显式填充；4块5280秒，整个作业最多5400秒/4.5GPUh。全部GPU空闲与失败计入；固定预留不等于成本最优的生产部署。
- 新问题是无结果筛选的反馈吞吐：不按首块生成有效性决定后续，全部无效/失败保留16分母，安全/基础设施异常才停。不同于v4失败资格试验，不是复用余款或放宽原门救结论。
- 反馈信号门：16正常闭合＋4块结构/预算核验，两个池配对均严格增加有效及时反馈且不降低有效终点数；最终质量严格门仍要求8对完整有效分数且逐任务中位差非负。缺失不补零；2池配对不是16独立调度复制。
- 600s相同不足以保证全成本相同；v5固定池槽，另报完整Slurm账单。客户端240s只是原生执行超时配置，可能另有中断/清理时间，不宣传严格240s物理cap。
- 只读观察：stage/live_status.py --version v7。闭合后用root/live_readout.py root root/readout-v1 --allocation-gpu-seconds 实测值，一次writer；再独立复验，禁止运行中改源/门。
- 服务alias qwen3.8-27b，实际qwen3_5/compressed-tensors4bit；不猜AWQ或更强生成器。编译cache跨块共用，活跃KV随服务重启清空。当前运行期间不做同节点大文件准备，避免I/O混杂。
- 闭合后新增只读诊断58b817dbd89e00c41ee2a7cb169011371b244113：live_queue_efficiency检查有空许可仍排队的时间；live_feedback_diversity核每run有效返回的代码/提交逐字节重复和反馈到达面积。仅旧门外描述，不替换门、不把任务槽秒当GPU节省；本地45测试/42通过/3Linux跳过。未运行v7分析writer。
- 17308强参照source4a19588cb24cea8ed1d1b91f563d4ed06a68f4af、plan783934f461321858efbca68c9b70505323729ba921f6c9aba002ff4c42f38c5c；root=/research/d7/spc/yzyang4/scheduling-neural-width-20261009-v1。两既有神经程序各两实例，width1/2/4×3轮Latin顺序=36执行；同seed42/训练量/单3090/6物理核≤90min/1.5GPUh，非新任务/seed或live质量。6209prepare已exit0/完整preflight并hash核验；43136submit已exit0/job17308。17:08附近最后核RUNNING，预热完整、block0四worker就绪/首程序执行；尚无正式完成结果。禁止重投。
- width暂存=/research/d7/spc/yzyang4/scheduling-width-20261009.kdFBrQ；本地10测试9过1Linux跳过。首次远端测试误早于SCP完成（test_width_runtime缺失，8项1error），不算通过；上传会话98854已exit0，主脚本/contract/readout/runtime-test四hash匹配，16:04重做正式Linux测试会话88417最终exit0、10/10通过（13.438秒），含真实flock三宽度。无GPU或候选执行。
- width准入在原worker外：四内核共同ready屏障后FIFO借还1/2/4，成功退出清理后释放，失败停后续不补样；保留原worker/程序AST。新增共同实际_gateway_port绑定，避免复用旧无效_slurm_gateway_port覆盖；闭合后核实际子进程端口互异。当前源码pin7577a95230515790ce58966bf5c6d3f486a6f6535d83503862aa8e80e6b33338。
- 16:45在v7成绩未读前提出条件追加live廉价强参照：2对4许可，另16条/新seed144901–144904及145001–145004/同ABBA、同任务/模型、600s/1320s池槽，3GPU90min≤4.5GPUh。仅v7全16完整+结构通过且width全36输出/步数/隔离通过才准备提交；不看先前效果正负，不替代旧批次。source f13dfb005276bb34f5176075633adec3494f5a66，stage=/research/d7/spc/yzyang4/scheduling-live-width-20261009.hyHQwJ；本地49测试46过/3Linux跳过，remote21/21通过(会话26113 exit0)，4源码hash相同。未prepare/提交；不晚于18:30提交以留收尾，不能为赶20:11延长预算。全部可启动批次最坏本窗≤10.7875GPUh，并非实际已用。
- 17308监视入口stage/kdFBrQ/neural_status.py --kind width（只读，未改冻结root）；闭合后root/width_readout.py一次写readout-v1，须等Slurm终态再读效果。v7三份预设诊断已执行一次；新增readiness-diagnosis-v1为看到首块121秒后做的事后检查，明确不能替换原门。

## 上一批新证据与修正（已闭合，不能重开）
- v4/17255于13:59:17资格门停止：4/16正常收尾、3有效终点、4有效候选；余12未启动，0观测A/B配对，原门false。3×1105=3315GPU秒=0.9208333333333333GPUh；这是14:11窗口之前的成本。
- v4 root=scheduling-live-search-20261009-v4；source e3e93d788cc6d8775d441d6945cf08529df5c4fd；plan6a91d2934959681b977d2d43ca0ea991dd6a1d3b0ce65ab6d1a88a7b5225d025。readout-v1、phase-analysis-v1、diagnosis-v1均已一次写出，禁止重跑。
- 本地证据sandbox_scheduling/live_v4_closed；summary SHA f54f3501b0d87ebd0681b31481fb3e053db70a95e78ed2ae51451c3b4083cdb6，closed SHA2bfd41a3babee547bb58fc3653b6cd3550510101ac9bf1c6d0253b2d4c49a785。6份下载hash与现场相符，PowerShell独立复算16/4/3/4及3315通过。
- 一个超时候选租约约289秒；三个run第二候选排队273.8312957799062/275.5957983350381/273.134565920569秒，共822.5616600355133任务槽秒（不是GPU节省）。三run总排队308–330秒，另一run总租约359.91306385118514秒且0有效。
- GPU573个采样中利用率中位0、最大7%，显存最大266MiB；这是执行队列拥塞线索，非GPU计算占满/共享收益/最终质量因果证据。两个小NLP开发任务不替代神经训练泛化。
- 原读出器错误要求服务step=执行step、affinity逻辑CPU数=6；现场同job/服务step1/执行2/GPU分离、12逻辑线程，节点SMT2。旧摘要保留；未来v5用sysfs物理核与独立步骤/GPU身份核验，完整合成读出/反例已测。不借此改v4原失败门。
- 旧v3/17232在gpu24 native CUDA失败，16条0开始；17232/17234/17235/17250共21GPU秒；v2/17229排队取消0GPU；v1准备后撤回0GPU。都不复用预算/重开writer。
- gpu27迁移诊断17251因未等SCP完成失败1GPU秒，17252 native成功1GPU秒；工具返回session_id须等待退出，再验证hash后执行依赖。不得重演抢跑。
- 初次新增整批合成读出测试遇Windows系统temp权限问题，fixture改为workspace后通过；不是GPU/候选失败。Git commit伴随sh.exe环境警告，不能宣称hooks通过。

## 保留的正信号与论文边界
- 17128：12/12，两固定神经程序，pipeline/share2三配对1.2672909369785448/1.6617137953073626/1.6730949919847078；中位1.6617137953073626，sample std0.23107569245795057。150/640步和数值输出一致，资格＋正式1204GPU秒；同seed重启、非独立训练seed或live质量。
- 证据evening_overlap_v1_closed；source22566d06fc8de23d6c16cc2bd4a85b0858af0d66，summary c763de7c8ee00db5d4ba4219d49c4d864e573061368be9566f7d48d4cc0bc258；完整独立审计已通过，不重复基础验收。
- 17017大输入12/12中位serial/share2=1.6811874366439696，但参照较弱；16997四小程序36/36强参照中位1.3177936445362894。不可拼成新神经强参照。17014/17021等失败全部保留，详见CURRENT_DIRECTION/旧交接Git。
- SchedMate已有源码/历史/日志调度与干扰撤销；MARS调度论文已有跨阶段遥测、AIMD准入与continuation优先。不能把队列阻塞、动态准入或适用MLE当首创；尚无胜这些强参照或重要新方法的确认。

## 恢复与安全
- 17:14己方已安全快进push到624f41afee10d7ce85b2732ea4a7b35df511e403（含58b817db/4a19588c/f13dfb及v7安全闭合）；4提交32文件安全扫描0凭据命中/0敏感文件名，未上传raw候选/标签/预测。17:33fetch仍相同；senior a5519bc8e0c85d0a3bd78c478ac8332120d415d9(15:42)，仅读提交/path元数据，更新属offline-GRPO/数据处理，未读raw文档或改分支。17308闭合待另commit。
- 未跟踪报告phase1/reports/给学长_MLE沙箱资源调度进展_20261009.md是用户上一轮要求、13:01版本，保留，不冒充最新或主动另写长报告。
- SSH linux5；PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。gpu27/gpu28 RTX3090已知兼容；不投projgpu39、不改驱动/权限或静默退CPU。旧Held12535不动。
- first-960/Target-300/Target-522、D_val、官方test继续关闭；16560数值导出仍待单独授权。不输出密钥/raw候选/回复/预测/标签/权重；不使用付费API、不更新agent底座。
- 研究盘总配额4TB、至2027-08-30；共享文件系统df余量不是用户配额。长期经验索引在旧checkout的phase1/memory/MEMORY.md，按需读取。
