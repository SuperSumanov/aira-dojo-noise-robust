# 当前短交接
更新：2026-10-12香港05:24。压缩前完整交接保存在Git dcb0975864d53307c57d07c214f1a313ba6b27f5。
恢复：fetch → CURRENT_DIRECTION → ROUTE_DECISIONS → 本文件；未复查的动态状态只写最后观察。

## 最新用户请求与本轮完成
- 新请求是三小时内真实同预算效果验证，不能再只筛轨迹，窗口约04:30–07:30。48续跑/6池=2任务×4seed×3臂×2重复，ABCCBA；1020s/run、每任务生成2/每卡执行1三臂相同，2+4GPU。原窗口cap8400秒×6=14GPUh；v5仍1180s/池，作业cap7560s，加前败476+353s，合计cap13.981666666666667GPUh（4974已耗GPU秒）。
- **17673已FAILED闭合**，不是仍运行：04:56–05:03:56，476秒×6=2856GPU秒。首8条在生成前IndexError、候选0/48、其余池未启动。根因是暖起点append后先递增current_step再原生log_journal，越界；原CPU检查错误地stub掉日志，漏过。旧v2/root与planSHA18257b6b24b195332723004d0271d1a2ff2049174c07dbe588d25f5f6d8e4c3c原样保留，不重开该批/不解释为方法结果。
- **17674已取消**：05:14:08–05:20:01，353s/2118GPU秒。冻结源码检查发现parse包装器用evaluation形参，但原生按eval_result关键字调用；先于结果判读主动停止。结构8起点加载、4生成获准、0轮完成，旧计划48保留，无closed.json，不冒称完成读数。v4原planSHA8aace9d8d65a190a7da2efc573766fcc5ea287c60d61738a3cf7c6b57b9ab8ff不改。
- **v5完整CPU门已过，单次submit会话36471进行中，尚无新job**：source e180a0b5e8289c99bad27872fd63629e7421d8ff；root=/research/d7/spc/yzyang4/scheduling-generation-joint-20261012-v5；planSHAe923a7eefe6b69fdf9416bed58cab10218553760351022cc0b31920d039c32db。24单测/48配置/32配对，真实expand→task返回→parse关键字→analysis→journal/backprop→debug→checkpoint通过，仅模型/执行在CPU fixture中合成。三臂策略/任务/seed/run/池未改；闭合前不读成绩，不重复submit。v1/v3仅CPU失败零GPU，原件保留。
- stage=/research/d7/spc/yzyang4/gen-joint-stage-20261012.NvlXeX，内有结构状态、闭合后readout及joint_submit_fresh_hash_20261012.py。后者新鲜并行计算所有镜像/权重SHA、核对读取前后stat再调用原提交门，不是跳过或复用历史哈希。只提交一次；先等prepare成功。读数尚未执行。
- 最近核实公开head5bc75e860788f1412aca6719ea457075bcc226d0，已push并ls-remote核实；随后v5修复本地e180a0b5尚待发布。独立发布guard此前全0，Git旧MSYS hook报错没有伪称通过。学长dojo-reproduce仍64fd78e98cfdc945b1af03f29f570975d58b88b7未改。
- v1 CPU前检失败于search_policy实际返回path却断言node，未提交GPU；完整v1原件保留，不重跑该prepare。v2修断言，并真实stub一次原生_improve许可接线；三臂共同去掉已知LLM is_bug误否决，外部评分/exit/有效提交门不变。
- 起点固定17592按run/step序首个accepted且外部ground节点，原始程序与输出不导出。新终点含起点，主分析看两任务/两个池重复joint相对两个参照的终分差；历史起点构建是共同已有资产，不计作在线节省/从零E2E。仅小型明确成本/资源baseline适配，不能冒称完整论文复现或已确认创新。
- 前轮04:26机会筛查已闭合：17592/17656/17670分开分析80run/40队列，候选稀缺选择均0，仅2次preview竞争；journal Improve1/0/0且accepted均0。21单测和独立复算通过，该轮零GPU、原质量门不改。它解释了为什么这次将干预提前到生成端，不是新质量阳性。
- 前轮本地产物sandbox_scheduling/opportunity_screen_20261012；screenSHA c1cb507322bf01065cb673221471c6007eb8c06bd3de856c69e01b0e26331abd；verifierSHA0e440c9bf30aa0ee02836264efb14b1b55db2a7f9bbb3d420ccd1af84431cb8d。远端/resource-diag-stage-20261011.M5wKjU/opportunity-screen-20261012.q7Tlx8位于研究盘根下，不覆盖或重跑旧输出。
- 已再核CostAda v4（2607.26828v4）、MARS（2604.26963v1）、SAGA v2；收益/成本、预算预留、续轮与动态资源准入均有近邻。当前只是资源状态附加项的受控试验，不承诺新颖性；小型适配不能冒称完整强方法复现。

## 独立重复17670：已闭合，不再提交
- 32/32开始/结束/清理：2任务×4新seed×2臂×2池对，ABBA240/600/600/240；900s/run、300s候选、1500s池、2服务+4执行。最后核COMPLETED，6005秒×6=36030GPU秒=10.008333333333333GPUh，cap10.2。
- 600/240正常16/3、原生有效终点4/1、首生成失败0/13。仅1/4池任务终分可比：aerial 600−240 AUC=-0.0001309579170742925；0/16同seed质量对，冻结质量门false。缺失不填0、不合并17656、不补seed救门。
- root=/research/d7/spc/yzyang4/scheduling-image-deadline-replication-20261012-v1；source13f8ebcb1cd76ca210aacf5c7f43ea2d086d7f85，planSHA23f368399f6c735ef81142ec46831ae4e9f45d58d80edf5d2559b4cbb7a22ea6，summarySHA99ae98964305d29a444d7d5ba86c347395f70ef96280e2cf53b47491c5ae569c。
- PID317337一次性closure已结束，禁止重启动prepare/submit/finish/analyze。6评分重算、16CPU对/4池同物理lane与服务卡、独立JSON/CSV/成本复算通过；本地image_deadline_replication_v1_closed。
- episode3有外部有效exit0提交，却被实际冻结MCTS的LLM is_bug条件否决；journal非导出漏记。源SHAf75a93f69fd79029ae4d3ce5b9dad81520480cbf36b56b05d8719a8b84c2a63d；本地同名代码不同。原终点不改，不以修基线称新方法。
- 候选准入累计等候600/240仅0.6042536979075521/0.18352756975218654秒；包含preview的总等待不同，不混口径。它们不是GPU利用率或内核竞争测量。

## 17656与17592：历史闭合，非运行中
- 17656固定16条、900s/run/300s候选/1500s池、先600后240，2+4。原生有效3/8对1/8、首生成失败0对3、探索覆盖门true，0/8完整质量对；顺序/部分lane换卡/请求先后混杂。18030GPU秒=5.008333333333334GPUh，非方法确认。
- 17656 root=/research/d7/spc/yzyang4/scheduling-image-generation-deadline-20261011-v1；source9b23d621ffb1937b831435386effd01e38cc4f08；planSHAd153e408fb88e7ac120fceadbab79528275943e356a639871abb7e9dcc5f86b7；summarySHAef4a2d9ea398488370dcbd750f6706105a825d1c6ed6b3188653e8e88bec4f99。5评分重算/CPU8对通过；两个旧PID187646/198703已闭合，不重启。本地image_deadline_v1_closed。
- 17592固定32条、1500s/run/300s候选/2200s池、FIFO许可1/2、ABBA、2+4；32开始14正常13原生有效。仅2/16完整分对，均aerial；denoising share2覆盖4/8对fifo1的1/8等于生成存活差，不能归因共享。候选20有效/58返回均重算，原exploratory_go=false。
- 17592 root=/research/d7/spc/yzyang4/scheduling-image-live-2plus4-20261011-v3；source52d22146145c5377c8e8adb889d5bc3afa5d0237；planSHA95825b54b256eb69f7a2a372db66c4f63b4c0d9840d3253f5ade5685f448fe66；summarySHA7918c85f5257a82d66e28d52c9a557e7c924ed2e0dc5a5f4ef7b0131f6a84a9c。52836GPU秒；含失败59052秒，不变旧账单。
- 17587入口物理核/SMT错误，17590旧CUDA mask错误，均搜索0/32；失败原件不重开。v3已共同修复，不再重复G0或容量验收。17592 completion字段为readout_sha256，后两批为summary_sha256。
- 三批都是同两个图像任务、既有public训练数据80/10/10新开发视图；另10%未读。不是独立盲评，不能合并异质效果或把run数当独立池数。

## 可复用与禁止重验
- 17571联合2+4：10程序/10短请求、输出一致、8508GPU秒；17570六GPU执行：14/14、1428GPU秒；均不代表新质量收益。17576原factory六项通过、191GPU秒。
- 就绪/清理补丁A与退出报告/gateway竞态补丁B配套；bundle=sandbox_scheduling/resource_unavailable_20261011/collaborator-patches-v2，未改学长生产分支。
- 跨节点17577/78/80空命令失败已交管理员；17579gpu27本地通过。不重诊断、不升级镜像或静默退CPU。
- 历史OpenBLAS EAGAIN根因未确认，容量通过不等于找出原因。R14固定程序有限阳性17366中位1.248439822872127仍有时序混杂；17368文本质量门false，均不作为新阳性。
- first-960/Target-300/Target-522、D_val、官方test、16560数值导出继续关闭。无agent底座训练/RL、无付费API。

## 工作区与操作
- 活跃checkout=C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001，detached HEAD有意；本轮前公开head dcb0975864d53307c57d07c214f1a313ba6b27f5，当前以git核实。不动旧checkout用户dirty。
- 未跟踪用户报告phase1/reports/给学长_MLE沙箱资源调度进展_20261009.md不stage/改动。
- SSH linux5；PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。Slurm19.05.4无--exact，核物理CPU/GPU UUID，不猜step=设备号。
- 优先gpu27/gpu28 RTX3090；旧MLE镜像不投projgpu39，gpu24 cuInit999未解；排除projgpu7/8/33、gpu36/38。研究盘4TB至2027-08-30，不是实时余量。
- 本地Windows Python不可用，用WSL纯CPU；SCP返回session必须等exit0再启动依赖命令。只读计时分析不能与GPU测量争用大文件I/O。
- 凭据只远端，学长新材料先credential scan；不导出raw日志/候选/标签/预测。发布前显式stage+敏感名扫描+独立guard；Git hook旧MSYS失败不能伪称通过。
- 新贵实验先具体矩阵/全成本/停止条件；广泛授权不是无限预算。记录要轻，不为每轮新建报告或自动化。
