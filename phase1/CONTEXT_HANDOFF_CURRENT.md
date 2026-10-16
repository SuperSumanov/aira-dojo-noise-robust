# 当前短交接：只记录现场与恢复操作

最后核验：2026-10-16香港12:25；下次先核现场，不照旧预计时间行动。
用户11:18批准六小时自主推进，窗口到香港17:18；限定新实验自行决策，不重复询问已批准事项。

## 活跃目录与来源

- checkout：C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001（detached HEAD有意）。
- 压缩前完整交接：Git 6c47086a603b4c7afcc25a3e80f9d5648c3bee63:phase1/CONTEXT_HANDOFF_CURRENT.md。
- 本轮fetch成功：myfork/phase1-value-critic=72167a42feccaec44f5793c3bc7d2f4e9132d581；
  dojo-reproduce=c394ca1756ab2e53d5cbb68802e2973c8ceebe8a。未push，不改学长分支。
- 用户未跟踪报告、_codex_tmp、pooling_host_compat_20261016.sh及旧checkout dirty保留。

## 18770：完整闭合，质量门未过

- root=/research/d7/spc/yzyang4/scheduling-pooling-20261016-v3；不得再prepare/preflight/submit。
- source=6c58f3b130534d8f4e1a0628f2ef5ce18b0c0356。
- planSHA=a7cc9780c927cdeac3fc1effb214643a387353122e1fa542d3a40116b248d477。
- readerSHA=3adac787a6a6e14efbda5441ef4ad4e64f31fd9cc2d278116cba11b1ea88e4ec。
- sacct：gpu1，COMPLETED/0:0，08:39:47–10:04:10，5063秒×6=30378GPU秒=8.438333333333333GPUh。
- 32启动/32完成/32finished；4池闭合；32实际首输入通过，dispatch资格、隔离、清理/模式均过。
- 矩阵/原门见CURRENT_DIRECTION；2旧开发任务×4配对seed×fixed/shared×2反序，≤10GPUh，不更改。
- 冻结reader完成root/readout-20261016-v1，--gpu-seconds 30378；29开发分重算通过，不再运行/覆盖。
- 安全读出已取到sandbox_scheduling/pooling_18770_closed；Node全32/原门/队列/身份/统计通过，11传输SHA一致。
- summarySHA=bef23ec17e2fd3e561a690e2aa7328c3df592cb315070fbc293d69c4ce84def5，质量门false。
- 去噪fixed/shared：重复0为0.014672638553735228/0.015065587448419392；
  重复1为0.0191865423765659/0.015308295476915064。Aerial一正一负，不合并救门。
- shared两池迁卡14/17；排队总时长较各fixed低，但不等于稳定终分收益。
- frozen reader在远端重算允许开发评分，Node只独立统计/结构，不说Node也独立重评分。
- 原队列预计10:50开跑已经过期；当前没有本批GPU占用。容器入口本轮已解决，不再因projgpu12旧失败阻塞。

## 新独立共置批18807：已分配gpu1，服务启动中

- root=/research/d7/spc/yzyang4/scheduling-colocation-20261016-v1；入口colocation_trial_20261016.py。
- 32条：两原开发任务×4配对seed×共享单许可/每卡双许可×两反序比较；顺序shared/colocated/colocated/shared。
- gpu1同6张3090，2服务+4执行，≤6000秒/10GPUh含失败与新共同共置安全门；用户六小时授权覆盖，不再询问。
- 17分钟/run、1180秒/pool、候选300秒、旧fast/公共预览/warm历史/固定CPU不变；完整32/两次去噪≥.001/Aerial不退/实际共置。
- source=c9251b7593edb4546cb371150f5067a922edd041；planSHA=36ce5852b26de2299755c19a8b9711a1f4161d68abd25a3de6cc7687cdde8560。
- 16项新CPU/Node自测、32真实输入/16配对、10生产信号场景均通过；哈希核验完成后提交18807。
- 12:25现场RUNNING/gpu1，服务尚未ready、0/32搜索启动；不是已有质量结果。≤100分钟allocation，预计14:04附近闭合。
- 状态助手=/research/d7/spc/yzyang4/colocation-source-20261016-RokSUP/colocation_status_20261016.py；未闭合不读中途质量。
- 新证据：pooling_18770_closed/mechanism-18770-v2.safe.json，SHA059a845e6e193c3e4955e1517d472c7b9a210fca42c64dc691925a3a85f5c769。
- 该记录只复用闭合开发评分，0新GPU/评分；采样利用率14%–24%、许可持有55%–63%不是共置收益或因果中介。
- closed_clock_screen_v2：75及时返回、73源码匹配、70有墙钟退出guard；29有效中28匹配/26有guard，静态不是因果。
- 独立小机制批准备中：两程序按时间序而非分数选择，solo/co/co/solo共8次，gpu27一卡≤45分钟/.75GPUh；尚未冻结或提交。

## 等待期间可继续

- 18770停止当前质量优势配方扩大；新实验须有不同机制/问题及额外证据，不追加seed救原结论。
- 既有时序分析已完成，不重跑填时间：pooling_v3_20261016_cpu/{closed-gain-timing.safe.json,no-execution-wait-quality.json}。
- 80旧终点/20任务池、8CPU测试/双语言核验通过；“有效更多≠pool-best更好”及条件时序机会，非E2E收益。
- 原fast去噪一个好解自身1186.27秒、此前排队256.03秒，删除全部等待约930.25秒；不当FIFO闭环预测。
- 旧18269/18412/18161/17740/17681/17675结论与近邻按ROUTE_DECISIONS检索，不重命名恢复旧机制。
- 新方法要能改变真实决定并胜合理强参照，不做只增加代码或audit数量的循环。

## 已闭合与操作边界

- 18673：0/32启动，78GPU秒，projgpu12缺指定容器入口；18510：15/32完成，15522GPU秒，旧SIGALRM接线漏项。
- 两者均冻结读出、独立核验，不重开或混入18770成功分母；18468及Held12535不动。
- gpu1原镜像CUDA资格18753已过；两服务+四执行也已跑通，不重复G0。
- projgpu36旧cuInit999、跨节点派发等留管理员，不转为当前主任务。
- SSH linux5；DNS偶发失败用既有137.189.88.148 + HostKeyAlias=linux5.cse.cuhk.edu.hk + StrictHostKeyChecking=yes。
- PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
- 状态助手=/research/d7/spc/yzyang4/pooling-v3-source-20261016-pCkUIK/pooling_status_20261015.py。
- 本地Python=C:/Users/yanze/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe。
- 不碰保护集/付费API/底座训练/学长分支。所有凭据仅远端；SCP先exit0再核hash。
- 已有automation已改为香港17:18一次窗口复查；提交后更新真实job，不新建重复跟进。
