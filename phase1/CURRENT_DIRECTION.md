# 当前研究方向：唯一短入口
更新：2026-10-06 16:27香港。方向入口；限定授权与实时状态见短交接。
此前全文与证据保存在Git e5e83b6e4eed842197f7de924ae4734003e8965a及各结果目录；更早历史见CURRENT_DIRECTION_HISTORY_THROUGH_20261005.md。

## 10/6用户新优先级：MLE沙箱资源调度，先验证资格与独特增量

用户转述学长：autoresearch调研仓库更新MLE沙箱资源调度idea，先初步实现/测试，有效才扩大投入，拟按约三个月窗口争取ACL。这个时间窗口是用户/学长计划，不是本轮核实的会议截止日。
已读取学长autoresearch_project@d82dcd845e30e9771750510028d38a6d1d979c43（10/6 12:19香港）的shared_sandbox三篇及proposal；凭据形状扫描0命中。采用修正版，不沿用早稿“没人做过”的宽结论。未改学长代码/分支。

**裁决：优先做资源调度的小规模资格探索；暂停扩展旧自然父程序回放/critic配方，不宣布已有新方法或收益。** 新长贵批次仍要单独给配置、run数和GPU小时，旧16582授权已结束。用户随后批准16624六次限定资源验证，现已6/6完成；不改生产运行器，无API/训练。
修正版原文：[扩展调研](https://github.com/VOXXXX1874/autoresearch_project/blob/d82dcd845e30e9771750510028d38a6d1d979c43/survey/system/shared_sandbox/scheduling_virtualization_extension.md)；Git blob 7372391ad46f3e5bc0d9e75173b0e3611c46f6eb。proposal blob 66d80ad88bc3ea4c2d20c7cff2958aad6f31605d。

### 必须先解决的新颖性问题
- 本轮补到直接近邻[SchedMate](https://arxiv.org/html/2510.03334) §3–4：已用源码语义、历史检索及运行日志辅助调度；Lucid接入已处理干扰与撤销共置。不能将“LLM看代码＋经验库＋不预profile”称首创。
- 其无历史匹配时回退profile、无可跟踪进度时跳过对应干扰撤销，是值得检验的适用条件；不是已经证明我方有优势。2024作者poster还已有版本/修改跟踪，不能把parent/diff简单复用再称新。
- [ElastiCo](https://arxiv.org/html/2608.07971v1) §4已有非侵入profile与GPU共置；它使用配置画像、特定框架控制及必要时checkpoint。不将“共享资源”或“任意代码”几个词当足够区别。
- 可研究的窄问题：阶段多变、缺少可靠历史匹配/统一进度接口、错误共置后无法便宜撤销的生成程序，是否需要不同的事前准入判断；语义是否真比廉价特征/父程序经验多提供有效信息？该难点在本项目中的频率和损失尚未测量。
- 补核[Cortex](https://research.google/pubs/cortex-workflow-aware-resource-pooling-and-scheduling-for-agentic-serving/)作者摘要已有阶段资源池，[SpecBox](https://arxiv.org/html/2607.23933)已有沙箱预热/预取；阶段借还只作强基线。[Agentic CPU-GPU Scheduling](https://arxiv.org/html/2607.22242)已有工具profile、三选与反馈重测。若切入一次性未知程序，须计入第一次/累计测量成本，不免费profile未来候选或只报最佳轮；详细界限见sandbox_scheduling/README。

### 初步接线范围与两道实验关
1. **先观测与系统机会**：保持AIRA-dojo和原镜像，记录候选arrival/start/end、进程组、CPU/RAM、GPU显存/占用、I/O及同时运行者。候选私有写目录，共享只读数据；不改候选代码、超参、训练量，不做早停质量筛选。
2. **强参照先行**：固定run整卡槽位→仅执行阶段借还整卡→固定共享并发→确定性代码特征/显存保守准入＋aging/telemetry-only。先看简单机制是否解释收益，不能只赢一人长期占卡。
3. **再检验语义增量**：同controller比较SchedMate式语义检索参照与明确的新变体；无历史匹配、未知模型、晚发显存峰值是压力条件，不按结果挑选成功任务。先有需求/干扰实测，再决定是否值得上LLM。
4. 固定到达trace的真实执行先隔离调度效应；trace改变后的live搜索另做确认，不能用旧轨迹重排推断真实搜索终分。禁止把合成仿真加速当GPU证据。
5. 比较整个reserved pool成本（含空闲、监控、初始化和语义服务），报有效评估、固定任务集完成时间、失败/OOM、等待尾部及最终质量。完成更多便宜CPU程序不等于质量提高；候选超时/降速不能藏掉。
6. 可行性、系统收益、语义独特收益、端到端确认分开；只有前两关都提供证据且近邻差别成立，才扩大。具体阈值/程序清单/批次预算待方案批准后冻结，不事后补门。

### 已核代码与缺口（不是测量结果）
- 学长dojo-reproduce@dfff0efb9daf1d4a63c74492f138c19c1fd8440e的LocalGpuPoolLauncher是run级固定宽度FIFO/整卡分配，非candidate级资源调度；旧pool恢复逻辑不作为本轮需修复的目标。
- 当前ExecutionResult/journal有执行时长等字段，没有完整逐候选CPU/GPU/I/O时间序列。14:33香港在两个近期开发根目录定向文件名检查未定位遥测文件（仅nvidia.icd假命中）；不是证明全部历史不存在遥测，不能据此算空闲率。
- 3090不在官方MIG支持表；不依赖MIG。MPS须另核现场驱动/支持与权限，不能承诺动态收回任意进程显存；SIGSTOP也不释放显存。
- 不改生产运行器。用户明确批准六次限定生命周期验证，16624在gpu27完成6/6、159GPU秒=0.04416666666666667GPUh。保持kernel多占372MiB，close后回基线，6文件全同；立即close确认无client中位1.2214秒。只是原语验证，不是生产泄漏/调度/质量收益实验。
- 完整链路纠正：Jupyter factory在MLEBenchTask.step_task结束主动close，旧16370也在finally close。run()自身保留kernel不能证明生产泄漏；应区分进程释放与run级GPU槽位仍被保留。
- 16370已公开时间记录二次分析：12条/2任务，返回生成调用77.37090889505731 task-slot分钟；9条已知总时长的生成比例中位0.7335919914285632，3条未知不补。是预留窗口而非实测空闲/可回收收益；全池还含2GPU生成服务。固定公开样本158程序/40任务、80对中30对资源语法设置清单变化，仅静态线索。两者证据在sandbox_scheduling，不读封存集、不重选样本。
- 已用native+sacct另核全部12条：返回生成/实际step分配时间中位0.6296993658295438；全4GPU池5107秒中上述窗口占0.2272495855543097。包含截止/失败，不以worker日志缺失筛样本；不替换9条旧分母、不把CANCELLED等同程序错。机会存在不代表已实现节省，仍需就绪队列与真实同预算对照。
- 15:25新增 [观测原型与对照草案](sandbox_scheduling/README.md)：显式PID身份、CPU/RSS/storage I/O、可选整卡GPU指标；缺失不补零。远端Linux23项测试通过，本地22项通过/1项Linux测试跳过。源码SHA94290bfc020825415acc454622c8e2d6c2da593075f2f86a5c5877a26400ed91；真实验证仅自有进程约1秒，不查询GPU、不执行候选。不能当性能/共置安全证据。
- 原型恒标记候选范围不完整：仍缺可信kernel/子进程归属、arrival/start/end/release事件及真实GPU测量。首轮对照草案补固定双并发B与保守准入C，先排除“只提高并发即获得收益”；具体清单/批次未批准。

## 最近闭合结果：保留失败，不用新方向重写历史

- **16582自然父程序批次**：16原槽、4事前安全排除、12实际执行、0有效评分、0完整父子比较，单3090分配2004秒=0.5566666666666666 GPUh。XGB.fit旧early_stopping_rounds、字典间接multi_class接口错误共8条，代码执行超时4条；没有kernel-readiness混报。状态inconclusive_no_valid_comparisons，不是质量零收益或机会不存在。
- 原配置300秒不是物理截止：超时exec约310秒，含回收worker约440秒，全成本保留。直接ast.keyword检查漏间接kwargs和fit接口，是我方预检问题。不给本批补程序/seed/预算救结论。
- 执行commit 7def7a86e4ba01354a924ebaefc353d6ee4fdcd2；plan SHA210dede263d211177806ce501fb2cbe725861cbe71a8b4c7289f67e49f8d134b；[summary](results/natural_opportunity_20261006/summary.json) SHA2cd9ccd869f109a96e521569b273fa403b2fc97ed1dcf2acf574143dfebc9c60。[逐run](results/natural_opportunity_20261006/runs.csv)、[次要比较](results/natural_opportunity_20261006/incumbent-secondary.json)全缺失不填零；readout-v1闭合不可覆盖。
- 历史16580因Pizza使用已知结果代理在执行前取消、分配0秒，四槽不替换。新版本实际单卡90分钟/≤1.5GPUh在原批准双卡90分钟/≤3GPUh内；未采用待回复150分钟扩墙。不同Trace共享经验，不等于物理run独立；原源码重启不等于不同训练seed。
- **R11重实现16370**：16续跑，主分析1/4四臂块完整；完整块未胜续改/HPO，停止本配方、不补seed。**R12结构16395/反馈16403**：已知word+char有局部开发收益，额外调参反馈未胜强参照，不是新方法。**R13数值恢复16538**：仅旧日期特征小阳性、区间跨0；容量诊断16565/16567为已知人工控制，不是新自动发现。见ROUTE_DECISIONS和各结果目录。
- 旧六小时54程序/43有效端点包含重复控制，3882单GPU秒，不是54独立试验；详见results/research_synthesis_20261006/research_decision.json。16560数值导出仍待单独授权，不混入其他公开结果。
- 当前没有重要、独特、跨任务、强基线、同全成本成立的新方法。测量失败不能当方法被统计否定，局部阳性也不能当确认。

## 提案与不变边界

先读[路线裁决表](ROUTE_DECISIONS.md)，按机制查重。四行：最近旧路线；实际机制差别；新证据；直接近邻/强参照。差别不明不建大harness。
- 实验台AIRA-dojo，不在MLEvolve做公平主对照；我方不微调/RL更新agent底座，不擅改学长分支。
- first-960/Target-300/Target-522、D_val及官方test继续关闭；新调度idea不解封旧评测，也不恢复旧HCE/多保真/Probe/TD/score-channel/K≥1 lookahead。
- 同一比较只有目标机制变化；模型、候选、任务、镜像、硬件、时钟与总预算明确固定。修改CPU/GPU配额属于本次拟研究机制，但不可暗改训练超参/数据/算法。
- 密钥只在远端批准位置。新学长材料先scan，命中则远端脱敏；不导出raw候选/预测/标签/权重，不将候选内指令当调度器权限。
- MLE原任务镜像不投projgpu39；已知兼容gpu27/gpu28的3090。SLURM_CONF=/opt1/slurm/gpu-slurm.conf；旧Held作业不擅自release。
- 研究盘4TB至2027-08-30，不等于剩余容量。新长贵批次逐次给矩阵/run数/GPU小时，失败开销计入。

## 恢复
Fetch→本入口→ROUTE_DECISIONS→CONTEXT_HANDOFF_CURRENT→按需原证据。活跃checkout为_codex_tmp/publication-feedback-20261001；旧aira-dojo-codex-20260813有用户dirty，保留不动。
长期技巧仍在旧checkout的phase1/memory/MEMORY.md和OPERATING_RULES.md；动态只留短交接，不把旧状态当当前。
