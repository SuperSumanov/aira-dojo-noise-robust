# 当前短交接 — 2026-09-19 22:49 UTC

14165已完整关闭，4813秒/6卡；唯一读出在独立AUC一致性检查失败，原readout-claim保留、无summary，不能报胜负。只读diagnose_closed_pizza_auc_20260919.py正在定位，不重跑GPU/不改提交。随后已提交同原选batch顺序对照14167，22:47最后观察RUNNING/47秒、服务加载中。精确身份、版本和边界分节如下；未复核动态状态仅称最后观察。

## 授权、边界

用户21:15UTC恢复三小时会话内工作，目标09-20 00:15UTC。不新建任务/自动化，不例行写报告；自主实验和正常push有效。先fetch、CURRENT_DIRECTION顶部、此文件、核现场。目标为固定总资源的真实MLE收益；缓存条件续跑只是开发检验，不是完整E2E。27B为较弱低成本生成器。
first960/Target300/522仍封；不恢复HCE/多保真/Probe/score-channel/K>=1/G0/旧失败cheap选择器；不微调agent底座。不改学长分支、共享source、既有冻结root；代码/日志/回答远端私有，密钥仅远端.env，不回显/本地/Git。

## 已闭合、评分待诊断：14165 Pizza完整时限

ROOT=BASE/comparison-pizza-full-deadline-20260919-yaywhbo1；commit a37e3595a62989746c5ffb96943bbfea8ec65e96；prepared a153be4e55a98da9e07fb75f60cee4d320da5aa91b551ce7b65bbf7967ef4ee3。22:46核COMPLETED/4813秒/all_four_episodes_closed，0/1/2由共同硬截止关闭、3正常结束。唯一e7d969读出报independent numerical grade，不能重跑主reader或覆盖claim。先诊断精度/官方定义，不放宽门凑通过。
固定Pizza原seed1/2×native debug / uniform-cache-then-debug，35分钟每episode/20debug，首次原生接受即停，第二组交换lane；gpu28六卡24CPU100min≤10GPUh，0API/fit。两独立双卡服务+各一任务卡；启动不计episode但全allocation成本计入。cache RNG预先固定，未按新分数选。
full-deadline策略在14146效果前冻结：API不传max_tokens，vLLM默认/上下文限制；debug/analyze均用episode剩余时间，无额外1200s/300s上限、无重试/截断代码抢救。exact-source进程级overlay只改local，共享文件不动。原model generation_config无max_new_tokens，镜像get_max_tokens源码已核。实接线26mock/四完整循环/绑定桥CPU PASS，非效果。
监控status_comparison_pizza_online_20260919.py，未闭合不读结果/incumbent。闭合后readout_comparison_pizza_online_20260919.py --reader-commit e7d969f1102a589cc2d887df9eb02cf48dad9047唯一读出；该版本已上传BASE。评分AUC higher-better，独立rank_auc/穷举测试；独立verify_comparison_online_results_20260919.py支持auc_delta。旧Spooky reader已闭合不重跑。

## 正在运行：14167同原生批次只换顺序

run_comparison_native_batch_order_20260919.py / comparison_native_batch_order_plan_20260919.json：同原第二入选程序和first debug cycle，只换repair→second / second→repair；两阶段均做（不因首成功停止），共同35分钟、按有限内部metric最大选最终提交（ties保首个）、首有效延迟单独记录。2seed×2arm、6GPU/100min≤10GPUh，已在14165终态后用冻结root driver提交14167；22:47观察RUNNING，预计若正常预热则约00:07UTC闭合。开发条件单batch而非完整搜索E2E。
22:05 CPU prepare c2c4e21b失败ROOT comparison-native-batch-order-20260919-8pdj0u_r，未提交GPU：模拟分类用字符串pass注释，原生formatter改空格使之误识别为sibling；改AST只识别单Pass。新ROOT comparison-native-batch-order-20260919-hz3c589n，部署commit dc4a7dbc6951f5bd8d24b49ca7eb2e2de3d5ccec，prepared25d55a42517e586b677dd72a7296a4453c0c68bfda03c551eeb30570e8274428；真实原生CPU预检通过，尚未提交。168相关单测通过，随后计时新增2项测试所在20测试模块组通过。独立batch reader已上传到BASE/comparison-batch-reader-20260919-Pt3BsrGK，commit ee3c6da24bfdf453dbdf0e124deca9b06500b10e，wrapper SHAe833ab7a130c61f78d91c02f9a770624ebb4bb3c83e4f4421124e0ddb527d105，shared SHA2a6e57da3bfcef9d157d8abdcc7e1e3a6a727789bf002c9555457fd7b35cd948；四依赖本远端hash逐一匹配，不改BASE旧reader。审计每次内部metric incumbent更新、首原生接受而非首官方有效的时延；只累计已完成请求的实测latency，下界非全量耗时，不给截断调用补值。14165仍只用BASE e7d969 reader，禁混版本。
14166 original-second闭合88秒2GPU/.04888888888888889GPUh，ROOT comparison-pizza-selected-second-20260919-u2nkqs5y，prepared51f32ba6bc25e6e25a58f8a1f8c4594206c2780c6cdcc5c9cbdd96b6e4400103，reader7ae3622574c926e9e044ca686b7dd1fc7c9c1ad6已唯一读出。seed1第二原选有效AUC .74184/87.09747589100152s，seed2 exit1失败；未native分析，非策略收益。本地results/comparison_pizza_selected_second_20260919，summary19668b47b51cbcec7c99af1ea9d16e7d8559ad02274b28c5c65ef74bb9da0d0f；仅安全summary/runs/cpu-preflight，无原始代码。不重跑。
全25初始池严格延迟有效兄弟机会0；独立事后次级7组成本较小但质量3胜4负，所以不用首成功替代最终质量。不修改零结果或称普遍更优。
未来完整ForeTS候选批次开关已写为forets_ready_batch_patch_20260919.py：只对exact be933生产fixture返回补丁bytes，native默认关闭，ready_first仅推迟debug。7CPU测试覆盖不同成功/失败/步数门的默认等价路径、无bug时启用等价、同候选/critic/生成；未修改远端源、未部署，不当E2E收益。下一实际完整搜索仍须预算/环境/源码接入，无条件正收益或方法新颖性尚未证明。
新增真实config默认/验证测试亦通过。注意当前ASSETS/source基于b7f8批次ledger接入、与be933 fixture不同；不能把此补丁直接声称已接入当前完整运行器。完整E2E还须统一逐动作incumbent记录与硬截止，原wallclock仅整轮存结果；不让两臂提交持久化规则不同，不自动投未核矩阵。
旧Pizza root comparison-pizza-online-20260919-1qiyjkqy（prepared8192d964d11b042d49724c854947839faa01153ea2a96fe84500a9dc00966e6f）从未提交，禁投/改旧root。

## 已完成，不要重做

14146 COMPLETED/3008秒/5.013333333333334GPUh。ROOT=BASE/comparison-online-continuation-20260919-qpw9ys94；部署8b117df27026cf2eef7920bd2332cc03fcbab48e；prepared99cff06463fa986bfa6a5d732d81cc1b392b4d08b61a194bf78c12cd4bc9783b。唯一reader版本9822af286bd900389f52960575b1f902f1a5c2a7已执行。
summary a958946c49bca5248c0ca7e647c71b22a493231657ee18f73ffd219ecb5c196e；本地results/comparison_online_continuation_20260919，独立PASS。两physical run一胜一平/p=1，不能总体确认。cache arm seed1有效loss .50338/795.8959797470015s，其余三条无有效提交且32k截断。两实际cache均失败，成功来自后续debug；两臂首次debug提示SHA相同、回答不同。单次优势可能生成波动，不当缓存机制或生产debug被击败。mechanism-diagnostic.json已一次生成，不重跑reader。
14149前缀COMPLETED/10秒2GPU，ROOT=BASE/comparison-pizza-prefix-20260919-0guhqznb；commit9822af286bd900389f52960575b1f902f1a5c2a7；prepared0581d1ac911f6152caff200c6f11ad5eca3ec49e76ec655afbe2da78df23c68e，summaryb3fff2aa4228b7b09e82296c0f3929e4fa7b9083a6bb510cdfcef63f28ddaa29。seed1原门通过、seed2因humanize“a moment”尾缀失败；独立按原exec_time精确去尾缀后两核心NameError匹配。原summary保留，prefix-format-supplement.json已闭合；cache结果未读。
14135第三Spooky银行闭合6程序2有效4无效/6.6883333333333335GPUh，summary7dd466d42627e642ded6cd34af5660e0d0f6f76ed1150fb423565e13f7fb9371；原门失败和严格格式补充匹配同时保留。历史debug有效.38821、四cache一有效.35692，非在线增益。
14115/14128银行、14127/14133新debug、14134截断、14136native接受、旧Leaf3池/Spooky2池及reader全闭合；细节CURRENT_DIRECTION/results，不再重复GPU/读出/验收。

## 并行核查

AGR-V已有未验证池和动态生成/验证，Recovering Wasted Compute已有回溯+兄弟选择，AI Research Preference Models已在AIRA排序/E2E。缓存/排序本身不是新颖；先验证公平预算下的真实收益，不把小样本升级成论文主张。
22:26补充只读primary核查：AGR-V(https://arxiv.org/html/2605.17609v1)建模固定标量成本、找首个二值通过者；其结尾明确变量成本/并行扩展。Recovering Wasted Compute(https://arxiv.org/html/2608.10424v1)已有同draft规模消融和MLEvolve严格TS对照，不能批评它只靠多draft。Matryoshka Agent(https://arxiv.org/html/2607.25090v1)已有层次调度、下游分支偏好和orchestrator/RL训练；不是我方新颖性，更不能借其恢复K>=1或agent微调。本次窄问题是同原选批次执行先后在实际最终提交上的影响，未证明重要/新颖/普适。
21:30学长head仍e4181fac5edb319e14d4d819088778d5d2708912；0918目录双读仍0可见文件，listingSHA d36f39e6e9476279df19da46f006f182236737f29e64e5808e93733d676ae239，仅当前可见列表，非学长没上传。

## 环境、发布

本地C:/Research/New/my_project/MLEvolve/aira-dojo-codex-20260813；SSH linux5；BASE=/research/d7/spc/yzyang4；Python BASE/venvs/aira/bin/python。SLURM_CONF=/opt1/slurm/gpu-slurm.conf，4jobs/8GPU，旧held12535不动。
MLE原镜像在gpu28 RTX3090（gpu27兼容、adapter锁gpu28），禁projgpu39/改Torch/CPUfallback。镜像BASE/aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif。
ASSETS=BASE/local-qwen27b-20260914-zcx1k1dy；27B revisiondc430725f831dd90d9271738b877879a46a82239，18文件36808331288bytes，不重下载/验收。ASSETS/source原生算子/FreshContainer；DONOR=BASE/forets-fresh-integration-20260914-ih6u0mpw。研究盘1TB至09-29，延期未知，容量门通过、无需清理。
0912五包BASE/comparison-quarantine-20260919-_tda9fh6，703326526bytes；只新Qwen46config/43journal，nodesSHA370976e31c8a9f501bc75fb7826f529f85b0e34059146291f2e7bb3cab4062c9；保护LATEST/日期/journal隔离已核。
分支codex-prospective-decision-v1-20260814，只正常push myfork HEAD:phase1-value-critic。22:12公开HEAD20ed7d45cc43d24c1ce7ee7ac7673e55cc1c915c，ls-remote匹配，23待推文件/凭据与敏感路径0；本地后续新增待推。无关untracked保留。发布前扫全部待推blob凭据形状及敏感文件名，仅报数量；结果JSON/CSV -text；标题无数字或只复制已打印值。
