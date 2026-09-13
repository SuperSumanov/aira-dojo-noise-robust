# 短交接：参考条件新八次已开跑；并行补齐旧首决策池
最后核现场：2026-09-13 04:54 UTC。用户要求本会话持续三小时，开始02:58、目标05:58 UTC；不建automation。
恢复先fetch→CURRENT_DIRECTION 0L191及本文件→核现场，不按早期摘要重投。

## 当前唯一收费搜索
13213/13214已04:32:45单次提交；04:54仍在gpu28运行，分别第二/第三条搜索，尚未读成绩。
ROOT /research/d7/spc/yzyang4/forets-wallclock-20260912-5_czzimk
STAGE /research/d7/spc/yzyang4/forets-reference-stage-20260913-m3U9toWD
source f1cdee3a9e553e8efeedaa1a66a2c6bd778f9798
controller 9cf2e7ec921730630568f3a090d81ca49cda46d2
prepared 82a85e630b4d58830cd382d2b7af549c454aed3645a2b3ca3c1f7d36e74fd571
AUTH 96191b7393556fc5c978d82d2f3f2789ffb5f8c8c0243605b425df6843c07540
readout-plan 4b3529a780484723475b8e7cd0c0169b8df5f26a5ffe552c69133b288430e282
本地source release仅forets-reference-source-20260913-v2；tarSHA39eb073114b97d78b9ed309b126588bedfffed38fa6f0ea3012dcc6d4376aefa。
矩阵Leaf/Space×32/33×random/reference-critic=8；两份单3090/6CPU/90分钟，总上限3GPUh。
每run600秒、程序300秒、RF共同起点计费；四候选选二、原UCT/debug、Flash/Plus单票。
只有critic请求增加已执行parent/incumbent/最近两节点参照；不含metric.info/外部grade/未执行结果。
interpreter五文件与亲本353...逐字节相同；失败重连修复没有部署。保留严格120秒就绪、已披露间歇风险。
12参照/独立回放测试、两臂实际batch请求接线、完整八配置和deadline接线通过。
原100人民币/10USD责任帽；激活时完整承接1140调用/结算3.558619389/责任4.958619389USD/两旧未知，旧账y_p2tlmi已封。
两block route均rc0后才提交，禁止重复activate/route/submit。04:54账1196调用/3654024478nUSD结算/5754024478nUSD责任；
unresolved=3其中包含在途调用，不能未闭合就把它说成新增永久未知。原两旧未知仍保留。
catalog第一次因未加载代理在任何新调用前失败；source严格shell又退出，但核1140未变，之后正常环境成功。
控制入口用STAGE/forets_reference_control_20260913.sh；正常source远端env_setup后才设严格shell，不能输出环境/凭据。
全8终态前不看本轮成绩/选择；闭合后仅一次STAGE/readout_forets_reference_20260913.py ROOT，包含独立参考回放与原提交重评分。

## 已闭合双分支seed30/31
13201/13202 ROOTy_p2tlmi，source35321718fef54f1907b469ab44334a30fe66b6cd/controllerbe59c736...。
04:01:43主reader唯一读出verified；本地results/forets_branching_s30_s31_20260913五主产物hash一致。
7/8技术合格、3配对：Leaf30平；Leaf31 critic.37782 vsrandom1.51485；Space31 critic.79655 vsrandom.80690。
Space30 critic.81839但random首次内核故障，整对不合格，不补0/补跑。
关键：Leaf31两个critic池选集及顺序都与同池随机相同，最终好程序来自debug；不得将胜出归因critic改选。
真实分叉6条；固定120/240/360/480/600曲线40行、9原提交独立重评分。Leaf31好结果360秒已交付。
本轮1.3375GPUh、搜索API.396137196USD。报告FORETS_BRANCHING_RESULTS_20260913.md。
finishSHA0bb7cdb563ceb2274645926314ab5bdf74d5b043bebeb7356e329bea0053fd95；
parent-facts已固定，旧paid账封闭是正常交接，不得重启。

## 并行零API机制补齐（13218完成并已唯一读出）
计划四个critic首个后基线池batch2，每池2未尝试原代码，共8；不挑好pool、不编辑/重排/修复/重试。
单gpu28/6CPU最多90分钟/1.5GPUh，原source353...、原任务镜像。出现基础设施错停止；未知不填无效。
STAGE /research/d7/spc/yzyang4/forets-branching-completion-stage-20260913-326VBH
本地derive_branching_completion_20260913.py从已运行12程序adapter机械派生8程序；输出release/forets-branching-completion-tools-20260913。
仍用内部文件名forets_pool_completion_20260912.py与旧root前缀，实际新协议FORETS_BRANCHING_COMPLETION_PLAN_20260913.md。
ROOT /research/d7/spc/yzyang4/forets-pool-completion-20260912-cwhdnjnp；04:39:49单次提交13218，COMPLETED/88秒。
04:44:31 readout_branching_completion_20260913.py唯一读出；全部8补齐，0API；不要重跑reader覆盖已有结果。
summarySHA eb1e8e1f61c4e95040b1345e6f1c5669051f7d3314255fd817560aa881d01be2；本地results/forets_branching_completion_s30_s31_20260913已下载。
三池4/4原程序无效；Leaf30三失败一历史未知。新8全部程序异常，原8保留7失败1未知；不把exit0当有效。
错误是列名、dtype/类别处理、旧LGB fit接口；没有父节点文件缺失报错。额外父节点核验全部首后基线池确实improve已执行RF。
报告FORETS_BRANCHING_COMPLETION_RESULTS_20260913.md；直接有效性不含debug，不能当新的e2e/critic普遍无效结论。

## 并行准备（未生产接入）
FORETS_REFERENCE_NEXT_GATE_20260913.md已在32/33揭盲前写定，不能看成绩后放宽。
forets_action_delivery_20260913.py默认关闭的逐已解析动作交付记录及独立read_forets_action_delivery_20260913.py，15测试通过；不动当前source/主终点。
还需实际接线才可未来启用，不能把本地测试冒充交付收益。
不要自动换Plus生成器：旧三批24程序Flash8/12、Plus5/12有效；不要重复旧方向或无依据改父节点。

## 内核支线：不要部署失败修复/宣称根治
原失败：120 ingress/0匹配egress/3foreign，0候选执行。32次login纯连接通过；13204节点64次通过（204秒）。
13205 source2248...的首次同内核重连保护注入失败：109.99秒新通道仍无回复，总120秒，0候选dispatch；129秒FAILED。
xc26fkd0是未激活准备包，0付费搜索。其CPU接线通过不能替代失败的实际通道测试。
13206四种session形式×4组全部重连通过；一次初始5秒失败后重连恢复。63秒，0API/0MLE。
注入失败只有一次，尚不能证明注入必然导致自然故障；会话标识不是已证根因。
原镜像库源码已查：connect/nudge/Session、buffer恢复；不升级镜像/Torch、不CPU回退，不把resilience当模型收益。
代码forets_initial_channel_recovery_20260913.py只有7单元测试过，当前生产未引用。

## 不变边界及其他
SSH linux5，Python /research/d7/spc/yzyang4/venvs/aira/bin/python；原MLE镜像只gpu27/gpu28兼容3090，不投projgpu39。
Key只远端aira-dojo/.env OPENROUTER_API_KEY→PRIMARY_KEY，不复述/重索要/本地存储。费用保留所有旧未知。
学长myfork/dojo-reproduce04:22仍113e25e7fa2570cb5f60401d051a1de3cce307c2；本地Qwen服务接入仍待外部回复，不改其分支。
公共与本地04:48均a569f0d48c4d290a66d11a6b73ffb0e2426249b2；本轮报告/源需正常安全push myfork HEAD:phase1-value-critic。
first960/Target300/Target522封闭；无agent底座FT/RL；不恢复HCE、多保真、Probe、score-channel、lookahead。
旧held12535不动；保留无关未跟踪目录。研究盘2026-09-29到期，续期未知。
