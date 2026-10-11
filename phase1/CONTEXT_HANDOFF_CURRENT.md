# 当前短交接
更新：2026-10-12香港04:26。压缩前完整交接保存在Git dcb0975864d53307c57d07c214f1a313ba6b27f5。
恢复：fetch → CURRENT_DIRECTION → ROUTE_DECISIONS → 本文件；未复查的动态状态只写最后观察。

## 最新用户请求与本轮完成
- 用户允许沿新假说做小尝试；当前仍R14，不自动恢复旧critic/HCE/多保真/Probe/TD/score-channel/K≥1或自然父程序修复。
- 本轮固定17592/17656/17670的80已分配开发run，三个批次分开做CPU只读机会筛查，没有新GPU/API/训练/automation，也未重新评分或改旧实验。
- 40条lane队列均独立复核：候选之间需要取舍的稀缺准入选择点均0；仅17592有2次preview/preview竞争。原生journal Improve为1/0/0，accepted Improve均0；未完成调用可能不进journal，不推所有改进均无效。
- 因此前述“候选排序优先级”在当前负载缺发挥空间，不开复杂调度器或重复旧质量配方；这不是新质量阳性，原门false仍保留。
- 候选研究切口：生成前联合决定同任务哪条搜索链获得下一整轮资源，结合已见进展与实时拥塞；保留每任务总预算，跨任务不挪预算。需先有有效起点/可重复改善/服务竞争，再与续轮优先及成本感知搜索+资源调度组合比较。只是假说，未部署、未跑效果、不承诺新颖性。
- 已核近邻CostAda v4（2607.26828v4）、MARS调度（2604.26963v1）、SAGA v2（2605.00528v2）；不能把整轮预留、收益/成本或续轮优先本身称创新。
- 源码scheduling_opportunity_screen_20261012.py；21项CPU测试通过，独立verifier直接复核原队列/角色，不导出候选、标签或预测。首次只读分析因历史回执字段名、局部操作序号命名空间失败，零GPU；修正后增加真实形状回归，不改原件。
- 安全产物sandbox_scheduling/opportunity_screen_20261012/{screen-v1.json,independent-verification-v1.json,runs.csv}；screenSHA c1cb507322bf01065cb673221471c6007eb8c06bd3de856c69e01b0e26331abd；verifier结果SHA 0e440c9bf30aa0ee02836264efb14b1b55db2a7f9bbb3d420ccd1af84431cb8d。
- 远端只读诊断目录=/research/d7/spc/yzyang4/resource-diag-stage-20261011.M5wKjU/opportunity-screen-20261012.q7Tlx8；两结果已生成，不覆盖或重跑写入原路径。
- 本轮fetch自身phase1-value-critic/学长dojo-reproduce成功；学长最后head64fd78e98cfdc945b1af03f29f570975d58b88b7，无新变化。未改学长分支。04:26 SSH正常，squeue只列12535 PENDING；旧Held不动，不能称新实验在跑。

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
