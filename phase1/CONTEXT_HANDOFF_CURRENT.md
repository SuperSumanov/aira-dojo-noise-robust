# 当前短交接
更新：2026-10-08 13:11香港附近最后观察；动态状态须重新核实。
此前详细交接完整在 Git 1ca06f255199785d84ef7ecf56129060d2b8d82f；不把旧状态恢复成现场。

## 入口与边界
- 活跃checkout：C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001。fetch→CURRENT_DIRECTION→ROUTE_DECISIONS→本文件；旧aira-dojo-codex-20260813有用户dirty，不覆盖。
- 唯一活跃R14：MLE沙箱资源调度资格/强参照。无重要独特、强基线跨任务同预算的新方法确认；旧R1–R13、HCE/多保真/Probe/TD/score-channel/K≥1不重开。
- 用户本轮约07:51–13:51香港完整六小时在会话内研究，goal active；最新“批准所有操作、不用问”。自主合理推进但不解除保护/凭据/底座边界；未满窗口不提前完成。
- 本窗口新增GPU自限≤3GPUh=10800单GPU秒，包括失败/初始化/空闲；无付费API或agent底座更新。不读first-960/Target-300/Target-522、D_val、官方test；不改学长分支，不碰旧Held12535。
- 公开己方HEAD已核7359aefa5f902442d2ce1970c2b4c6d280c2e27c；11文件发布扫描0命中。17017结果/补充核验已发布。dojo-reproduce fresh fetch仍dfff0efb9daf1d4a63c74492f138c19c1fd8440e，autoresearch最后d82dcd845e30e9771750510028d38a6d1d979c43。
- SSH linux5/yzyang4；PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。MLE仅gpu27/gpu28 RTX3090，不投projgpu39。复杂SSH上传脚本，不用内层管道格式引号。
- 研究盘/research/d7/spc/yzyang4总4TB至2027-08-30，非剩余量。原镜像SHA801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda。

## 最新闭合：17017独立大输入确认，不重跑writer
- root=/research/d7/spc/yzyang4/scheduling-neural-full-confirmation-20261008-v1；tmp=/tmp/r14-neural-confirmation-20261008.eJVICI。
- source=5f44b1af605f4f7b6034d3556c4c1a2f62b7232b；plan SHA=b8bf8619c61a98db5af35bb2b68f4b9838354c9ccfef166d8dd788ca0b16df7f。
- 已COMPLETED/12尝试12完成/2035单GPU秒；三配对1.6811874366439696/1.6923715665437906/1.6232967236130837，中位1.6811874366439696/std0.03707594310497998。Cactus150步/DnCNN3920步各六次一致，六输出/程序数值全同。
- 17005相同两源码/公开输入/原seed42重启，serial/share2×3=12；gpu27/6CPU，45分钟≤2700秒；450/525/550秒原候选/解释器/worker界不变。所有我方下一批重准备在submit前已完成，运行中不做大镜像哈希/数据构建/全输出审计。
- readout/audit已各执行一次，均通过；本地full_confirmation_v1_closed。summary SHA8c985bc78b4056980436589486ffa50c0999a5b5efc91c6bae76d21e4db608a7；audit SHA88284db5599308040e3dca83a421f289cab502d038cc193e4f55795bef70f0f0；runs SHA87fe0120ff1dc06fea0fcffd532a1aedc5c212197c86422dc9318a8fe6544005。
- 另补audit_execution_identity.py（SHA455d38da353a8a7cd055005e2f7ca26d725db8050a2568e680b34aaa05fdadb6，4本地+远端测试通过），16996/17005/17017全部12身份与输入hash通过，各目录identity_audit.json。preparation_overlap_audit已核17017六块0已记录重叠；measurement_context.json保留范围，不声称全主机隔离。feedback_latency.json只是事后首返回时间，不是下一轮生成/效用。

## 已闭合：17021神经强参照，明确17014基础设施重试，不重跑writer
- root=/research/d7/spc/yzyang4/scheduling-neural-overlap-retry-20261008-v2；tmp=/tmp/r14-overlap-retry-20261008.jTdpZ1。
- source=f507a53f759b41fee5e3f39906ff6db50ec69796；plan SHA=528026478eff9138b06ff53023d5793139ea3bd9246fc3082cc3d749c8c25dfc。
- 旧17014预热wait_for_ready超时，157GPU秒，12正式槽0尝试；原失败不覆盖。本次明确基础设施重试，非独立科学复制；同2小输入神经程序、pipeline/share2×3=12、原worker/源码/seed/450/525/550秒不变，总限30分钟≤1800秒。
- 13:02核FAILED/12尝试10完成/885单GPU秒。pipeline slot6在prelude就绪超时120.05448503326625秒，slot7由前驱失败屏障拒绝，两者0候选开始；不是两个独立任务算法失败。两个完整配对2.0118806105322156/1.3991776441257207，确认门false，不删第二组、不补跑。10可用输出每程序5份全同，150/640步一致。
- 冻结readout/audit各完成一次；summary SHA6cd031cd88f5312ba302b1f40751b284a2883c7f11ec9a90540634157fadc948，audit SHA6fee88b76dac2b5aacf4fa99180451f948b829a5b989c0e5eee06e4b31d8d624，runs SHA6aab8f316603fc2a9e4723fab8bb71d43ea2f48718f588818b4ddeb2d86b502b；pipeline-contract已独立核成功槽的串行屏障。补充身份12/12及14242引用输入hash通过；六计时块无已记录我方重准备重叠。全部产物在overlap_retry_v2_closed，写原件的命令不得重跑。
- 已闭合GPU秒：16987=37、16989=43、16992=100、16994=566、16996=1444、16997=488、16999=2053、17004=0、17005=1989、17014=157、17017=2035、17021=885；sacct独立复核总9797=2.721388888888889GPUh，上限10800。余1003秒不补旧批救结论，本窗口不再新投GPU。仅17004已核PENDING取消/0秒/空TRES/无step，不泛化所有CANCELLED为0。

## 已有证据：只按需读结果，所有旧writer都已闭合
- 16994 pool_v2_closed：36尝试35完成，serial/share2各12/12，中位1.7852942816262258；4程序输出全同。C一次候选前超时，不删失败宣称C胜；GPU驻留≤1，不能称同时GPU训练。
- 16996 neural_v1_closed：12/12/1444秒，中位1.3508923175938645/std0.09956925293864344；两神经源码，150/640步，每程序6份输出全同；非独立训练seed/质量/新方法证据。
- 16997 pipeline_v1_closed：36/36/488秒；4小程序，启动并行/执行串行强参照仍输share2，中位pipeline/share2=1.3177936445362894；输出/训练量一致。不是神经强参照，勿混称。
- 16999 homogeneous_v1_closed：24/23/2053秒；Cactus12/12中位2.2346668327601384含单执行时长波动，不称超线性；DnCNN11/12，slot7候选前初始化超时，未过门。两个完整块首返回反而更晚，不删缺失或以吞吐掩盖延迟。
- 17005 full_input_v2_closed：12/12/1989秒，中位1.602670906461665/std0.03902198324710583，150/3920步、输出全同。DnCNN113公开配对=98内部train+15内部val、同2noisy query/无query clean；实际输入看plan.input_scale_receipt，不看继承的旧fixtures.json。
- 16999 blocks6/7/11、17005 blocks0/1与我方后续准备mtime窗口重叠；计时均标有混杂，不删块。16994/96/97未见这些已记录区间重叠≠完全隔离；mtime子区间不是物理I/O因果证明。17017专门控制我方重I/O，不替换旧观察。
- 17014 overlap_v1_closed：预热finally误写complete=true但无output/metrics、supervisor退出1；controller已拦住，monitor已修交叉核验。未解决偶发kernel-readiness根因；空pipeline-contract不证明硬件对照完成。
- 17004仅排队取消，跨节点复现未完成；full-input v1仅prepare留存。不重投这些旧批次。16987/89/92及10/7的16846失败细节保留于1ca06f25旧交接及原结果；不得用新输入重写。
- 三个feedback_latency.json已发布：首个成功程序关闭返回不是下一次普通LLM生成/搜索质量；混合长短程序FIFO次序强烈影响比值。原混杂仍适用，缺失仍保留。

## 当前科学判断与操作防错
- SchedMate已有代码/历史/日志语义、干扰撤销；ElastiCo、DetShare、Cortex、SJF-BSBF、AgentSysBench及新近邻见sandbox_scheduling/README。语义/阶段借还/资源耦合/未知时长不是空白。没有证明复杂调度器必要。
- 新核ForeTS固定源码：执行返回立即更新journal/step/价值，失败可先debug，再检查step limit。并行兄弟或按完成顺序消费会改搜索；后续纯调度优先跨独立run共享、保留run内逻辑/消费顺序及固定生成容量。未改生产实现。
- 旧16370全池22.72%生成预留窗口不是节省，只有2worker/2执行卡/波屏障，无额外ready积压证据；普通滚动补位也必须是强参照。固定回放速度不是live效用。
- 多驻留GPU PID不等于kernel并行；Adam host步区间不是kernel耗时。Cactus整卡训练包络利用率仅约2–3%，神经源码不等于重GPU负载。未启MPS，不静默换镜像/CPU或调小batch。
- 本地待提交17021安全汇总/附加只读分析及短交接。feedback_latency已在闭合后远端通过6测试并运行，pipeline键不冒称serial；每次程序返回不是下一轮生成/搜索效用。26相关本地测试通过。safe export发布前扫内容/文件名，数字用已打印值；Git附属sh警告不等于hook通过。
- readiness_evidence只读导出握手事件：slot6在client创建后等待就绪，未开始任何代码；日志未提供消息传输轨迹，不能确定根因。冻结client SHAa6c6abdca37745ce8d5137f48595a3c0e6332c113e8133b0782425b7bbb291bf只有一次info请求/逐消息完整timeout。bounded_readiness为未部署的未来opt-in辅助，保持总deadline、仅重复info请求、不重启/重发候选；原方法故障注入复现单次丢回复不能恢复/无关消息延长等待。mock不是现场根因或实测修复；不改src/学长分支/闭合批次。
- 六小时结束前核时钟/goal和所有本轮作业；只写轻量交接，不新增长报告/自动化。记录科研边界，不承诺阳性或顶会百分比。
