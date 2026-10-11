# 当前短交接
更新：2026-10-11香港14:47。旧排障长交接已保存在Git4279975d；这里只保留当前事实，未复查的状态写最后观察。
恢复：fetch → CURRENT_DIRECTION → ROUTE_DECISIONS → 本文件；不得回到旧8月路线。

## 最新用户裁决与当前实验
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
- 17592在香港14:26:12于gpu3 RUNNING，24CPU/6GPU；14:46最后观察首池8搜索/8预览已完成，6条在首次240s生成请求上限失败；另2条首候选执行超时，均继续原生搜索。2返回/0有效开发分，0完整对照；不能报质量收益。cap02:30:00，正常约16:53完成、allocation上限16:56:12，严禁重复submit。
- 服务仍健康，日志采样峰6运行/2排队；这不是队列致因证明。6个请求失败留在32分母，不能中途调240s上限、补seed或放宽原扩大门；按冻结对照走完且不自动扩跑。2条仍在运行的轨迹中候选累计队列等待各0.04406109801493585/0.056249343091621995秒（含后来入场候选），不把执行超时说成等卡。
- 独立只读image_live_funnel_20261011.py仅统计本批数字回执，不读保护集、不改冻结结果；0优化器回执不证明无CUDA训练（回执只在成功评分后抓取），最终需结合遥测。当前尚无改善信号。
- 有界一次性结束复算PID3971306已确认，最长8h、只等17592；完成后读取冻结开发分并核验32分母/物理核/全成本，不提交新job。stage/image_live_status_20261011.py v3读计数；completion-claim.json记录进程。原8月自动化指令不恢复。
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
- 最近公开head 7d38dc89de25b32a28d4543f05e0086750091c1f；14:44 fetch学长到524b5e0351090795c6bf09f32c0fafbfb41d71d4（13:59仅删除sample.jsonl/samples.jsonl，未读内容，无新outcome/实验代码）。只推自己的myfork/phase1-value-critic，FF、不force。
- 用户未跟踪报告phase1/reports/给学长_MLE沙箱资源调度进展_20261009.md保留、不stage。
- 17587/17590均已闭合；v3只申请gpu3六卡24物理核。旧Held12535未动；排除projgpu7/8/33、gpu36/38；旧MLE镜像不投projgpu39。
- SSH linux5；PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
- stage=/research/d7/spc/yzyang4/resource-diag-stage-20261011.M5wKjU；研究盘4TB至2027-08-30。
- Slurm19.05.4无--exact；hint=nomultithread核物理CPU；SCP返回session须等exit0；不要在计时GPU时重hash大镜像。
- 凭据只远端，不回显/导出；新材料先credential scan；不改全局limit/firewall、不碰他人进程。
- 本地Windows python不可用；WSL缺Pillow，纯函数可测，完整24测在远端已有venv通过；没有安装依赖。
- 记录器/资料工作不替代真实效果；本轮不新建automation/thread/goal。
