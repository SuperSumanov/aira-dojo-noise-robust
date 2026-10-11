# 当前短交接
更新：2026-10-12香港00:54。旧排障长交接已保存在Git4279975d；这里只保留当前事实，未复查的状态写最后观察。
恢复：fetch → CURRENT_DIRECTION → ROUTE_DECISIONS → 本文件；不得回到旧8月路线。

## 最新用户裁决与刚闭合实验
- 新用户要求：沿局部信号验证、一小时给有价值反馈。23:39 SSH banner曾HTTP404三次，用户修复后23:41重连成功；没有把连接失败算实验失败。gpu3有空余，旧Held不动。
- 新request-deadline screen已唯一提交为17656：16条=2任务×4新seed212001–212008×2条件，deadline600先/deadline240后；执行许可两臂均2，run900s/候选300s/池1500s，2服务+4执行、cap3120s=5.2GPUh。只有1个池配对，不能称跨seed独立调度确认。旧17592不重开、不补旧seed；代理超时范围校验在新目录共同支持600，未改原件/生产分支。
- 9项CPU测试复验通过，远端16配置/8配对预检通过；source9b23d621ffb1937b831435386effd01e38cc4f08已push/ls-remote一致，planSHAd153e408fb88e7ac120fceadbab79528275943e356a639871abb7e9dcc5f86b7。新入口image_generation_deadline_20261011.py，读出image_deadline_readout_20261011.py；目标=/research/d7/spc/yzyang4/scheduling-image-generation-deadline-20261011-v1。
- 00:54已核17656 COMPLETED/gpu3，3005秒×6=18030GPU秒=5.008333333333334GPUh（cap5.2）；两池各1500秒含启动/空闲/清理，全部16条开始。600/240：正常闭合8/5、原生有效终点3/1、有效候选3/2；aerial各1/4，denoising2/4对0/4；首生成失败0/3，后三个全denoising。冻结screen_positive=true，结构/5评分复算/CPU配对8/8通过；无新GPU作业。
- 终分边界：0/8同seed双方有效成绩对，中位差/方差均null；按覆盖配对3增1减4平，不当独立池统计显著性。只有固定600先/240后的1个池对；不是方法确认或最终成绩提升，不与旧1500s结果混比。安全原件summary/runs.csv/runs.json及账单在sandbox_scheduling/image_deadline_v1_closed；summarySHAef4a2d9ea398488370dcbd750f6706105a825d1c6ed6b3188653e8e88bec4f99，与completion-closed一致；本地独立重算全部计数/分母/门/成本一致。
- 独立硬件核对通过：同服务GPU对、同四执行GPU集合、两池隔离和服务清理通过；Slurm将lane1/2/3换卡，仅lane0同卡。初始请求600池denoising先、240池aerial先；不能称逐seed精确同卡/同到达确认。完整数字和限制在independent-diagnostics.json，不临时重配或补跑。
- 已核真实CUDA候选训练回执（index1/6/7/12为990/5325/5285/2840步，非GPUkernel计时）；5评分由冻结读出全部复算。600首生成8/8成功、7个超过240s；17/10候选返回并不等于有效3/2。若干8192token的journal代码不可AST解析但exit0，未证明其等于实际执行源码，不据此诊断SyntaxError。
- 唯一submit PID187646已结束，途中SSH断开但原进程继续、未重投；输入哈希约12分钟完成，额外GPU0。原始提示/候选/预测留远端；diagnostic只导出token/语法布尔/预定义错误枚举，未改运行源码。
- 已追加只读数字诊断：原32条首生成失败18（aerial7/16、denoising11/16），四池首请求跨度0.6937–14.8490秒，服务峰6运行/2等待。240s是我方保护设置；本地原始backend1500s/10重试，00:30核学长64fd78e的backend为14400s/10重试，部署override未知，不能混称生产默认。修复该设置不是方法创新；证据image_live_v3_closed/generation_funnel_audit_20261011.json。
- 一次性CPU读出PID198703已退出并写completion-closed；claim SHA7256f28c79a40cae4acac24bdd75e0d3c015cd6fe698b5ee24f4aac087d97454已核；切勿重启动/重投。冻结9项CPU测试再次全部通过。本轮不改参数或门；首次连接中断没有重复提交。
- screen通过的是全16分母、逐任务覆盖不降、总体覆盖增、首生成失败减少及结构门，不是最终分数门。候选累计执行排队600/240仅0.3546661902219057/0.187119722366333秒，尚未暴露执行竞争；后续应在可靠生成基线核真实调度机会，不能包装调长timeout为方法新颖性；无自动扩大。

## 已闭合17592及前置事实（不是当前运行）
- 用户：跨节点问题由其问管理员；先用已跑通的两卡服务＋四卡执行推进同预算真实收益，不再反复验收。
- 本轮只改每执行卡的FIFO候选许可1→2；四GPU各固定配对两个独立run，保持run内MCTS顺序。不是全局迁移/一般phase-aware强基线，更不是SchedMate复现。
- 新任务：aerial-cactus-identification、denoising-dirty-documents。仅从既有prepared/public训练数据划80/10/10；10%开发评分引用仅宿主可读，另10%不复制不评分。新视图不是独立盲评。
- 当前v3：2任务×每池每任务4seed×2臂×2轮=32条原生MCTS；ABBA四池；每run1500s、每候选300s、每池2200s。
- 单节点gpu3，2服务+4执行RTX3090；24物理CPU=服务8+4lane各4，lane内两run各2核，两臂相同。
- 27B INT4固定本地模型；medium/8192输出；不训练agent底座、无付费API。当前cap9000s×6=15GPUh，加前两失败保守6216GPU秒，总上限16.726666666666667GPUh；均含启动、空闲、清理。旧失败不重开。
- 主终点原生选择的外部开发分；全32分母、无效/缺失不填0；有效CUDA反馈及任务池最好分次级。只有2个配对池重复，32run不是独立调度重复。
- 扩大门：完整32终点/16有效分对、两池CUDA有效反馈都增加、逐任务配对分中位不负且至少一任务正、无更多无效终点、等预算/隔离/清理通过。不换seed、不因单池结果加跑。
- 当前路径=/research/d7/spc/yzyang4/scheduling-image-live-2plus4-20261011-v3；旧v1/v2同前缀仍保留。
- v3 source52d22146145c5377c8e8adb889d5bc3afa5d0237已push/ls-remote一致；planSHA95825b54b256eb69f7a2a372db66c4f63b4c0d9840d3253f5ade5685f448fe66。24项CPU测试/32配置/16配对通过。
- 17592已于香港16:52:58 COMPLETED（14:26:12开始，8806秒）；四个ABBA池各2200秒，32全部开始、14正常闭合、13有效终点。58候选返回、20有效评分全部独立复算，结构/CPU配对16/16通过；原exploratory_go=false，禁止重投本批或改门。
- 同16条分母：fifo1正常6/有效终点6/有效候选12；share2正常8/有效终点7/有效候选8。两个配对池有效反馈差+1/-5，非稳定提升。16个同seed分对仅2个完整（均aerial、小幅正），denoising无完整同seed分对。
- denoising有效终点share2为4/8、fifo1为1/8；第一池最好RMSE为0.019668933511051076 vs0.04551226514614451，另一池fifo1缺有效终点。只能报局部探索线索，不替代完整主门；aerial池最好差一正一负。
- 18失败run全部在首次生成请求约240s退出、无候选执行；具体服务排队/长生成占比未定因。所有候选（不含preview）累计等执行许可fifo1仅0.4998949011787772秒、share2为1.03202722244896秒，本批没有明显执行队列竞争，不能凭共置推质量收益。
- 真实CUDA训练已确认（早期run0/aerial2700步、run5/denoising1655步）；优化器回执不完整不等于无训练。现有只读funnel不改冻结结果；无新增GPU/API。结束后未自动扩大。
- 独立结束复算16:54闭合；summarySHA7918c85f5257a82d66e28d52c9a557e7c924ed2e0dc5a5f4ef7b0131f6a84a9c，本次21:52核SHA一致。成本52836GPU秒=14.676666666666666GPUh；含前两失败保守59052秒=16.403333333333332GPUh，低于17上限。本地安全汇总sandbox_scheduling/image_live_v3_closed/status_checked_20261011.json。
- 21:53队列仅旧Held12535，无本轮运行作业；不动旧Held。旧status脚本对已退出队列的job报Invalid job id，不能据此称实验失败；此时查sacct及completion-closed。原8月自动化不恢复。
- 17587已FAILED闭合：八worker在搜索前退出，0/32搜索、0候选；服务正常。原入口错误要求4逻辑线程，但lane回执实际4物理核/8SMT线程；不是CUDA或跨节点故障。439秒×6=2634GPU秒，原32分母与失败保留。原planSHAb44f6002b5da35d953a0ae1ead7b88d7776428cf7e775a26475fcce545837e78。
- v2已解决4物理核/8线程入口，保留每worker两物理核、CUDA初始化前绑核；本轮继续复用。
- 17590在香港14:05:04开跑，八worker越过CPU入口；八预览因旧native CUDA adapter要求mask='0'、而当前传已核UUID失败，0generation/0候选。14:15已主动取消余池，不能称有质量结果；原controller没有最终closure，completion-incomplete已记录。
- 17590 scheduler596秒/3576GPU秒；最后batch到14:15:01，保守597×6=3582GPU秒。连17587合计6216GPU秒。原作业/原件不重开。
- v3只兼容已核单GPU UUID，保留数量/PCI/设备节点/期望UUID/namespace检查；加生成前入口失败即终止后池。两个臂共同池预留2400→2200秒，搜索预算不变，变更已在执行前告知用户。
- v2源码b2f82aec6246336d095a7b7b088e3293761749e6已push/ls-remote一致，planSHAdf7b44e3a89f5c6fd110424aeffd5ea7ad569cafa8a139ea667c1083614ab6e8；路径同v1前缀改v2。准备时重复创建配置的CPU失败另存v2-prepare-incomplete-1，无GPU使用。
- 32配置/16对配平及原生搜索实例化通过；九项CPU测试通过，另1项Adam/AdamW/SGD被动观察器参数字节一致检查通过。无GPU准备原planSHA06a81639237cedc1fde6d550559cb9a1f9578254a4931f5f091e59e46aee768a保存在prelaunch-preparation，数据/config/seed未改。
- 不另开GPU容量或模型验收；提交前输入hash检查无GPU分配。
- 真实标签/预测/候选留远端私有；只导出本轮聚合/行级安全指标。观察器覆盖常见优化器，未观测不否定成绩，host时间不是CUDA kernel时间。

## 可直接复用，禁止重跑验收
- 17571 joint2+4：10原程序/10短请求，150/588步、输出一致，full_capacity_gate=true，8508GPU秒。512token请求全length，不能说完成agent生成或质量收益。
- 17570六GPU：14/14原UNet、588步、91输出比较一致，1428GPU秒；无模型服务，不是2+6。
- 17576原factory：三正常UNet+三已知exit17，6/6；191GPU秒。补丁A就绪/清理、B丢失内核报告和gateway等待竞态必须配套；不改学长分支。
- 精确bundle在sandbox_scheduling/resource_unavailable_20261011/collaborator-patches-v2；gateway unique receipt SHAac890ba1a61d371e04f8c1b8faec87b20d64b10a10c95b027656745baa36313e。
- 原b8与最新f7在本轮所用解释器/MCTS路径无diff；复用原生开发adapter，仅增加rmse指标枚举，两臂相同。
- 17577/78/80跨节点空命令失败；17579gpu27本地空命令4/4。交管理员，不再诊断/升级镜像/换CPU。旧Held12535不动。
- 历史OpenBLAS EAGAIN根因未确认；成功容量不替代故障时UID/cgroup证据。可选数字旁路16测试已过，不自动部署，避免继续工程膨胀。
- 上窗27job已闭合：scheduler36260GPU秒；计至最后step的保守包络37030GPU秒(10.286111111111111GPUh)，非实际账单证明。

## 科学边界
- R14有限系统信号保留：17366两源码12/12，pipeline/share2中位1.248439822872127，但CNN时序漂移未排除，原fixture不是质量基准。
- 17368文本live原门false：16尝试15正常、有效反馈池差-4/+5；仅3/8完整分对全负，全8事后有效性排序2胜5负1平。不救旧门、不汇总异质阳性。
- 不自动恢复critic/HCE/多保真/Probe/TD/score-channel/K>=1。
- first-960、Target-300、Target-522、D_val、官方test、16560导出仍关闭。
- 当前没有新的重要、独特、强基线跨任务同预算方法确认；不承诺正结果。

## 工作区、权限与现场
- 活跃checkout=C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001，detached HEAD有意；旧aira-dojo-codex-20260813用户dirty不动。
- 本轮闭合提交前公开head424a33a8dec044363d00cb37c4de758ab8f6e8f7已复查，当前HEAD以git log为准；实验source仍9b23d621。学长64fd78e98cfdc945b1af03f29f570975d58b88b7于00:43再次fetch无更新、未改其分支。原Git hook曾MSYS拒绝，独立guard通过，不冒称hook通过；本轮仍需发布前guard。
- 用户未跟踪报告phase1/reports/给学长_MLE沙箱资源调度进展_20261009.md保留、不stage。
- 17587/17590/17592/17656均已闭合，本轮未再提交；旧Held12535未动。排除projgpu7/8/33、gpu36/38；旧MLE镜像不投projgpu39。
- SSH linux5；PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
- stage=/research/d7/spc/yzyang4/resource-diag-stage-20261011.M5wKjU；研究盘4TB至2027-08-30。
- Slurm19.05.4无--exact；hint=nomultithread核物理CPU；SCP返回session须等exit0；不要在计时GPU时重hash大镜像。
- 凭据只远端，不回显/导出；新材料先credential scan；不改全局limit/firewall、不碰他人进程。
- 本地Windows python不可用；WSL缺Pillow，纯函数可测，完整24测在远端已有venv通过；没有安装依赖。
- 记录器/资料工作不替代真实效果；本轮不新建automation/thread/goal。
