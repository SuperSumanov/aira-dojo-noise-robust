# 当前短交接：恢复先读本文件，不从旧心跳恢复任务

更新：2026-10-12香港10:26。揭读前规则保存在Git 4a14831e853929e28612e9b9212e9205ff24416f。
恢复顺序：fetch → CURRENT_DIRECTION → ROUTE_DECISIONS → 本文件 → 必要原始证据。

## 本轮闭合：反馈预约停止扩大，不重开旧联合罚项
- 用户要求重新思考并在三小时内实测；首次时钟为10/12香港07:58:39，目标约10:58。48条=2旧开发任务×4搜索seed×greedy/pending_ucb/feedback_gate×2反序池重复；1020s/run、1180s/pool、6GPU cap13GPUh，窗口cap14GPUh。原去噪两重复均胜两参照≥0.001/Aerial不退步/机制与结构全过的门未通过；不是新方法阳性，不自动再开GPU。
- 新处理是同父code仅一个在途Improve，等待首个外部反馈；三臂共同共享已评分archive。不是旧等待惩罚换名，不是完整WU-UCT/CostAda复现。公开source=53de94e3b2bf07b5a46a9c388efe40d7dfdff8d7（push/ls-remote核实），planSHA=e6d41cd7b40598f349e7956d3daaf610d85c5e00170b4d358b9e5cfdaa9910ee。
- root=/research/d7/spc/yzyang4/scheduling-feedback-parent-20261012-v1；stage=/research/d7/spc/yzyang4/feedback-parent-stage-20261012.Sdes1e。17CPU单测、48配置/32配对、真实native导入/展开/parse/debug/checkpoint通过。前两次CPU前检分别因无Slurm环境和旧独占cpu.json停，零GPU，原回执在cpu-preparation-attempt1/2/3。后一已通过门因提交前观测定义修正重新冻结，策略/预算未改。
- 10:08:59 job17681已FAILED/闭合：48计划、40启动、39正常、1失败、8未开始。首4池各1180秒正常；第五池pending_ucb返回码0/0/0/1且未闭合等预算，最后greedy未开始。原48条完整成功门不可通过，不补跑、不复用余款。6067秒×6=36402GPU秒，服务GPU清理通过；无GPU作业在跑，monitor23494已exit0，无新automation。
- 失败episode34的执行队列locked在截止中断后，清理再进同PID/thread临时文件exclusive-create时FileExistsError；原源码已有SIGALRM屏蔽，具体信号绕过机制未证实，不称缺少屏蔽。只读错误栈已保留，不能将该基础设施失败解释成模型失败，也不以补丁重开本批。
- 缺失规则在读取质量前以4a14831e公开冻结：48行保留，仅完整等预算池0–3比较，第二重复缺失对照为null，禁止用起点补值/翻转原门；2缺失测试通过。原冻结reader/运行源码不改，不能运行要求48完整的旧main。
- 实际读出完成：完整首轮去噪greedy/pending_ucb/gate=0.013749410741741694/0.02482337877709754/0.04551226514614451；Aerial=0.9999037860201088/0.9997434293869565/0.9998476611985055。方法第二轮去噪0.02132434553892021无完整参照，不能救门。29评分重算、4合格池16CPU对/物理卡一致/队列清理通过；第五池执行queue审计失败如实保留，不过滤失败run拼对照。
- 两方法池5/6次实际feedback_wait、3/1次非起点父解Improve完成；去噪强制等待区间335.71048188209534/522.1648397445679秒（非GPU idle）。首轮gate去噪生成4个不同代码仍未胜起点；不能称没有干预，也不能只看多样性或等待少判断效果。
- 事后只读overlap诊断（非预注册主检验）：首轮两参照同父在途准入19、返回17、及时有效4、胜准入时incumbent3；两个Aerial参照最佳均在其中。没有把debug后代归于直接Improve。它否定同父必冗余的前提，不识别若当时阻止调用的反事实；停硬预约，不改阈值救结果。
- 本地结果sandbox_scheduling/feedback_parent_v1_closed；summarySHA=9192a25577d5880b33ed3d8813aa26e430b88a19ff4068390bb8ff4677e78503。4结果远端/本地SHA一致；独立Node核48行、CSV逐格、4可比/4缺失差值及费用通过。实际36402GPU秒=10.111666666666666GPUh，含失败/闲置/清理。
- 如有阳性，仍需分离“反馈内容更新”与“并发降低后模型请求变快”的中介；本批识别硬预约整体效应，不能声称已分开两机制。固定单生成许可是后续可能的强消融，不能加入当前矩阵。异步BO/局部惩罚已有近邻，硬预约本身不自动具有原创性。
- 08:40揭读前补充只读机制分析feedback_parent_mechanism_20261012.py，6CPU测试通过；闭合后才运行，不改主门/在线源码。独立重建空闲生成许可被硬预约阻止的时长、同父在途重复、新父使用；该时长不是GPU idle/节省，不能估反事实质量。
- 揭读前最后公开head=4a14831e（缺失规则）；运行source仍53de94e3，不混淆。09:26核48配置/冻结Improve：模板含memory/packages，11包shuffle，有memory；固定seed不等于同提示/同输出。检查器原误读operator层包数0已纠正到solver层，不是运行配置修复。
- 09:53揭读前补secondary读出：逐任务机制计数、精确生成代码重复（不导出hash/内容），7CPU测试通过；不改变main readout/质量门。需在closed.complete=48后运行stage中的feedback_parent_mechanism/secondary，均写新文件；这种事中但揭读前的描述分析不冒充原计划主检验，代码重复也不等于同提示或seed因果。
- DNS一度失败；用已观察同一IP137.189.88.148 + HostKeyAlias=linux5.cse.cuhk.edu.hk + StrictHostKeyChecking=yes可连；不改SSH配置、不跳过hostkey。所有私密候选/标签留远端，不在中途读取终分。完结读出feedback_parent_readout_20261012.py，原运行/读出均已冻结；评分重算后独立再核CSV/JSON。

## 本轮已闭合：生成前联合准入，不再提交
- 用户要求三小时内验证同预算最终质量，不能停留轨迹筛查。17675于07:30:49正式COMPLETED；48/48正常结束、48/48有效终点。6池顺序continuation/cost/joint/joint/cost/continuation，2开发任务×4搜索seed×3臂×2池重复；1020秒/run、1180秒/池、2服务+4执行GPU。
- 冻结原质量门false，结构门true。8个池/任务/参照对比为3胜4负1平（相关对比，不作8个独立样本）；两次joint共15个稀缺选择点，额外资源项实际改变选择0次。参照池有2次假想反事实差异，不能算作joint实际干预。
- 去噪RMSE越低越好：重复0 continuation/cost/joint=0.01773766034675879/0.017483073139600545/0.04551226514614451；重复1=0.01773342357652896/0.018683635028191925/0.013718285978365746。第二次joint局部最佳不能抹掉第一次退步，也不能归因未介入的资源项。
- Aerial AUC：重复0 continuation/cost/joint=0.9998022268191125/0.9998690420829258/0.999855679030163；重复1=0.9999385299572917/0.9997140306708787/0.9997140306708787。给定起点0.9997140306708787只余0.0002859693291212828上升空间，小于0.001实质门；不得再把该起点当大幅改善任务。此局限不撤销去噪的失败重复。
- 去噪8个搜索seed的终分中位数 continuation/cost/joint=0.02062521564578909/0.020789326370465523/0.03396904349923425；样本SD=0.01372515140952784/0.01200366080140969/0.014488577463408195。只作描述，不当8个独立调度池。
- 45份外部分数复算、24物理CPU配对、固定物理GPU/lane与清理通过；6池收尾均有服务队列0/0采样（不是连续请求级证明）。独立JavaScript核48行、CSV/JSON逐字段、32同seed对比、8池对比和费用通过。
- 次要external-best保留诊断仅发现index28有AUC+0.00001202674748634891未进入原生终点，去噪不变、质量门仍false。诊断是在首池结束后但任何质量读取前添加，原主判据未改，不能用次要口径救结论。
- 裁决：停止当前等待惩罚配方，不补seed、不重开批、不把局部最优或多完成轮数包装成方法收益。普通续改已证明去噪可改善；联合项的独立收益未被本负载识别，不推所有联合控制普遍无效。后续新矩阵必须先说明实际可干预差别和强参照，不能只是重命名。
- 重要限制：共享有效起点后的条件续跑，历史构建不是免费从零E2E；2个重复开发任务、2个池重复。cost用链内改善频率，不是CostAda完整global-best credit/探索控制复现；补核出处在ROUTE_DECISIONS。没有文献强方法胜出或论文创新确认。

## 精确证据与成本
- root=/research/d7/spc/yzyang4/scheduling-generation-joint-20261012-v5；正式结果readout-v1。source=e180a0b5e8289c99bad27872fd63629e7421d8ff；planSHA=e923a7eefe6b69fdf9416bed58cab10218553760351022cc0b31920d039c32db。
- summarySHA=865496de253120f0224558b93e0d35fdf8e333d1b3b427f4522e022f44056399；readoutSHA=fe7e55fe475e6ff49839ad25d4493de8db918e560842b76c6b8258014d7ead1b。分析器揭读前公开commit=26110279cd92a2fdf05f80186de82c465f615e69。
- 本地结果phase1/sandbox_scheduling/generation_joint_v5_closed：summary、runs JSON/CSV、identity、accounting、service-audit、independent-verification；四个远端结果SHA与本地全部一致。原始代码/预测/标签仍仅远端私有。
- 发布门曾拦下CSV的CRLF→LF暂存转换；仅补精确结果目录的-text属性并重新暂存原字节，数值/远端原件未改，复查credential/敏感文件名/字节不一致均0。
- Slurm7366秒×6=44196GPU秒=12.276666666666667GPUh；连同前败4974GPU秒，总49170秒=13.658333333333333GPUh，低于原14GPUh。启动/预留空闲/清理全部计入，不是GPU busy时间；无付费API、无agent底座训练。
- 17673 FAILED：476秒×6=2856GPU秒；暖起点current_step先增导致原生日志越界，候选0。17674主动取消：353秒×6=2118GPU秒；代码检查发现evaluation/eval_result关键字错配，8暖起点/4调用准入/0轮完成。均我方接线错误，旧48分配与原件分别保留，不计入成功效果样本、不复用预算。
- v1 path/list断言、v3复制/tmp IPC socket均CPU前检失败零GPU。修复后真实原生expand/parse/analysis/debug/journal/backprop/checkpoint门通过，离线34单测通过；不是以合成测试替代实际48条。
- 06:17一次SSH超时仅结束monitor19407；只读重连成功，原GPU作业未重启。替代monitor50598、readout1052、取回13698均已exit0；本轮没有运行中的GPU作业或待启动跟进，不得重复submit/readout覆盖。

## 历史与不可恢复事项
- 17670独立请求时限复验已闭合：32条、只有1/4池任务分对、0/16同seed分对、质量门false；不再扩240/600秒配方。17656仅覆盖信号、17592质量门false；旧原件和详细数字见上列Git交接及各closed目录。
- 17571联合2+4容量、17570六GPU执行、17576原factory门已过，不重复G0。17577/78/80跨节点派发失败已交管理员，不再围绕它排障；历史OpenBLAS EAGAIN根因仍未确认。
- first-960/Target-300/Target-522、D_val、官方test、16560数值导出继续关闭。旧critic/HCE/多保真/Probe/自然父程序修复等不自动恢复；不训练或RL更新agent底座。
- 学长分支最近只读核实仍64fd78e98cfdc945b1af03f29f570975d58b88b7，未改对方分支。旧Held12535不动，不删旧失败或检查点。

## 操作与恢复
- 活跃checkout=C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001；detached HEAD有意，发布仅myfork/phase1-value-critic，先显式stage/安全guard/fast-forward，再ls-remote核实。当前发布head以Git为准，不把本条中的揭读前hash当永远最新。
- 未跟踪用户文件phase1/reports/给学长_MLE沙箱资源调度进展_20261009.md及旧checkout用户dirty均不动、不stage。
- SSH linux5；PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。Slurm19.05.4无--exact，设备按实际UUID/物理核核对。
- 本轮gpu3 RTX3090已使用既定资格；优先gpu27/gpu28，现有任务镜像不投projgpu39、不升级Torch、不退CPU。gpu24 cuInit999未解；排除projgpu7/8/33、gpu36/38。
- 研究盘4TB至2027-08-30；不是实时剩余空间。Windows Python不可用，用WSL纯CPU。SCP必须等exit0再核全文件SHA；不把复制中的缺文件当最终结果。
- 凭据只远端；学长新材料先credential scan。保护原件，新贵批次事前矩阵/全成本/停止门；本轮停扩，不用广泛授权自动重开。
