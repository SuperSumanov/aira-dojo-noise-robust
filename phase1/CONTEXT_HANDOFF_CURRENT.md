# 当前短交接：只记录现场与恢复操作

最后核验：2026-10-16香港15:56；用户11:18批准六小时自主推进，窗口到17:18。
限定新实验自行决策，不重复询问已批准事项；不能用无界重试、择seed或改门追正。

## 目录、Git与授权

- checkout：C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001（detached HEAD有意）。
- 旧完整三文档归档Git6c47086a603b4c7afcc25a3e80f9d5648c3bee63；方向只读CURRENT_DIRECTION，历史按需检索ROUTE_DECISIONS。
- 15:22快进push/15:55fetch核对phase1-value-critic=7600573a1bf39784e9fe5adb8109209270de7647；1提交/5blobs扫描0凭据/大二进制/private文件。当前有18845闭合补充未提交。
- dojo-reproduce=c394ca1756ab2e53d5cbb68802e2973c8ceebe8a，15:55fetch未变；未改学长分支。
- 用户未跟踪报告、_codex_tmp、pooling_host_compat_20261016.sh及旧checkout dirty保留。
- 本窗口不训练底座、不用付费API、不碰保护集/官方test/D_val/旧Held12535；GPU镜像不升级、不退CPU。

## 18807：32条已闭合，质量门false，禁止重开

- root=/research/d7/spc/yzyang4/scheduling-colocation-20261016-v1。
- source=c9251b7593edb4546cb371150f5067a922edd041；planSHA=36ce5852b26de2299755c19a8b9711a1f4161d68abd25a3de6cc7687cdde8560。
- 两DEV任务×4配对seed×共享单许可/每卡双许可×2反序比较，shared/co/co/shared；同旧fast/起点/历史/CPU/1020秒、2服务+4执行卡。
- gpu1 COMPLETED/0:0，12:23:23–13:47:52，5069秒×6=30414GPU秒=8.448333333333334GPUh，含启动/失败/清理。
- 32/32完整，32真实首输入、隔离/清理/共置/派发均过；两处理池真实双许可准入8/12。
- 唯一冻结读出root/readout-20261016-v1已完成；readerSHA5744414b9cea8c443e9db4cef421ddb57402a1138f197871ec344abdff174cea；不得再读出覆盖。
- 38 pristine开发评分重算；Node独立统计/队列/身份/门及12传输SHA通过。Node不是独立重评分。
- 本地sandbox_scheduling/colocation_18807_closed；summarySHAc8c2f71009a39e9932ec59e388f9b052ce190730179119aed5d73e4fa38576a4。
- 去噪两次co−shared有向best差+0.002312806537356958/−0.004900952505611393；Aerial一正一负；原质量门false。
- 两共置池有效返回11/11，对照7/9；执行等待近零仍无稳定终分收益，不是“多返回就更好”。
- 事前条件确认协议d0a49df0要求18807原门true；故不启动新seed217501确认批，不把余款转成补跑。

## 18812：固定源码工作量机制已闭合，不是E2E收益

- root=/research/d7/spc/yzyang4/clock-contention-20261016-v2；source=f0c616b375f71908f9286951cca80f6446659c6c。
- planSHA6e19c7f715597f30d784982943618b73aeba69db4b9fc1bc446ea0a307cc0e17；gpu27 COMPLETED/0:0，1822GPU秒。
- 8/8完整有效，8 pristine开发重评分、独立Node/4传输SHA通过；readout-20261016-v1封存，不再重跑。
- summarySHAb1b7053e5372b33770fa360a94aad393b911dfa9d96803ab9a5e0a0da32b5d40；本地clock_contention_18812_closed。
- 两程序solo/co的step1491/994、1584/1044；有向均分差−0.00032338587685687425/−0.00020111421947950625，超过各臂restart span。
- 两共置host训练包络重叠195.56/192.98秒，不是kernel重叠；过6f6bab3e事前扩展门，不是显著性检验。
- 事后：去噪co/solo平均执行时间比0.7988482912036062，但工作量/质量均降；更快结束不等于等质加速。
- 两程序相对其原始父回执的优劣符号不变，未证明接受/拒绝翻转；原父未在负载下重跑。
- v1准备误触8登录Jupyter已关、0候选/0GPU，保留不提交；v2修外部构造mock，不再重复该调试。

## 18819：已闭合，固定16次排序机制

- COMPLETED/0:0/gpu27，13:24:59–14:25:17，3618GPU秒；16/16完整有效，14:29一次冻结读出完成。
- root=/research/d7/spc/yzyang4/clock-rank-20261016-v1；source=4c2b6fa514bec295a045c19dcf93faada77ed5c5。
- planSHA4c22748699952da0b79bf862e1db5e785b7d2a9fb951bb26ee9c21be47ca3306；16执行，一3090≤5400秒/1.5GPUh。
- 4源码按18770时间序：Aerial ep4/c0、ep6/c1，Denoise ep3/c0、ep5/c0；同任务两程序共置，原源码/输入/seed/300秒不变。
- solo/co/co/solo，反序执行；8CPU测试/16原配置门通过；不按分差或翻转选择程序，不补跑或替换样本。
- 唯一readout-20261016-v1已封存；16 pristine开发重评分、独立Node/3传输SHA通过，不再重跑读出。
- summarySHA0f5ba4f180d2b82d0a0e343e140791e35447d138d615f417e99a83bf366ed0ba；本地clock_rank_18819_closed。
- 报告两次各自翻转和跨重复区间严格翻转；4已知DEV程序/2池重复/2程序复用18812，不是独立E2E或泛化。
- clock_parent_reference_20261016.safe.json只取旧18770真实父回执，3/4唯一识别；缺失不补造，非新成功门。
- Denoise严格跨重复区间翻转；Aerial仅配对翻转，区间重叠。过333c5662事前新来源门，不是方法收益。
- 新来源v1/18844 FAILED封存：14:38:30–14:38:41/gpu27，11GPU秒，首容器导入旧pooling模块失败，0候选/评分、清理true；不是方法反证。
- 15:06封存18819事后机制补强：去噪实际完成折数两次均3→2、5→1，12轮×每折batches等于全部梯度steps；源码平均完成模型。fold-mechanism回执SHA80ed9a56f1127270432a370c3c99de7894f38547c95cf97dadb76cde48b04028；不是折数单因子干预/E2E。
- 18845 COMPLETED/0:0/gpu27，14:48:31–15:43:04，3273GPU秒；现在本轮无活动GPU。root=clock-rank-confirmation-20261016-v2，source=30af07a15f33d3f444028108566ae18554e5b819，planSHAd9834749a7d1add6ba10168372ea2c947adaa5f00273fb8719491591a2d0d146。
- 16wrapper闭合、11有效/11pristine重评分，独立Node及3传输SHA通过；确认门false，不能计算完整排序。唯一readout-20261016-v1已封存，readerSHA89040d72a776486aa02ac6ddd176f025998e9ac2ccd9e136527588af767fd70e；禁止再次读出/修正/补样本。
- 4去噪共置执行超时均报告CV已完成，2次另有inference开始声明；不能由缺终端训练回执推零GPU工作。index13内核未就绪属设施错误，被包装成普通超时，未触发声明的设施停止门，之后执行index12；补充审计保留此偏离，不能用后续个例确认效果。
- failure-audit回执SHAd674c63e34f01d7a26b6f70a088a392e3a38fbe13b405fcbf600d49bee0dbea4；7解析测试/独立Node分类/传输SHA通过；原summary不覆盖。源closed_rank_failure_audit_20261016.py。
- 本窗口5作业全allocation合计39138GPU秒=10.871666666666666GPUh，已打印独立求和；见window_20261016_allocation_receipt.json，18770在窗口前结束不混入。

## 已闭合与操作经验

- 18770共享FIFO vs固定：32/32、29评分/11SHA通过，30378GPU秒；质量门false，见pooling_18770_closed，不再重投。
- 18468/18510/18673及旧Held12535不动；18673缺入口已由gpu1真实执行解决，不再转旧排障。
- 近邻clock_scheduling_neighbors_20261016.json：SchedMate/HyperSched/TensorShare/DSec/AgBench/经典anytime，新增Winning by Peeking/Mosaic/RTCSA2020；不能宣称质量调度或争用改变排序首创。
- 不用静态guard或host包络推断实际完成epoch/fold/kernel；低GPU利用率不是无干扰余量，分数下降不是自动“标签错误”。
- SSH固定137.189.88.148配HostKeyAlias=linux5.cse.cuhk.edu.hk、StrictHostKeyChecking=yes；DNS偶发失败不重投作业。
- PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
- staging=/research/d7/spc/yzyang4/colocation-source-20261016-RokSUP；优先原gpu1/3/27/28/29，非projgpu39。
- 本地Python=C:/Users/yanze/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe；SCP先exit0再核hash。
- 已有automation是香港17:18一次复查，不新建重复跟进；本会话继续推进，结束窗口后删除该一次提醒。
