# 当前短交接
更新：2026-10-11香港12:16:55工具观察；本窗06:37:30–12:37:30。GPU实验已全部闭合，只余旧Held12535未动；不新建automation/thread/goal、不承诺无人运行的后台实验。
恢复：fetch → CURRENT_DIRECTION → ROUTE_DECISIONS → 本文件。旧8月任务不恢复，未核现场的状态一律“最后观察”。

## 当前任务与硬边界
- 当前R14；本窗优先定位学长六并发resource unavailable、帮助其既有policy实验；调度保留探索，不将可靠性修复冒充质量/方法突破。
- 用户广泛批准，但新批仍先公告矩阵、完整资源上限、停止门。学长两卡模型服务六卡MLE/medium只是建议，尚未完成真实2+6容量验证。
- 不更新agent底座、不改学长分支、无付费API；first-960/Target-300/Target-522、D_val、官方test、16560数值导出仍关闭。旧HCE/多保真/Probe/TD等不自动恢复。
- 活跃checkout=C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001；detached HEAD有意保留。旧aira-dojo-codex-20260813用户dirty不动。
- 最后公开且ls-remote核验e6ac9a06400717d8ed8335141ad468c91fdcc230；学长仍f7ccd79323112b10ccc82d8e9ec9d6cf089df607。17571/17575/17576数值回执、窄补丁边界与2节点代码已发布；26blob凭据/敏感文件名/字节差异0。hook MSYS警告不称hook通过，独立guard通过。用户报告未stage。
- 用户未跟踪报告phase1/reports/给学长_MLE沙箱资源调度进展_20261009.md保留、不stage。旧长细节Git b24及原实验目录可恢复，不覆写原件。

## 现场：17570六卡14/14；17571两服务+四执行卡10/10；17576原factory6/6
- 最后17566：10计划/6尝试/5完成/4未开始，785GPU秒；root=/research/d7/spc/yzyang4/resource-execution-stack-capture-20261011-v1。失效仍发生单卡，不能归因六并发。
- plan SHA4741e0748c51affd413700690d1f3f24e879c522f194b74e5226a63917ca27b8；最多10次串行UNet原seed42/588步/450s，gpu3一卡4物理核最多30min≤1800GPU秒。首失败闭合、不补样本；无模型/API。
- 17565已闭合14计划/8尝试/7完成/6未开始；失败index5两次握手均正常，候选调用452.858323012013秒超时；没有线程创建/OOM枚举报错。7完成均588步，21输出比较全字节一致，仍不称六并发门通过。
- 17565 source/input/image未变；原CLI与client观察器可能影响时序。失败时gateway收到2个execute、仅1个execute_reply（prelude）；候选尚未产出文件。源码DataLoader num_workers=2，仅为假说线索。
- 17566只在prelude加30s父内核堆栈watchdog、分配卡内部2s NVML；父堆栈不含DataLoader子进程，采样不是GPU kernel时间。source原样、不改线程或训练参数。
- 17566审核已完成且gate false，UID峰243、清理3/3/0；GPU失败期间采样237/237、中位0，后期显存4MiB。单次30s堆栈不完整且不再更新。末次观察内存failcnt/pids.events无增加（有不可读祖先），不排除其他故障。
- 同分配内Slurm零GPU只读进程核查：gateway子进程启动晚于候选，疑似死亡后重启，确切退出码未采到。不能说DataLoader死锁/历史OpenBLAS根因。节点SSH主机验证未通过，未禁用验证；改走本作业Slurm诊断步。
- 17567 resource-execution-exit-capture-20261011-v1：plan64d4d03d1b4513bfac11518736671031691f334334195e134eab564ba99931f0，原样UNet串行10/10、578GPU秒；30execute均完成，UID峰286、无执行中非零exit。去faulthandler同时加退出观察器，不能因本批成功就归因旧watchdog或称根治。末13进程47线程含同时17568，不作泄漏结论。
- 17568 restart-guard-v1：12计划/4尝试/3完整/8未开始，163GPU秒；旧exit17等16.388614677125588秒超时，新guard于2.371317527955398秒收到真实parentless restarting并返回非timeout失败，但清理HTTP500。原门false保留。
- 精确栈：Jupyter8.9.1 MultiKernelManager._async_shutdown_kernel在restart的ready Future未完成时调用exception()→InvalidStateError；关闭server也触发，120s后强杀。新增窄gateway覆盖只在delete前等ready≤15s，不升级image、不重执行候选、不吞错误；8异步单元+2矩阵测试、原CLI无内核预检通过。
- 17569 resource-restart-guard-trial-20261011-v2：plan4a27286e2480951f8b0114107f751e3cc8685a2317226038dccf22430f979929，12/12、129GPU秒；正常六输出相同，exit旧中位16.39422196894884秒、新2.385627934942022秒，SD0.014168659872206123/0.0386125174152679；guard清理中位0.3674750328063965秒、无500/InvalidState/强杀，UID前后5进程8线程0zombie。原错误仍是已知人工exit17，非EAGAIN根因。
- 17570 resource-execution-guarded-six-20261011-v1：pland96fba91f303325714b8a7320571776cbec66a87ccaa45f12d01afd5a2b418a5；完整14/14、全部588步、42execute、91输出对字节一致、两块各6独立GPU/24物理核、UID峰358、末3/3/0，无非零exit/关闭竞态。1428GPU秒≤10800，独立gate true；模型不在本批。audit966ccfa1cce5888a4dbe18429406fe2ffe7ab17ac11c1738112d4cc949478d23、CSV9f50307c818fbaa1264cfaa3777c99796ff1d09cf5b3d00919afc179d3b5a2e5远近一致，审核已写勿重写。
- 新resource-joint-four-capacity-20261011-v1：公告固定10程序+10本地请求；2串行、两组4并发，CNN150/UNet588步各5次，原seed42/450s/source/input/image；2服务+4执行GPU/24物理核/40min≤14400GPU秒。原模型medium/seed49/max512，无付费API/底座训练，首失败闭合，不补样本。可用普通分区暂无8张健康同节点空闲卡，不能称2+6。
- 17571已独立闭合10/10、10/10本地请求，planfb949c4c6cbe9ee5d02ae467e45a08fb3b1409e01530555d4b0ccf7bdaaab0b2；原150/588步、20对输出字节相同、执行观察完整、无资源/清理错误、UID峰510末3/3/0，8508GPU秒。2+4四程序host optimizer窗口峰2，不冒称四GPU同步计算。audit C4E437D5E5FACD82235DFCCB3AC7DAAA5DDAE31428B35978F83D528673644743、CSV0521939ED6DC6E500BBDFCE7C9683F78B4A803F3900DC7CBF5B6FB045B342170已取回；审核writer已完成，不重写。watch54746完成。
- 17575 factory-v1闭合6计划/1尝试/0接受，6GPU秒、无guard回执。配置UUID与host Slurm数字mask触发原隔离guard；这是我方harness接线错误，不删guard/不撤隔离。旧批只存ValueError无栈，原因通过精确guard另行复现，不冒称观察旧栈。
- 17576 factory-v2闭合6/6、191GPU秒；3原UNet/3已知exit17交替同workspace，三588步输出与17570固定参考字节相同、6新receipt，退出中位1.607325836084783s、SD0.15274187894372407，无500/InvalidState/强杀，owned谱系干净。plan0772f12abc510953140ecb13ddbb3574ce629ee995b25e8efcb783a4d336db52，audit3cf77eee8e6badad878fa37c5c8d8136caf28c29988a13d2bb3cc60b9ea2f3f3、CSV82d783b968fd362494b96318097fd6900e61dd073c3896dd671e7dbbbfefab73远近一致；审核writer已完成勿重写。
- 17577 joint-two-node-v1已失败闭合：14程序/14请求均0开始，第二节点sampler步骤在完整launch前aborted，无Python栈；原controller/allocation闭合缺失保持缺失，独立failure-reconciliation-v1留全14分母。planec40294858e917ba4a773af69f50c6ca8998193388db80973b6154b474502dc7；scheduler448GPU秒，计至最后extern清理的保守包络952GPU秒≤19200；非实际账单证明。failure审计372567bcc0ee7684bcb4b34a4d883033471e3ceeeab4dd9d6221edc1101d2c35远近一致，未重开、2+6仍未过。
- owned_process_pressure原6解析及3子进程NPROC测试通过，receipt b1ac8f02e099a2b043cca69ad57adb3a374dcde9d2026b13c01ae00601a34d87。新增可选owned_pressure_monitor/owned_cgroup_pressure：限定已知host PID、0600不覆盖、退出/僵尸/PID重用即停，目标cgroup与observer分开，未知不填0；16测试WSL/远端都过、SHA相同，见owned-monitor-validation-v1.json。未自动部署/改限额/读cmdline/env；旁路增加进程和CPU/IO，比较中须对称启用并计费，不能作为历史EAGAIN因果证明。
- 最小补丁collaborator-patches-v2独立index应用/3精确f7故障单元通过，ready/client与17570字节一致；17576已核原factory正常/已知exit路径，两finally特殊异常仍仅单元。B须配gateway guard；unique回执变体ac890ba1a61d371e04f8c1b8faec87b20d64b10a10c95b027656745baa36313e修旧同目录二次FileExistsError。validation-boundaries.json已据实更新，未改/部署学长分支。

## 本窗已确认的工程事实与未解决问题
- 共享mle/comparison/1009八包已定位；Spooky/Dog各一精确日志SHA独立复核，OpenBLAS pthread_create失败，NPROC soft1024，请求线程分别3/12。原始日志仅远端内存凭据先筛，不导出代码/标签。
- evidence.json及stage-localization.json/error-origin.json：首错误跟在Executing code后21/10行、无中间代码fence；支持执行/import阶段，计数可能重放，不能证明1024命中或就是学长所说六并发事件。
- 缺故障时host同UID总线程、cgroup pids/memory事件和残留谱系。OpenBLAS会对多种pthread错误打印NPROC；不盲升unlimited、不清别人进程、不把容器PID总数当hostUID总数。
- thread-setting-hints-v2复核：Spooky故障前最后startup段无线程设置literal；Dog段含torch.set_num_threads(2)、num_workers=0，不能由此认定实际生效或DataLoader耗尽。旧n_jobs=-1计数混入历史echo，不作失败程序证据；跨库线程池也不能仅凭torch限制判定BLAS已限。原错误仍未获故障时证据。
- 当前Drive元数据comparison最新仍1009；mlebench/spooky下为prepared数据，不深入其标签。目录列表不保证完整。
- 已实证stdout就绪bug：select(fd)看不到TextIOWrapper预读行，单reader+队列修复，真实OS管道5项和精确f7既有单元11项通过；17543真实14/14。此层不同于kernel-info握手，更不是历史EAGAIN根因。
- 两个finally清理缺口已有3故障注入回归，未证明历史资源耗尽因果；生产默认factory会关闭kernel/server，不得又称必然跨候选泄漏。
- 17555/17561及旧17322/17326仍有kernel-info失败；旧重询曾120次无reply，不能把再发info当新解法。旧gateway观察器被Jupyter CLI exec丢失，旧48计数缺失，修正解释已保留。
- 17556正确直接入口48/48，17563同入口192/192，17564保留原CLI+sitecustomize观察48/48，均没有复现；全有forwarding计数，不是根治/失败率估计。17563/64末均5进程8线程0zombie、UID峰256。
- 原任务镜像版本kernel_gateway3.0.1/jupyter_server2.20.0/jupyter_client8.9.1/ipykernel7.3.0/pyzmq27.1.0/tornado6.5.7；WebSocket.open已await connect，nudge已有2026FD修复，CLI与直接入口同conda解释器。不要盲升镜像/Torch或套旧issue。
- 17559发现gpu1一分配槽（STEP_GPUS=3，不推物理编号）宿主/镜像×默认/撤mask四组合全cuInit100；另七槽单GPU算术正常。设备门false，不冒称17557也是同数字码；不reset/改权限/绕cgroup。
- 单纯主进程导入数学库帽3/未设/未设/3，线程7/25/25/7；无训练，只是线程余量线索，不是六并发修复或性能结论。
- 本窗新增源原46项指定Linux回归通过；本段另15项通过。首次WSL两项git-show失败是Windows worktree指针不兼容，测试进程指定Linux GIT_DIR后通过，不改实验源码/不冒充生产实验。
- 学长9/24已有mlebench_multiprocessing_resource_limits.patch提示math线程≤4、torch8、loader≤4；当前src只找到patch，不能由此认定生产已应用。LOCAL_VLLM_SERVER.md凭据形命中，原文输出已抑制，须远端脱敏后读。

## 所有失败和实际成本保留
- 17541：14计划/7尝试/6成功/1服务器readiness超时，132GPU秒。
- 17543：stdout修复后14/14，102GPU秒；17545：--exact不支持、模型前失败，10GPU秒。
- 17547：两GPU服务+CPU六内核，14/14内核与14/14请求，UID峰561、清理后3/3/0，1078GPU秒；不是六GPU训练。
- 17550：14计划/1尝试/0完成，遗漏input_cache；原错误没保存不可断言精确栈，4120GPU秒。零GPU原镜像路径复现FileExistsError；17552补私有空缓存后两原程序150/588步合格，496GPU秒。
- 17554：14计划/1尝试/0完成，首CNN450s超时、六路未开始，7720GPU秒；不改时限换源救原门。
- 17555：192计划/6尝试/5完成、首轮kernel-info失败，132GPU秒；17556：48/48正确观察，162GPU秒。
- 17557：UNet收窄14计划/8尝试/2完成/6未开始，六路展开cuInit失败，4512GPU秒；2请求均length结束，不是完整agent回答。
- 17559：八槽×四探测32/32已采集，一槽全失败，200GPU秒；17561：14计划/1尝试/0候选执行/0完成/13未开始，kernel-info120s失败，UID峰47，804GPU秒。
- 17563：192/192，586GPU秒；plan3ea942591218aa1be21ed1c68083aa3fbd4b9bb7e3acf669d7880ba6c7c85485，audit ccb036af7a485c465bd3d8ba527b37820a06af16b419708fefe7c4c08e43fd1e远近一致。
- 17564：48/48，148GPU秒；audit f3033b5b24bffe93ea3cb36ffa6d1f1708c7fc8956e491caaa96e0c136bb4356远近一致。17565：7/14，3576GPU秒；audit 0a601ebff94e499cab8fd8fc5a4e6433097fe4d678a006dbeb7136202c955222、CSV 94cce2af727618e3600414469acf38ed18901847d22c247055807d28ed5a0f8b均远近一致。各原门/上限不合并，不手算commit数字。
- 17557 audit e63264ddff2ade46395201da28d05a9bf2fb3253a4dac5ff1c83f51eeadee60a；17559 audit742ea8631fb3e747c9bb5399a155457963da63ef6b32760cea51886d94a155e4；17561 audit b38a53aeafaf90ddcea1d0c90992ee58738259f1034f29bf2fc53e86afd38a53，均远近核验。
- 17578派发诊断6计划/2尝试/1通过：同分配gpu3的/bin/true通过、gpu27空命令超时；17579 gpu27本地4/4空命令通过（含零/一卡步骤），并非CUDA兼容性验收；17580两固定跨节点零/一卡空命令0/2，launch RPC rc0后无task完成。确认新跨节点启动问题独立于Torch/模型，不是历史EAGAIN同因。三批成本scheduler82/2/162、含清理包络208/2/288GPU秒；已闭合、勿重投。0GPU提交被ratio拒绝、ex_gpu不存在、仅gpu权限，无作业且未绕过。

## 科学边界与旧结果
- 10/10五job总29857GPU秒。10/11截至17580共27闭合job：scheduler36260GPU秒=10.072222222222223GPUh；计至最后step结束的保守包络37030GPU秒=10.286111111111111GPUh。window-cost-final-v1.json关联原24job及三个新审核SHA；旧elapsed-only回执不改，清理包络不等于实际计费。无付费API/底座更新。
- 17366两原任务家族新变体12/12，pipeline/share2中位1.248439822872127，SD0.17052995413242686，固定查询六输出/源相同；CNN时序漂移，非跨seed/全任务质量/一般phase-aware强基线。
- 17368 live16尝试15正常，有效反馈池差-4/+5；仅3/8双方有效成绩对且全负，原门false。允许两种可用性解释全8配对仍2胜5负1平；不换主门、不把8run当8独立池。
- 17376/17380反序失败无有效配对。当前不扩大文本live配方或复杂LLM调度；SchedMate/MARS/Synergy等已覆盖广义共享、语义、干扰和阶段控制。没有新方法收益确认。
- 12:07已异步请求用户转管理员核17580.0/.1（香港12:02附近）的slurmd/stepd与启动回连；无回复前停此两节点路线，不改限额/网络、不再拿模型撞启动故障。历史OpenBLAS仍缺producer故障时UID/cgroup/内存数值，不能以我方线程帽6的成功batch替代因果复现。后续科学验证仍需代表性真实GPU开发负载/强参照/全池成本，公开fixture不是质量基准。

## 路径与操作坑
- SSH linux5；PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
- stage=/research/d7/spc/yzyang4/resource-diag-stage-20261011.M5wKjU；本地临时工具=_codex_tmp/resource-availability-20261011。
- 原task镜像SHA801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda；模型与真实任务CUDA分开验收，不投projgpu39，不静默CPU回退。排除projgpu7/8/33、gpu36/38；gpu24旧cuInit999不重投。
- Slurm19.05.4无--exact；hint=nomultithread按物理CPU集合验收；>6且≤10CPU/GPU需highcpucount。gpu35等课程卡QOS未授权不可借用；prod32属farnia不是普通gpu队列。
- 研究盘4TB至2027-08-30，不是实时余量。凭据只远端批准.env，不回显/导出；共享原材料先凭据扫描，日志只枚举输出。
- SCP返回session须等exit0；共享盘重hash不要与计时GPU候选重叠；审核writer只运行一次。
- Windows沙箱asyncio单元测试挂起，已只终止我方指定PID264344；WSL需权限，8项异步测试真实通过。Linux-only resource模块不能用Windows套跑；不要再把这两种环境失败解释成实验失败。
- 发布只显式stage我方文件；扫描暂存及所有未发布blob、敏感文件名、Git/本地/远端字节。无force push、无学长分支修改。hook历史MSYS警告不是hook通过。
- 用户授权耗尽后本窗已消费一张现有重置卡，未购买；不要因上下文长再消费。无变化轮询不是进展。
