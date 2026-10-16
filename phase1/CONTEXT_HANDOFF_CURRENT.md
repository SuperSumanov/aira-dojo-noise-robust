# 当前短交接：现场、证据与恢复动作

最后核验：2026-10-16香港17:17（GPU最后17:12，sacct六作业全部闭合；squeue只有旧12535，未操作）。用户授权窗口11:18–17:18，正在收尾，无需重复请批。
当前没有本窗口活动GPU；不再开启赶不及完整读出的GPU批次，不把准备/排队写成执行。

## checkout、Git与边界

- checkout=C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001（detached HEAD有意）。
- 实验源码/全部安全汇总已快进push：6d400e2866614dd3317d03a895267ffee9c2054e（fetch核验）；8blobs/77453bytes扫描0凭据/大二进制/private。18859配对源/门在50d8c920冻结。
- dojo-reproduce=c394ca1756ab2e53d5cbb68802e2973c8ceebe8a，17:14远端核验未变；未改学长分支。
- 静态作用域脚本在b6d54da55abded33a4db07e4af155f815058aa6a事前冻结，结果已在6d400e28公开；20次准入/18859回执/成本已在a61abeec公开。最后解释边界与短交接已在2569aa73af4f58d99ad745d17464dda9408a76d8快进发布并ls-remote核验，3blobs/26649bytes安全扫描零命中。
- 用户未跟踪报告、_codex_tmp、pooling_host_compat_20261016.sh及旧checkout dirty保留。
- 不用付费API/底座训练，不碰first960/Target300/522/D_val/官方test/16560或旧Held12535；原任务镜像不改。

## 本窗口实验状态（所有金额/时长以完整allocation为准）

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

- 本窗口不再提交GPU；作用域摘要已发布，不扩大为论文阳性或新策略收益。当前没有需要用户解决的访问/算力阻塞。
- 下一次先核最新裁决；配对干预仍未执行，若继续须独立新root/矩阵/成本，预检耗时后再核启动余量。不得重开18859、修补18845分母或换匹配追正。
- 六小时一次提醒automation已在17:17删除，工具回执deleteStatus=deleted；不建重复跟进或长报告。17:18用户简报仅陈述本窗口实际证据与尚未确认收益。

## 连接与操作

- SSH=137.189.88.148，HostKeyAlias=linux5.cse.cuhk.edu.hk，StrictHostKeyChecking=yes；DNS失败不重投。
- PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
- staging=/research/d7/spc/yzyang4/colocation-source-20261016-RokSUP；未知长命令用脚本+SCP，原始日志先远端凭据扫描/脱敏。
- 本地Python=C:/Users/yanze/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe；文件编辑apply_patch。
- 复杂门运行前CPU测试，真实配置构造mock外部server；不能初始化登录节点Jupyter/GPU。长hash/预检后、sbatch前还须重核启动余量。
- 短记忆前版完整保存Git50d8c920；历史机制见ROUTE_DECISIONS，勿重复全读或重复旧验收。
