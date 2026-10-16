# 当前短交接：现场、证据与恢复动作

最后核验：2026-10-17香港05:38队列回执。授权窗口02:49–08:49，用户批准同范围自主批次，持续在会话推进，无需重复请批。
19004于05:37:27在gpu3六卡RUNNING，独立quota32、≤100min10GPUh，预计07:05完成；不读中途质量。18997已封存32完整/35外部DEV重评分、独立Node及12传输SHA通过，质量门false，30540GPU秒；旧18987733GPU秒另计。条件diverse仍禁止提交。本窗口不再开第三个GPU方案。

## checkout、Git与边界

- checkout=C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001（detached HEAD有意）。
- 上窗口最终公开2cf2883917d5fc67b97b62894006a1bec7f8bb66；本轮配对源a349aa7a2c7a70d298a6703c3faced4bc5d0a685、条件六卡源f24715fb1f74ceca7a700266b2b1755509814468均已安全扫描。
- dojo-reproduce新e4d478350e704e8c5927eba566b2847aaa6dcbab；两新文档先远端扫描/脱敏后读。95journals/5任务结论是学长报告，非我方复现；selected改善不等于best-found提高，存在跨天硬件/负载差异。记录senior_update_20261017.safe.json；未改学长分支。
- 18987root=/research/d7/spc/yzyang4/clock-pairing-20261017-v2，planSHA a2f2ea693c0d2a194ac194a3023e81645eeb55b94263733dd12e943515d6ed22；1卡52分钟≤3120GPU秒。v1仅CPU二次导入失败0GPU/0候选，不覆盖原包；修复后12CPU测试及实际shim通过。
- 条件六卡root最新scheduling-diverse-20261017-v3，source660d58c65b52a0c71e3cc27634e784c4da4ed287；v1测试替身注入失败，v2修测试；v3提交前补原有worker异常停止契约。48输入/15信号场景CPU通过，planSHA5cb896640d9dd0a3aa7af5f43f02e78fb2157c1bcd26a2d6864803582ee2739c；0GPU，父门false，绝不submit。
- 18987唯一readout-20261017-v1已闭合，本地clock_pairing_18987_closed保留全16分母及Node独立核算/3传输SHA。summarySHA05afb45ee116a41fff342a997b9b52d9d29b4fc9f8b420fb3f5ac1325fbdd57d；program2原300秒超时，exec301.4508007057011；两折153.6s/133.2s、CV287.6s、inference6s，不能只归因序列化。无配对质量结论。
- 用户未跟踪报告、_codex_tmp、pooling_host_compat_20261016.sh及旧checkout dirty保留。
- 不用付费API/底座训练，不碰first960/Target300/522/D_val/官方test/16560或旧Held12535；原任务镜像不改。

## 上窗口已封存状态（10/16；不混入新窗口成本）

| job | root（前缀/research/d7/spc/yzyang4/） | 状态/有效数 | GPU秒 |
|---|---|---|---|
|18807|scheduling-colocation-20261016-v1|32完整/38重评分，质量门false|30414|
|18812|clock-contention-20261016-v2|8/8有效，局部工作量/质量机制|1822|
|18819|clock-rank-20261016-v1|16/16有效，去噪局部严格排序翻转|3618|
|18844|clock-rank-confirmation-20261016-v1|导入失败，0候选，已封存|11|
|18845|clock-rank-confirmation-20261016-v2|16wrapper闭合，11有效/重评分，确认门false|3273|
|18859|clock-pairing-20261016-v1|FAILED2:0，16:26:34–16:26:35，时间门拒绝，0worker|1|

- 合计39139GPU秒=10.871944444444445GPUh；window_20261016_allocation_receipt.json已独立求和。18770窗口前结束，30378GPU秒另记。
- 原分配32条18770和18807均没过终分门，不补seed；18819是机制，不是同预算搜索收益。
- 18807/18812/18819/18845各唯一readout-20261016-v1已封存；不得再次readout覆盖、submit或混合补分母。
- 对应本地sandbox_scheduling/{colocation_18807_closed,clock_contention_18812_closed,clock_rank_18819_closed,clock_rank_confirmation_18845_closed}保留JSON/CSV/独立统计及传输SHA。
- source/完整planSHA/原门从上述independent-verification及原plan取，不从旧口头数字重建。

## 关键补充与禁止误读

- 18819完成折数两次均3→2、5→1；fold-mechanism回执SHA80ed9a56f1127270432a370c3c99de7894f38547c95cf97dadb76cde48b04028。日志×12轮×batches与全部梯度steps相符；非折数单因子干预。
- 18845四去噪共置在CV完成声明后超时；1独占index13内核未就绪被包装成普通超时，遗漏设施停止规则后又跑index12，已记录协议偏离。16complete不是16有效，缺末尾训练回执不是0GPU工作。
- 18845 failure-audit SHAd674c63e34f01d7a26b6f70a088a392e3a38fbe13b405fcbf600d49bee0dbea4；7CPU解析测试/独立Node分类/传输SHA通过。不得用index12或完整个例补确认。
- 18859 source50d8c920，planSHA2312d9665f92c8ee8cbc2b5c9fa7849bd156ea6069ac74b1b923349aafd7bf3a。源码/16真实配置/8CPU测试/准备shim通过，但镜像hash后实际分配只剩3084.282077074051秒，低于3300秒门。0候选/0分；不重投，问题仍未知。
- 18859的新readiness异常传播仅CPU真实类测试通过，没有实际GPU路径验收；不能声称生产修复已证实。
- 20次共置均candidate+candidate；仅3次双侧终端CUDAtrace，均不够前后32/128步窗口。19个缺trace侧出现=8超时/9错误/2事件不足；有重复lease，不当19独立作业。不据此说SchedMate无效。
- 静态作用域进一步分层：Aerial35/35有epoch命名循环退出；去噪40/43有fold命名循环退出（有效12/13）。8CPU测试/独立Node/传输SHA通过，granularity回执c0e4210829d824dcb3347efb40da044e7b81e6ff9d5923669035a7b320d3a785。源码/AST不同不是独立家族，只有两个18819程序有运行级折数变化证据。
- 低利用率不等于可无损共置；host训练重叠不是kernel并行；MPS历史状态未知。不要归因全部到CUDA上下文切换。
- Aerial的18819两个程序steps减少但分数更高，因此保工作量不是保质量；实际共置成绩并非错误标签。不以排序翻转恢复critic或多保真。

## 收尾与下一次恢复

- 18987不可再readout/submit/改时限；条件六卡父门false，不提交。诊断仅解释失败，不拿第一组或完整个例救配对收益。
- 独立selective18997源码8384f405，root=scheduling-selective-20261017-v1，planSHA1783555a7c680021b2a1bae874798f1042c0bfe79d0b11af70fa7f2a75d26e32。唯一readout-20261017-v1已闭合；本地selective_18997_closed含全32/独立统计/12传输SHA，summarySHA0bd972126ab1bb9427ea93e446be3d3e245955c8bd5aa7e08778b7afa05c3514。去噪有向best差−.028238214366029694/−.0018636732167496284，Aerial+.00012828530652175818/+.0001363031381792501；策略实际变化/输入/结构均过门。停止该配方，不重readout/submit或补seed。
- 新只读证据：18807四池固定2/task生成许可有123.56–287.05s可借用状态；独立积分回执quota-borrowing-independent.json。408vLLM采样Waiting全0、Running≤4、KV≤13.3%；不是空闲算力或可节省时长。两安全传输SHA已核，原日志未导出。
- 余时核算已公开098a4b44：≥300秒余时每池仍有95.71323990821838/117.8350818157196/123.41448783874512/167.92554330825806秒机会，主要analysis/debug等待。quota-slack原件SHA d9c4bfb490baf1a6924262ee72939c07d163e6eb79ba2b0173d6fef710de5181；4CPU测试、独立Node积分/传输SHA通过，不是额外完成数或收益。
- 旧18807发布延迟诊断SHA c8ce2d7ede1241d9ff09c366af76f55886f949dba292e4e78b26e8e16c35e827已传输核验：38有效/37发布/1截止前未发布，仅1次真实Improve可能切换至更好尚未发布父程序。原始join尚未独立复验，不能升级方法信号；不为此开第三GPU方案。文件feedback-publication-20261017-v1.safe.json。
- 独立quota19004已在selective读出前冻结，source044cd889471417f357edfa6dcf8fdd2c7e262477（旧combined/new-window cap只界定本批，不是整个窗口总额）。root=scheduling-generation-quota-20261017-v1；CPU32输入/实际selector双模式门通过，planSHAf08b3052fcecf467f500b5b9aa6638087c602321ca3a81bf22ef8b65a55b41f9。submit/session94841成功结束，sacct确认RUNNING6GPU，不得重复submit。partitioned2+2 vs pooled4、同全局analyze优先/FIFO、执行均shared cap1；原终分门+两pooled池实际借用。闭合后唯一generation_quota_readout、独立verify_generation_quota_20261017.cjs、16传输SHA及实际sacct成本；不救selective、不做第三GPU批。
- 公开0bb807ab新增只读quota角色时序分析，自测通过；只分解代码/分析/调试的排队、请求占用和取消，不是新成功门。安全文件待完整closure后使用；不把request秒求和当墙钟节省。
- 18997首程序诊断SHA b87aa52b18e0e06b02e888bd988bca2c6b9ba4c7e454f3da9829119fad0fab3e：16对同首prompt/配置seed，raw/AST仅3对相同、去噪0/8。origin回执SHA87e64ec58d39e08628d0c2adf59e50b35428bc327877faec222c4d02fbe79856核32首程序均匹配原生journal、首日志成功Improve/adapter_attempts=1；排除执行包装哈希差异。独立计数/传输SHA通过，未独立重提取代码AST/journal，不能指认服务原因或把配对seed当同提案。原质量门不改。
- 32条前必须完成真实输入矩阵、实际双模式CPU信号场景、common readiness及worker异常停止门；22本地CPU测试通过。若不胜不补seed；不自称新算法/胜SchedMate。六卡diverse包不得误submit。
- 旧一次提醒已删除；本轮继续本会话到08:49，不建重复跟进/长报告。当前无外部权限或节点阻塞，不碰旧12535。

## 连接与操作

- SSH=137.189.88.148，HostKeyAlias=linux5.cse.cuhk.edu.hk，StrictHostKeyChecking=yes；DNS失败不重投。
- PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
- staging=/research/d7/spc/yzyang4/pairing-source-20261017-GWteBV；未知长命令用脚本+SCP，SCP返回session须等完成再运行；原始日志先远端凭据扫描/脱敏。
- 本地Python=C:/Users/yanze/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe；文件编辑apply_patch。
- 复杂门运行前CPU测试，真实配置构造mock外部server；不能初始化登录节点Jupyter/GPU。长hash/预检后、sbatch前还须重核启动余量。
- 短记忆前版完整保存Git50d8c920；历史机制见ROUTE_DECISIONS，勿重复全读或重复旧验收。
