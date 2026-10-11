# 当前短交接
更新：2026-10-11香港，17587失败后。旧排障长交接已保存在Git4279975d；这里只保留当前事实，未复查的状态写最后观察。
恢复：fetch → CURRENT_DIRECTION → ROUTE_DECISIONS → 本文件；不得回到旧8月路线。

## 最新用户裁决与当前实验
- 用户：跨节点问题由其问管理员；先用已跑通的两卡服务＋四卡执行推进同预算真实收益，不再反复验收。
- 本轮只改每执行卡的FIFO候选许可1→2；四GPU各固定配对两个独立run，保持run内MCTS顺序。不是全局迁移/一般phase-aware强基线，更不是SchedMate复现。
- 新任务：aerial-cactus-identification、denoising-dirty-documents。仅从既有prepared/public训练数据划80/10/10；10%开发评分引用仅宿主可读，另10%不复制不评分。新视图不是独立盲评。
- 2任务×每池每任务4seed×2臂×2轮=32条原生MCTS；ABBA四池；每run1500s、每候选300s、每池2400s。
- 单节点gpu3，2服务+4执行RTX3090；24物理CPU=服务8+4lane各4，lane内两run各2核，两臂相同。
- 27B INT4固定本地模型；medium/8192输出；不训练agent底座、无付费API。GPU上限10200s×6=17GPUh，含启动、失败、空闲、清理。不复用旧批余额。
- 主终点原生选择的外部开发分；全32分母、无效/缺失不填0；有效CUDA反馈及任务池最好分次级。只有2个配对池重复，32run不是独立调度重复。
- 扩大门：完整32终点/16有效分对、两池CUDA有效反馈都增加、逐任务配对分中位不负且至少一任务正、无更多无效终点、等预算/隔离/清理通过。不换seed、不因单池结果加跑。
- 本轮路径=/research/d7/spc/yzyang4/scheduling-image-live-2plus4-20261011-v1。
- 17587已FAILED闭合：八worker在搜索前退出，0/32搜索、0候选；服务正常。原入口错误要求4逻辑线程，但lane回执实际4物理核/8SMT线程；不是CUDA或跨节点故障。439秒×6=2634GPU秒，原32分母与失败保留。原planSHAb44f6002b5da35d953a0ae1ead7b88d7776428cf7e775a26475fcce545837e78。
- 独立v2拟原32配置/seed/2400秒池，不改变任务/模型/评分；仅按物理核分成每worker两核、CUDA初始化前绑核。五项CPU回归通过。新cap9720秒×6，合并旧失败60954GPU秒，不超原17GPUh；尚未提交，不能称开跑。
- 32配置/16对配平及原生搜索实例化通过；九项CPU测试通过，另1项Adam/AdamW/SGD被动观察器参数字节一致检查通过。无GPU准备原planSHA06a81639237cedc1fde6d550559cb9a1f9578254a4931f5f091e59e46aee768a保存在prelaunch-preparation，数据/config/seed未改。
- 原提交前完整数据/模型/两镜像校验通过；v2只做入口CPU回归和源/输入确认，不另开GPU容量或模型验收。
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
- 最近公开head bdefe67729d69e39097199ba6b2e27c6de2962f3；学长f7ccd79323112b10ccc82d8e9ec9d6cf089df607，未见更新。只推自己的myfork/phase1-value-critic，FF、不force。
- 用户未跟踪报告phase1/reports/给学长_MLE沙箱资源调度进展_20261009.md保留、不stage。
- 提交前只有Held12535，未动；本轮新17587只申请gpu3六卡24物理核。排除projgpu7/8/33、gpu36/38；旧MLE镜像不投projgpu39。
- SSH linux5；PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
- stage=/research/d7/spc/yzyang4/resource-diag-stage-20261011.M5wKjU；研究盘4TB至2027-08-30。
- Slurm19.05.4无--exact；hint=nomultithread核物理CPU；SCP返回session须等exit0；不要在计时GPU时重hash大镜像。
- 凭据只远端，不回显/导出；新材料先credential scan；不改全局limit/firewall、不碰他人进程。
- 本地Windows python不可用；WSL缺Pillow，纯矩阵3测过，完整7测在远端已有venv过；没有安装依赖。
- 记录器/资料工作不替代真实效果；本轮不新建automation/thread/goal。
