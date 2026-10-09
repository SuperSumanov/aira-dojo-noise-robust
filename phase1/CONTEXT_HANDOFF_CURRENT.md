# 当前短交接
更新：2026-10-09香港；旧79行完整留在Git 2b634744a92d17e5732419f11be30f6c0e9da04a。原实验与授权不因压缩改变。

## 当前六小时窗口
- 用户14:11授权持续自主推进至约20:11香港；尚未完成窗口，不提前宣称六小时研究。主线R14沙箱资源调度，不恢复旧critic/HCE/Probe/TD/score-channel/K≥1。
- 活跃checkout：C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001。fetch→CURRENT_DIRECTION→ROUTE_DECISIONS→本交接；旧aira-dojo-codex-20260813的用户dirty保留。
- 14:52独立CPU诊断17267完成：服务12物理核/执行6，物理和逻辑CPU集合均不重叠，36GPU秒。标准Slurm nomultithread hint有效，不叠加冲突cpu-bind；不是科学收益。先前session92814连接超时未提交，现场核无intent后才成功新提交。
- v5/17262已CANCELLED：14:37:37–14:42:56，319×3=957GPU秒（0.2658333333333333GPUh）；16条0启动、服务未ready。服务实际9物理核违背12核契约，候选前停止；旧root不重开。operator_stop.json是取消回执，非合成完成结果。
- v6 root=/research/d7/spc/yzyang4/scheduling-live-search-20261009-v6；stage=/research/d7/spc/yzyang4/scheduling-physical-cpu-20261009.TEzCYJ；入口live_physical_cpu_trial.py。
- source e28fc36da474e58091676310cd20fd9bc314e679；15:00最后核prepare session29867仍进行中，尚无plan/preflight或新GPU提交，禁止重跑。首次权限审核超时未创建进程，获允许后仅重试一次。实际上传session9186退出0，三个改动核心SHA一致。
- 本地36测试/33通过/3Linux跳过，远端11通过，含完整16行读出和核重叠/9核反例；纯工程测试不计科学样本。生成服务在模型加载前核12物理核，执行在候选前核6核且逻辑/物理/GPU集合分离。
- v6矩阵：Pizza/Spooky既有合法dev；4独立run/块，ABBA四块共16条600s轨迹；种子142901–142904、143001–143004。同27B/2GPU12物理核生成服务＋1GPU6物理核执行池，只变FIFO许可1/2，保留run内顺序。
- 每块固定1320秒，包含服务启动、搜索、清理与显式填充；4块5280秒，整个作业最多5400秒/4.5GPUh。全部GPU空闲与失败计入；固定预留不等于成本最优的生产部署。
- 新问题是无结果筛选的反馈吞吐：不按首块生成有效性决定后续，全部无效/失败保留16分母，安全/基础设施异常才停。不同于v4失败资格试验，不是复用余款或放宽原门救结论。
- 反馈信号门：16正常闭合＋4块结构/预算核验，两个池配对均严格增加有效及时反馈且不降低有效终点数；最终质量严格门仍要求8对完整有效分数且逐任务中位差非负。缺失不补零；2池配对不是16独立调度复制。
- 600s相同不足以保证全成本相同；v5固定池槽，另报完整Slurm账单。客户端240s只是原生执行超时配置，可能另有中断/清理时间，不宣传严格240s物理cap。
- 只读观察：stage/live_status.py --version v6。闭合后用root/live_readout.py root root/readout-v1 --allocation-gpu-seconds 实测值，一次writer；再独立复验，禁止运行中改源/门。
- 服务alias qwen3.8-27b，实际qwen3_5/compressed-tensors4bit；不猜AWQ或更强生成器。编译cache跨块共用，活跃KV随服务重启清空。当前运行期间不做同节点大文件准备，避免I/O混杂。

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
- 当前己方远端9c52040372909aa2173705903def1a4102f6bb3f；senior dojo-reproduce0155c7dedded47b59e29e81089e814250e38bd70（仅元数据，未改分支）。本地有未push新实验提交。
- 未跟踪报告phase1/reports/给学长_MLE沙箱资源调度进展_20261009.md是用户上一轮要求、13:01版本，保留，不冒充最新或主动另写长报告。
- SSH linux5；PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。gpu27/gpu28 RTX3090已知兼容；不投projgpu39、不改驱动/权限或静默退CPU。旧Held12535不动。
- first-960/Target-300/Target-522、D_val、官方test继续关闭；16560数值导出仍待单独授权。不输出密钥/raw候选/回复/预测/标签/权重；不使用付费API、不更新agent底座。
- 研究盘总配额4TB、至2027-08-30；共享文件系统df余量不是用户配额。长期经验索引在旧checkout的phase1/memory/MEMORY.md，按需读取。
