# 当前短交接 — 2026-09-14 01:20 UTC
方向CURRENT_DIRECTION 0L203。六小时会话窗口09-13 21:06:43→09-14 03:06:43 UTC（HK11:06:43结束）。必须继续会话内研究到端点；不新建自动任务替代。用户希望正结果，不能保证/伪造/隐藏失败。

## 正在运行，尚未读效果
13298/13299于00:38:17单次提交。最后01:13:53均gpu28 RUNNING；六条Leaf已按预算闭合，两条Space运行、四条待执行。观察到的结束类型只有timed_out/API剩余预算不够，不能把controller failed直接当模型失败。
ROOT=/research/d7/spc/yzyang4/forets-wallclock-20260912-km65uuej
STAGE=/research/d7/spc/yzyang4/forets-cheap-v2-stage-20260914-bqkP9eR8
预计约01:40–01:55 UTC全12闭合；两allocation各85分钟。全闭合前不读当前label/quality/预测值、不改模型/seed/预算/策略、不补跑。
矩阵Leaf/Space×46/47×uniform/short_code/learned_validity=12；600秒总搜索，300秒程序，64step/100adapter，2生成1执行。Fresh原镜像gpu28/6CPU，共同RF起点。只有选择器不同；与旧8B/Jupyter不能做单旋钮因果比较。
source61b48862532d048f5f04a517e3f89b211c59bd3d；controller e4f9dfcf409b62ea7d6d00e6e4b9189712029ee3；preparedb2f53da2f6c9cde40c3a6b066a2670a13073f08547bb5d7f301ae4ba8293720b；auth42c7dff9a962500c91bc40b7e5928d688a525638b8afb66c0bcd20e4206031b7。
source archive57323979e6d07f3edc0a9991a3bad8abcccdbe04270737a85bf752425ea3ca67，local releases/forets-cheap-selector-source-20260914-v4/，成套archive+artifact，不能根据相同tree猜tar相同。
readout-plan4affb5b380bf7aabd71a956208b7c3c96e243d0ab907158aa56c092ec48408fe。
两allocation及12行全闭合后一次运行STAGE/readout_cheap_selector_20260914.py ROOT。它有exclusive文件；如中途失败，先核已写产物，不盲重跑。主action、次iteration，全部技术合格且对两个基线均净胜/两任务无净退步才过原投资门。
STAGE/monitor_cheap_selector_v2_20260914.py只读结构/账；01:13账2736calls held8587723047/settled6487723047nUSD、unresolved3（含在途），stoppedfalse。2条旧未知始终保留，不把在途误叫新增未知失败。
闭合后STAGE/audit_cheap_closed_waits_20260914.py另核共享责任预留等待，2解析测试过；不减等待伪造同预算分、不改资格。

## 新实质结果，正负一起保留
报告CHEAP_TRANSFER_FINDINGS_20260914.md与0L203。线上固定模型SHA05379469122879c798f1d2c571eb733956a067dac314050feeb06d3e09c641d1。
模型root=/research/d7/spc/yzyang4/forets-task-validity-20260914-n8q3h72y；2482旧节点/138run/14任务，929有效1553无效；旧v9有锚点的run补回失败，排除无锚点全失败run，不能称无偏全语料。
四旧协议全部计划来源32run→15有完整对run/45完整对/11discordant。HGB有效选择10/11，短代码4/11，行数5/11，syntax-only5.5期望，一次同参尺寸HGB6/11。HGB vs短代码6pair胜0负，但只有4run胜0负11平，不能用11pairs做独立显著性。vs尺寸5pair胜1负。
四来源scope88v5m9dr/action7wzrny21/width2z2s7sc3/memory103zf3nb；完整及含未知全对独立原始label/生产特征/模型重算通过；跨run完整unordered pair重复0。较新protocol是看见scope信号后新增post-hoc压力检验，不是假装确认。
含未知62pair/17unknown。scope完整程序组HGB-vs-short最不利界：Leaf[.0555555556,.277777778]；Space[.0669642857,.200892857]。vs尺寸Leaf[.0555555556,.5]、Space[.0119047619,.110119048]。不是CI/总体保证。width vs短0；memory Leaf[-.666667,+.666667]仍未知，全部组必须报。130代码出现前缀可parse，不是130unique。
本地已验哈希results/cheap_transfer_robustness_20260914/（17文件）与cheap_size_ablation_20260914/（summary67fdb9c4...、independent9203b6f6...）。公开包04f4cfb711a964df06681f802977a58684a09b298bc1bcee1c86869550c7f5d4；尺寸包b583472eecc65bd7436da673ebccf08c86b6e4d46d970a95c31ad2a0f969ed69。

## 新反证已独立通过，不能选择性隐藏
quality：45完整pair仅3 both-valid，全Space/3run。原journal全部report字段唯一匹配原escrow，6提交独立数值重评分。HGB全3偏低质量；vsuniform平均-.004405，vs短代码-.0057433333333333225（0胜2负1平）。不是完整E2E反事实。summary93beff6761de70a1632e4fefc09a55329b254b108a9f007f64d27b1bea37a752，independent8c7dc0202df7e806c672e7fa2df4c1aeaf952f53acb1dd9fa2c313a647844fd5。
LOTO：固定14历史task×full/size=28CPUfit，28.716913531068712秒；不部署、不重选。rootforets-leave-task-out-20260914-3bppxdqh。
primary任务宏平均within-run AUC full.48886771165193804/size.5158798185810396/short.5558735851921456。full vs short3task胜11负，vs size10胜4负但均值较差，不能仅挑task胜数。purge0，独立vector/模型/加权pairwise AUC126cells验证，预测差0。summary43573a5c8dcf96b72fa60a3dfbd195c1c966a5fe12746c977ef8df95c2cdaeba；independentc8fd3a01d9659a77352736bda955e9bf7f29134611e01f4f2ed0c9780a3d0a59。
上述本地results/cheap_transfer_stress_20260914/，4manifest文件哈希已同；tar2b4f82520060f62e4927c3cda558875d1e3f6794d62d2afc7b4a1b539a92103e。
当前只能主张有限任务相关有效性先验，不能叫通用质量预测器/任务外能力。下一决定性证据仍12搜索实际最终成绩。

## 先前失败/禁止重做
v1 q_imzdb_ 13293/13294各67秒取消，4生产回执有但backend找错integration固定名；proofa775e0d9a6dcf62accf055f31ebd6822fcf9b06a2adf225b16c03ada227ea8e7证0生成0评分0search API，只4route。完整同seed12v2重启非按效果换seed；仅修childPID绑定/拒绝旧receipt，4tests+7reader过。失败134秒+v2两85分<=原3GPUh。
临时tpjljg17激活重复route scope原子回滚（旧账active/新db空），已封存，勿复用。km65uuej唯一active，q旧账sealed。
EScope88v5m9dr全16闭合主4可比对0胜4负4未知；272module输出全部接口拒绝。原扩大门/preservation失败，不补seed。native extract_code补充修正原reader representation验证234调用/146转换，结果完整保留，见相关报告。不能重新main读出exclusive。
传统13284八条8/8有效512候选、API0，非完整AutoGluon。Fresh原验收有限，G0/12892/8B不重做。旧critic/宽度/记忆/T1失败均留报告不扩大同配方。
CodeScaler已读3/4.2.1；Automata已读length-vs-structure相关段；MARS4.3/4.4/5.1等已有先例。静态失败预测/AST/HGB/模块化/记忆不自称原创，详ESCOPE_ADDITIONAL_PRIOR_ART。
学长branch最后fetch仍be9335348b569086ef9b0af36a15b13e61fec45c（01:18本地ref核对）。0912包已隔离11,844,727bytes/4config，不是4eligible，未入训练/LATEST；unknown duplicate保持failclosed，不重下。不借其他人allocation/未确认共享免费端点。

## 操作/交接
SSH linux5，airaPython=/research/d7/spc/yzyang4/venvs/aira/bin/python，SLURM_CONF=/opt1/slurm/gpu-slurm.conf。MLE原镜像仅gpu27/gpu28，禁projgpu39/Torch升级/CPU退路；旧12535不动。
remote aira-dojo/.env OPENROUTER_API_KEY，proxy需source ~/env_setup.sh；绝不回显/本地/git/重索。原累计100RMB→保守10USD责任帽；两旧未知不清、不重置/借钱。
保护first960/Target300/522封闭；HCE/多保真/Probe/score-channel/K>=1/agent底座更新禁止。
本地C:/Research/New/my_project/MLEvolve/aira-dojo-codex-20260813，push只myfork HEAD:phase1-value-critic。最后确认公开1b39efe363a898bec87dd7b901f661cddaec51f0（LOTO plan）；当前一批代码/结果/报告待精确暂存扫描再push，不改学长branch、不新建branch。无关untracked保留。
apply_patch编辑，复杂SSH经scp文件；wait scp完成再执行。SQLite连接用closing避免NFS句柄。读取只credential扫描后的明确旧根，不碰新保护数据。
研究盘1TB到2026-09-29，续期未知。未重新核验动态状态要写最后观察。不要用记录替代实质工作。
