# 当前短交接
更新：2026-10-09香港；旧79行完整留在Git 2b634744a92d17e5732419f11be30f6c0e9da04a。原实验与授权不因压缩改变。

## 当前六小时窗口
- 用户14:11授权持续自主推进至约20:11香港；尚未完成窗口，不提前宣称六小时研究。主线R14沙箱资源调度，不恢复旧critic/HCE/Probe/TD/score-channel/K≥1。
- 活跃checkout：C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001。fetch→CURRENT_DIRECTION→ROUTE_DECISIONS→本交接；旧aira-dojo-codex-20260813的用户dirty保留。
- 14:52独立CPU诊断17267完成：服务12物理核/执行6，物理和逻辑CPU集合均不重叠，36GPU秒。标准Slurm nomultithread hint有效，不叠加冲突cpu-bind；不是科学收益。先前session92814连接超时未提交，现场核无intent后才成功新提交。
- v5/17262已CANCELLED：14:37:37–14:42:56，319×3=957GPU秒（0.2658333333333333GPUh）；16条0启动、服务未ready。服务实际9物理核违背12核契约，候选前停止；旧root不重开。operator_stop.json是取消回执，非合成完成结果。
- v6/17273已FAILED：15:12:42–15:12:56，42GPU秒，0搜索。包装入口缺host导出，生成容器shim发生ImportError；我方接线遗漏，非节点GPU失败。readout-v1一次闭合/本地live_v6_closed，旧root不重开；plan9bd8dc3b786c69f3a98fb892f49722c5a4c545532346e46be0e392108ae5ad9a。
- v7/17279于15:30:54在gpu27实际开跑；16:23:34最后核block0/1各四条正常收尾，分别12/14候选回执、各6评分回执；两块均清理和1320秒预算闭合。block2四条已开始、1返回；block3未开始。未读中途分数，不以回执数判断收益。首次服务启动436.65462437830865秒、后两块185.16286213696003/175.6052068863064秒，全计成本。上限90min至约17:01；plan86aa8f7a3d534ef1eaaa5475482a8838fe29c06f1ee30cb367cc05aae411c774。禁止重跑prepare/submit。
- v7 root=/research/d7/spc/yzyang4/scheduling-live-search-20261009-v7；stage=/research/d7/spc/yzyang4/scheduling-entry-fix-20261009.yAyBZB；入口live_entry_fix_trial.py；source44fcf9b433d0ed26c7799f82e5052a82d888f5a1。prepare会话36436断线但原PID1454405继续；最终preflight完整且PID退出才提交，不把传输退出码当进程成功码。
- 本地37测试/34通过/3Linux跳过，远端12通过，含实际shim导入和入口不重复初始化的反例；纯工程测试不计科学样本。生成服务在模型加载前核12物理核，执行在候选前核6核且逻辑/物理/GPU集合分离。
- v7矩阵保持v6所有任务/种子/预算，仅修入口（未见候选结果，不换种子）；不是新科学复制。Pizza/Spooky既有合法dev；4独立run/块，ABBA四块共16条600s；种子142901–142904、143001–143004。同27B/2GPU12物理核生成＋1GPU6物理核执行，只变FIFO许可1/2，保留run内顺序。
- 每块固定1320秒，包含服务启动、搜索、清理与显式填充；4块5280秒，整个作业最多5400秒/4.5GPUh。全部GPU空闲与失败计入；固定预留不等于成本最优的生产部署。
- 新问题是无结果筛选的反馈吞吐：不按首块生成有效性决定后续，全部无效/失败保留16分母，安全/基础设施异常才停。不同于v4失败资格试验，不是复用余款或放宽原门救结论。
- 反馈信号门：16正常闭合＋4块结构/预算核验，两个池配对均严格增加有效及时反馈且不降低有效终点数；最终质量严格门仍要求8对完整有效分数且逐任务中位差非负。缺失不补零；2池配对不是16独立调度复制。
- 600s相同不足以保证全成本相同；v5固定池槽，另报完整Slurm账单。客户端240s只是原生执行超时配置，可能另有中断/清理时间，不宣传严格240s物理cap。
- 只读观察：stage/live_status.py --version v7。闭合后用root/live_readout.py root root/readout-v1 --allocation-gpu-seconds 实测值，一次writer；再独立复验，禁止运行中改源/门。
- 服务alias qwen3.8-27b，实际qwen3_5/compressed-tensors4bit；不猜AWQ或更强生成器。编译cache跨块共用，活跃KV随服务重启清空。当前运行期间不做同节点大文件准备，避免I/O混杂。
- 闭合后新增只读诊断58b817dbd89e00c41ee2a7cb169011371b244113：live_queue_efficiency检查有空许可仍排队的时间；live_feedback_diversity核每run有效返回的代码/提交逐字节重复和反馈到达面积。仅旧门外描述，不替换门、不把任务槽秒当GPU节省；本地45测试/42通过/3Linux跳过。未运行v7分析writer。
- 强参照已本地冻结4a19588cb24cea8ed1d1b91f563d4ed06a68f4af：neural_width_trial.py/width_readout.py/width_contract.py；两既有神经程序各两实例，width1/2/4×3轮Latin顺序=36执行；相同seed42、训练量、单3090/6物理核；≤90min/1.5GPUh，非新任务/seed或live质量。当前未prepare/未提交，等待17279闭合后才做远端大文件准备。
- width暂存=/research/d7/spc/yzyang4/scheduling-width-20261009.kdFBrQ；本地10测试9过1Linux跳过。首次远端测试误早于SCP完成（test_width_runtime缺失，8项1error），不算通过；上传会话98854已exit0，主脚本/contract/readout/runtime-test四hash匹配，16:04重做正式Linux测试会话88417最终exit0、10/10通过（13.438秒），含真实flock三宽度。无GPU或候选执行。
- width准入在原worker外：四内核共同ready屏障后FIFO借还1/2/4，成功退出清理后释放，失败停后续不补样；保留原worker/程序AST。新增共同实际_gateway_port绑定，避免复用旧无效_slurm_gateway_port覆盖；闭合后核实际子进程端口互异。当前源码pin7577a95230515790ce58966bf5c6d3f486a6f6535d83503862aa8e80e6b33338。
- 16:45在v7成绩未读前提出条件追加live廉价强参照：2对4许可，另16条/新seed144901–144904及145001–145004/同ABBA、同任务和模型、600s/1320s池槽，3GPU90min≤4.5GPUh。仅v7全16完整+结构通过且width全36输出/步数/隔离通过才准备提交；不看先前效果是否阳性，不替代旧批次。source待提交，当前仅本地49测试46过/3Linux跳过；未prepare/提交。全部资格/失败含成本，不能为赶20:11延長。

## 上一批新证据与修正（已闭合，不能重开）
- v4/17255于13:59:17资格门停止：4/16正常收尾、3有效终点、4有效候选；余12未启动，0观测A/B配对，原门false。3×1105=3315GPU秒=0.9208333333333333GPUh；这是14:11窗口之前的成本。
- v4 root=scheduling-live-search-20261009-v4；source e3e93d788cc6d8775d441d6945cf08529df5c4fd；plan6a91d2934959681b977d2d43ca0ea991dd6a1d3b0ce65ab6d1a88a7b5225d025。readout-v1、phase-analysis-v1、diagnosis-v1均已一次写出，禁止重跑。
- 本地证据sandbox_scheduling/live_v4_closed；summary SHA f54f3501b0d87ebd0681b31481fb3e053db70a95e78ed2ae51451c3b4083cdb6，closed SHA2bfd41a3babee547bb58fc3653b6cd3550510101ac9bf1c6d0253b2d4c49a785。6份下载hash与现场相符，PowerShell独立复算16/4/3/4及3315通过。
- 一个超时候选租约约289秒；三个run第二候选排队273.8312957799062/275.5957983350381/273.134565920569秒，共822.5616600355133任务槽秒（不是GPU节省）。三run总排队308–330秒，另一run总租约359.91306385118514秒且0有效。
- GPU573个采样中利用率中位0、最大7%，显存最大266MiB；这是执行队列拥塞线索，非GPU计算占满/共享收益/最终质量因果证据。两个小NLP开发任务不替代神经训练泛化。
- 原读出器错误要求服务step=执行step、affinity逻辑CPU数=6；现场同job/服务step1/执行2/GPU分离、12逻辑线程，节点SMT2。旧摘要保留；未来v5用sysfs物理核与独立步骤/GPU身份核验，完整合成读出/反例已测。不借此改v4原失败门。
- 旧v3/17232在gpu24 native CUDA失败，16条0开始；17232/17234/17235/17250共21GPU秒；v2/17229排队取消0GPU；v1准备后撤回0GPU。都不复用预算/重开writer。
- gpu27迁移诊断17251因未等SCP完成失败1GPU秒，17252 native成功1GPU秒；工具返回session_id须等待退出，再验证hash后执行依赖。不得重演抢跑。
- 初次新增整批合成读出测试遇Windows系统temp权限问题，fixture改为workspace后通过；不是GPU/候选失败。Git commit伴随sh.exe环境警告，不能宣称hooks通过。

## 保留的正信号与论文边界
- 17128：12/12，两固定神经程序，pipeline/share2三配对1.2672909369785448/1.6617137953073626/1.6730949919847078；中位1.6617137953073626，sample std0.23107569245795057。150/640步和数值输出一致，资格＋正式1204GPU秒；同seed重启、非独立训练seed或live质量。
- 证据evening_overlap_v1_closed；source22566d06fc8de23d6c16cc2bd4a85b0858af0d66，summary c763de7c8ee00db5d4ba4219d49c4d864e573061368be9566f7d48d4cc0bc258；完整独立审计已通过，不重复基础验收。
- 17017大输入12/12中位serial/share2=1.6811874366439696，但参照较弱；16997四小程序36/36强参照中位1.3177936445362894。不可拼成新神经强参照。17014/17021等失败全部保留，详见CURRENT_DIRECTION/旧交接Git。
- SchedMate已有源码/历史/日志调度与干扰撤销；MARS调度论文已有跨阶段遥测、AIMD准入与continuation优先。不能把队列阻塞、动态准入或适用MLE当首创；尚无胜这些强参照或重要新方法的确认。

## 恢复与安全
- 15:38己方已安全快进push到2e571ee53218ec8d6d6dc5d20b3beea7084c5d1a；19提交全diff/62文件凭据扫描0命中，1敏感文件名是已审live_environment.py源码、不含环境值；未上传raw候选/标签/预测。16:23前fetch一度DNS失败，随后成功；senior a5519bc8e0c85d0a3bd78c478ac8332120d415d9(15:42)，仅读提交/path元数据，更新属offline-GRPO/数据处理，未读raw文档或改分支。己方58b817db/4a19588c尚未push。
- 未跟踪报告phase1/reports/给学长_MLE沙箱资源调度进展_20261009.md是用户上一轮要求、13:01版本，保留，不冒充最新或主动另写长报告。
- SSH linux5；PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。gpu27/gpu28 RTX3090已知兼容；不投projgpu39、不改驱动/权限或静默退CPU。旧Held12535不动。
- first-960/Target-300/Target-522、D_val、官方test继续关闭；16560数值导出仍待单独授权。不输出密钥/raw候选/回复/预测/标签/权重；不使用付费API、不更新agent底座。
- 研究盘总配额4TB、至2027-08-30；共享文件系统df余量不是用户配额。长期经验索引在旧checkout的phase1/memory/MEMORY.md，按需读取。
