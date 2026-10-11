# 当前短交接
更新：2026-10-11香港09:50附近工具观察；当前六小时窗口06:37:30–12:37:30，继续会话内工作，不新建automation/thread/goal。
恢复：fetch → CURRENT_DIRECTION → ROUTE_DECISIONS → 本文件。旧8月任务不恢复，未核现场的状态一律“最后观察”。

## 当前任务与硬边界
- 当前R14；本窗优先定位学长六并发resource unavailable、帮助其既有policy实验；调度保留探索，不将可靠性修复冒充质量/方法突破。
- 用户广泛批准，但新批仍先公告矩阵、完整资源上限、停止门。学长两卡模型服务六卡MLE/medium只是建议，尚未完成真实2+6容量验证。
- 不更新agent底座、不改学长分支、无付费API；first-960/Target-300/Target-522、D_val、官方test、16560数值导出仍关闭。旧HCE/多保真/Probe/TD等不自动恢复。
- 活跃checkout=C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001；detached HEAD有意保留。旧aira-dojo-codex-20260813用户dirty不动。
- 最后公开且ls-remote核验b24c8b933836fd6c819c24af110aedeb26e45171；最近fetch学长仍f7ccd79323112b10ccc82d8e9ec9d6cf089df607。新本窗文件待发布，不能称已push。
- 用户未跟踪报告phase1/reports/给学长_MLE沙箱资源调度进展_20261009.md保留、不stage。旧长细节Git b24及原实验目录可恢复，不覆写原件。

## 现场：17566单卡堆栈诊断，其余本窗作业已闭合
- 最后09:50：17566六次候选已开始、五次完成、未闭合；root=/research/d7/spc/yzyang4/resource-execution-stack-capture-20261011-v1。
- plan SHA4741e0748c51affd413700690d1f3f24e879c522f194b74e5226a63917ca27b8；最多10次串行UNet原seed42/588步/450s，gpu3一卡4物理核最多30min≤1800GPU秒。首失败闭合、不补样本；无模型/API。
- 17565已闭合14计划/8尝试/7完成/6未开始；失败index5两次握手均正常，候选调用452.858323012013秒超时；没有线程创建/OOM枚举报错。7完成均588步，21输出比较全字节一致，仍不称六并发门通过。
- 17565 source/input/image未变；原CLI与client观察器可能影响时序。失败时gateway收到2个execute、仅1个execute_reply（prelude）；候选尚未产出文件。源码DataLoader num_workers=2，仅为假说线索。
- 17566只在prelude加30s父内核堆栈watchdog、分配卡内部2s NVML；父堆栈不含DataLoader子进程，采样不是GPU kernel时间。source原样、不改线程或训练参数。
- stage/stack_capture_readout_20261011.py已记录launch及审核器hash；观察exec17737。结束后audit只运行一次并核远近hash。旧Held12535不动；不重复提交。只读跨step GPU查询此前失败，原因未捕获，不作零利用率。

## 本窗已确认的工程事实与未解决问题
- 共享mle/comparison/1009八包已定位；Spooky/Dog各一精确日志SHA独立复核，OpenBLAS pthread_create失败，NPROC soft1024，请求线程分别3/12。原始日志仅远端内存凭据先筛，不导出代码/标签。
- evidence.json及stage-localization.json/error-origin.json：首错误跟在Executing code后21/10行、无中间代码fence；支持执行/import阶段，计数可能重放，不能证明1024命中或就是学长所说六并发事件。
- 缺故障时host同UID总线程、cgroup pids/memory事件和残留谱系。OpenBLAS会对多种pthread错误打印NPROC；不盲升unlimited、不清别人进程、不把容器PID总数当hostUID总数。
- 当前Drive元数据comparison最新仍1009；mlebench/spooky下为prepared数据，不深入其标签。目录列表不保证完整。
- 已实证stdout就绪bug：select(fd)看不到TextIOWrapper预读行，单reader+队列修复，真实OS管道5项和精确f7既有单元11项通过；17543真实14/14。此层不同于kernel-info握手，更不是历史EAGAIN根因。
- 两个finally清理缺口已有3故障注入回归，未证明历史资源耗尽因果；生产默认factory会关闭kernel/server，不得又称必然跨候选泄漏。
- 17555/17561及旧17322/17326仍有kernel-info失败；旧重询曾120次无reply，不能把再发info当新解法。旧gateway观察器被Jupyter CLI exec丢失，旧48计数缺失，修正解释已保留。
- 17556正确直接入口48/48，17563同入口192/192，17564保留原CLI+sitecustomize观察48/48，均没有复现；全有forwarding计数，不是根治/失败率估计。17563/64末均5进程8线程0zombie、UID峰256。
- 原任务镜像版本kernel_gateway3.0.1/jupyter_server2.20.0/jupyter_client8.9.1/ipykernel7.3.0/pyzmq27.1.0/tornado6.5.7；WebSocket.open已await connect，nudge已有2026FD修复，CLI与直接入口同conda解释器。不要盲升镜像/Torch或套旧issue。
- 17559发现gpu1一分配槽（STEP_GPUS=3，不推物理编号）宿主/镜像×默认/撤mask四组合全cuInit100；另七槽单GPU算术正常。设备门false，不冒称17557也是同数字码；不reset/改权限/绕cgroup。
- 单纯主进程导入数学库帽3/未设/未设/3，线程7/25/25/7；无训练，只是线程余量线索，不是六并发修复或性能结论。
- 本窗新增源已运行46项指定Linux回归通过（含堆栈解析/单卡接线），单项远端预检按各receipt。不是46次生产实验。

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
- 所有本地安全产物在phase1/sandbox_scheduling/resource_unavailable_20261011；细节/原份/root在各审核JSON，失败未覆盖。成功候选原term_out覆盖不足已声明，0成功时warning_coverage=true只是空集真。

## 科学边界与旧结果
- 10/10窗口已结束；五job17364/66/68/76/80总29857GPU秒。详细旧短交接在Git b24；原证据未删除。
- 17366两原任务家族新变体12/12，pipeline/share2中位1.248439822872127，SD0.17052995413242686，固定查询六输出/源相同；CNN时序漂移，非跨seed/全任务质量/一般phase-aware强基线。
- 17368 live16尝试15正常，有效反馈池差-4/+5；仅3/8双方有效成绩对且全负，原门false。允许两种可用性解释全8配对仍2胜5负1平；不换主门、不把8run当8独立池。
- 17376/17380反序失败无有效配对。当前不扩大文本live配方或复杂LLM调度；SchedMate/MARS/Synergy等已覆盖广义共享、语义、干扰和阶段控制。没有新方法收益确认。
- 若继续科学验证，先代表性真实GPU负载、独立dev合法性、廉价阶段准入强参照与全池成本；当前公开神经fixture只能做数值一致性。

## 路径与操作坑
- SSH linux5；PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
- stage=/research/d7/spc/yzyang4/resource-diag-stage-20261011.M5wKjU；本地临时工具=_codex_tmp/resource-availability-20261011。
- 原task镜像SHA801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda；模型与真实任务CUDA分开验收，不投projgpu39，不静默CPU回退。排除projgpu7/8/33、gpu36/38；gpu24旧cuInit999不重投。
- Slurm19.05.4无--exact；hint=nomultithread按物理CPU集合验收；>6且≤10CPU/GPU需highcpucount。gpu35等课程卡QOS未授权不可借用；prod32属farnia不是普通gpu队列。
- 研究盘4TB至2027-08-30，不是实时余量。凭据只远端批准.env，不回显/导出；共享原材料先凭据扫描，日志只枚举输出。
- SCP返回session须等exit0；共享盘重hash不要与计时GPU候选重叠；审核writer只运行一次。
- 发布只显式stage我方文件；扫描暂存及所有未发布blob、敏感文件名、Git/本地/远端字节。无force push、无学长分支修改。hook历史MSYS警告不是hook通过。
- 用户授权耗尽后本窗已消费一张现有重置卡，未购买；不要因上下文长再消费。无变化轮询不是进展。
