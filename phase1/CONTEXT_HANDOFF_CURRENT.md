# 短交接：截止预算e2e 13152已在gpu28开跑

2026-09-12最后更新06:28 UTC。用户05:36继续推进；旧三小时轮次已闭合，新轮为600秒预算e2e。
恢复先fetch→CURRENT_DIRECTION顶部→本文件→现场；主线同预算MLE-bench最终收益，不以旧状态替代当前事实。

## 当前接续：正在进行，不可重复提交

- 新包 /research/d7/spc/yzyang4/forets-wallclock-20260912-0t4odqpn，stage forets-wallclock-stage-20260912-2C42Vyve。
  code ee544097a59b70b51493184a6d19b2ea7453ba8e；source6780e383d20d6051ba53cace793f0db910027315；
  prepared9194eb00bcff646bad70e8422f8af50aae59b549a3d707d96b93f8e77aed1e00；source archive1207df148f3d8ba1a838c76df168ee070376d10add5e5b31db011d9ad07d93d6。
- 新矩阵两任务×22/23×random/Plus上下文critic，全8，600秒worker截止，64step，单3090/6CPU/原镜像。
  每完整迭代后冻结原journal选出的incumbent与原submission，不用外部分数重选、不重跑最终代码；135秒API准入余量两臂相同。
- 17本地测试通过；真实Task/archive/MCTS/paid reserve导入接线与实际POSIX截止核验已通过，integration-check.json。
  06:07:51单次提交 **13152**；06:08现场RUNNING gpu28，第一worker **13152.0**，其余7pending。
  06:18确认13152.0终态FAILED/468秒，已只检查固定SearchBudgetExpired标记，为预设135秒API准入余量退出，不是新基础设施异常。
  第二worker13152.1运行，未读任何新run成绩；全8闭合再读。时间资格文件当时0，缺失不补0。
  **06:27最新现场**：前两worker均结束（第二501.210939秒），两者均命中固定SearchBudgetExpired准入余量退出；
  第二未命中缺失submission绑定/代码漂移错误。第三worker **13152.2 Space s22 critic** 正在运行，其余5待执行。
  这些是预算终止元数据，不是“模型效果失败”或额外GPU验收；没有读取新成绩。
  source/controller/plan已冻结，不在运行中改源码/选择器；预计80–110分钟，全8闭合后独立读出。
  POSIX只杀进程组，Slurm终态/额外清理资源必须另报；不宣称物理用量精确相等。
- 预算已从thgk111r排他转交 **0t4odqpn/paid.sqlite**，旧ledger stopped1，完整继承402calls/两旧未知。
  新AUTH **2129c34aa8758e9b5e2e07e98f6b2e9864fd9e896853c07c6b6333e98d716039**；不得重复activate。
  Plus catalog+2真实公开route fixture通过；整账10USD不重置、新责任上限3.5USD，实际新费用看当前ledger。
  最初只读catalog检查漏source proxy、Network unreachable且0API收费；已修为整个route进程显式source远端env_setup。
- readout_forets_wallclock_20260912.py在全allocation终态后读全部8槽，只用截止合格incumbent与原submission独立重评分。
  必须核同GPU/额外清理资源；不要使用旧完整六步e2e读出器（本轮预算终止是预期状态）。不重做G0/镜像验收。
  单次CPU收尾阶段已启动：**PID3943532**，06:24核实存活，等待13152终态后仅调用固定读出一次。
  closeout-intent.json已固定stage中closeout/readout/numerical helper三个SHA；**不可改远端这三文件、不可重复启动/读出**。
  该阶段不发GPU/API/新实验，不是新automation；等待上限14400秒、读出另限180秒。结束查closeout-finished.json和wallclock-summary.json。
  如果读出失败，保留原回执后查具体原因；不得把失败当0分或自动重跑。20项wallclock/closeout本地测试通过，另3机制测试通过。
  06:24现场仍13152 RUNNING第二条，417累计API记录/两旧未知，责任2.757976529USD、结算1.357976529USD；不是结果闭合。
- 原分享报告/24程序包结论仍有效：仅有效性局部线索，无e2e质量收益。我方本轮已push并ls-remote核对
  **9d8d7c57c28d3a6aa82505f098c9d271dbcbc8b4**；06:16学长dojo-reproduce仍9c46cca1dccd7633b556374d33c6c76390d1d061，未改他的分支。
  后续收尾与机制诊断已push到 **440d0cc4c8e309b3cc3a99d2c8c9223d8d8f65fe**，06:26 ls-remote一致；原无关untracked完整保留。
- 等待期间新增零GPU/API事后上限分析：两混合池均已达到top2有效数上限，两个Leaf质量仍距同有效数边界0.059675/0.013250。
  其余两池全有效/全无效是平凡上限，不是跨池独立复现；成本G/R未测，不用mtime猜latency。
  结果results/forets_selection_ceiling_20260912.json；说明FORETS_SELECTION_MECHANISM_20260912.md；3测试含穷举通过，不影响13152。

## 最新20/21已完成，禁止重跑/重写读出

- root **/research/d7/spc/yzyang4/forets-generation-capacity-20260912-thgk111r**；
  stage **forets-generation-stage-20260912-d2GRvV4f**；controller **fa55d4a692eccb0154d6d2e551daac697d0a1a6b**；
  preparedSHA **e98bfb3b91a6176a8162b619962a4a22211916270e2b64e45f07d14ff8d599c8**。
  05:22:01完整12API结束，session19918已完成；05:23:01单次提交job13149，现COMPLETED181秒。
  05:26:35独立读出全8、4数值重评分通过；summarySHA **76c3387a3ff942aaffa60c996c293d0b73dea761a2f532fb32b1c193a07afcc3**。
  冻结方案FORETS_MIXED_POOL_SECOND_REPLICATION_20260912.md：8新生成+4执行前双序盲排名，两任务同原规则；
  原镜像、source900fa3bdf6971381c37a9792723dba42c63e5ac6、gpu28单3090/6CPU/300秒配置不变。
- 当前唯一API后继账在thgk111r；05:32查hp7jtagu stopped1、thgk111r stopped0，无运行API进程。
  AUTH **4d66bef41f5ad23d64a8e6f26350a25486eb65bbde5c416a531879d6b48925ca**；402calls，
  settled1.327324583USD/accounted2.727324583USD、两个旧.70未知。原100人民币/10USD不重置，不克隆账本。
- 已用d2GRvV4f/readout_forets_generation_capacity_20260912.py完成排他读出，不再运行。
  Leaf全池4/4、top2有效2/2，条件质量 .4979475→.479845；Space全池0/4、top2为0/2。
  同质池不能提供新有效性区分证据；正逆top2集合都不同，不能称稳定顺序。未提交后继paid e2e或新训练/G0。
- 两批四盲池合计保留6/8=.75，对全池9/16=.5625，次要Flash4/8=.5；Leaf质量一负一正，不称e2e正收益。
  三批24程序Flash8/12、Plus5/12，13原submission独立核对；0代码SHA重复。停止追加同配方追显著。
- 新结果已下载results/forets_generation_capacity_s20_s21_20260912；完整汇总results/forets_mixed_pool_combined_20260912.json。
  分享ZIP：releases/forets-development-20260912/forets-development-20260912.zip（38,466字节/24代码+3JSON），
  SHA **dc99104b0faf0d175b9dac7be5fd54aaf02037f2b7268e974571a15afc8322b4**，远端forets-development-export-20260912-scdlkfn4。
  已credential-scan/逐项回读；标签都已读，只能开发，不得当新冻结测试。结果/报告/ZIP均已发布到
  **88f7f6b3412d9269c74d9449fd2ddda002a177ee**，05:34 ls-remote核对同SHA；只改我方phase1-value-critic，学长分支未改。
  最初发布门唯一命中是新scanner自身正则声明（非凭据）；定位后按实际API/PEM形状扫全部11个暂存文件为0，ZIP27项另行解压扫描为0。

## 已闭合实际证据，不重复排他读出/执行

- 18/19 job13148 COMPLETED147秒，root **forets-generation-capacity-20260912-hp7jtagu**；
  controller4fc38fe60e44db8e2cdcc811e185924aa4496f29，preparedSHA a86b55bbfebd80f71e06a6b277db82137b989e94daa14d0bef17e39642226328。
  05:17:49完整8程序、5有效submission独立数值复验通过，summarySHA **84ff9345b0123f90555b278371308be3680ebf6d2d5a362eaa8377efa2ceeba7**。
  Flash2/4、Plus3/4有效；盲top2 Leaf2/2 vs池3/4、Space2/2 vs池2/4；正逆top2集合一致。
  alwaysFlash两任务1/2，次要参照为执行后/揭盲前追加，不能称主要预注册。Leaf条件质量变差，不能称最终质量收益。
  API生成.020848919USD、排名.0144118USD。results/forets_generation_capacity_s18_s19_20260912已安全push至504601d6。
- 16/17 job13143 COMPLETED125秒，root **forets-generation-capacity-20260912-asl_0ytg**；
  controllerf3b2c68551b9eea728b67781e630cb5bb0426810，preparedSHA ab7bfcd9d1c93b14fbb6f65c04995d9ec3faca42299aba1120f2f9dd4e2fad06。
  Flash4/4、Plus0/4，4数值复验；summarySHA1ab23e7ff96910cdd3a73a671e9139c20edbc2856abf237060d6f4fa0c1d23e2。
  Flash Leaf .62195/.54568、Space .81264/.81379；18/19已表明生成模型次序不稳定。API .020897149USD。
- 更早真实e2e 13124seed14/13128seed15：3双方有效对均random更好；critic4/4final有效、random3/4不称稳定有效率收益。
  Leaf方向收益−.91916/−.12765，Space seed15−.00920，缺失不补0。FORETS_CONTEXT_TWO_SEED_RESULTS_20260912.md。
  40调用中4个未派发代码的内核就绪失败误写执行超时，原分数有效但撤回技术完全干净/纯critic能力解释。
- 13129首池完整8程序全无有效提交（6代码错误2超时），无启动故障，数值复验0项不是8项；不补跑。
  同Plus信息包消融8调用闭合，有排序变化但无有效程序，不能称说明有益/无用。详见给学长报告。
- readiness修复source **900fa3bdf6971381c37a9792723dba42c63e5ac6**，仅3启动/异常文件，不改候选执行规则；
  root **forets-readiness-source-20260912-BQletMGi**，archiveSHA221f20372c0b52472172238b4674bb012799d1781dfbb1f05102cbc858a00a71。
  实际executor/witness导入证实未就绪0派发/无质量metadata；13133原镜像old/new各6内核均通过，旧版没复现失败，不能称故障率下降。
  source capsule与接线/真实内核/旧池结果已发布。此修复只用于新生成诊断，旧paid e2e授权不改。

## 已知失败与外部更新

- tps3pbrw不支持schema，0API/GPU；ngtb47lk我方prompt写/input与真实/workspace/data不符，13141整组取消46秒，
  3结果文件未读值，旧8程序不改/重跑、.021790639USD照计。后续prepare核实际容器命令路径。
- vkgl8inm旧scope重名，0新API/GPU；两个停止账副本与排他recovery-claim保留，后继asl已闭合，不再恢复。
- 首次16/17数值校验误要求Spaceship答案全列匹配；已修为PassengerId/Transported并加测试，未改提交/官方分数或重新执行。
- 04:20安全读取学长新0911报告，branch commit **9c46cca1dccd7633b556374d33c6c76390d1d061**，credential-shape0；
  报告SHA5e28c9e94644f7558f50e7f5ddaef5818718357cad5fe1fee43063e38c6901ff。两seed scaling不一致、RL未超BT，3e2e仍探索。
  新报告不等于新合格语料runs/新checkpoint；未修改学长分支。

## 操作与边界

- 不恢复HCE/多保真/Probe/score-channel/K≥1 lookahead/CPU期限筛查/旧静态失败precheck；不更新agent底座。
- first-960/Target-300/Target-522封闭；0910六包隔离，不重复下载raw journals。
- SSH linux5；BASE /research/d7/spc/yzyang4；venvs/aira/bin/python；proxy source /uac/y24/yzyang4/env_setup.sh仅远端。
  PowerShell→bash stdin有CRLF坑；复杂远端命令Python stdin/subprocess。SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
  gpu28的Slurm RealMemory=1MB是不可信登记值，不加--mem8G；真实物理内存并非1MB。原镜像，不退CPU、不投projgpu39。
- key仅远端aira-dojo/.env OPENROUTER_API_KEY，不回显/本地/Git/再索要。仅push myfork HEAD:phase1-value-critic且先secret扫描。
- held12535不碰，g0-r5 PAUSED，无新automation；研究盘1TB/2026-09-29到期，续期未知。保留无关untracked。
- 主要用户交付FORETS_PROGRESS_FOR_ADVISOR_20260912.md，已补全部新池结果/复验边界/下一科学问题。
  05:32队列仅旧held12535，本轮三批任务已完成；学长分支仍9c46cca1dccd7633b556374d33c6c76390d1d061，无新报告commit。
  17项单元测试通过；最终代码/报告/开发ZIP已安全push，可直接交付，不把有限池信号包装成最终搜索收益。
