# 短交接：三批真实执行与两批盲排名闭合，局部正信号但无e2e收益

2026-09-12最后更新05:32 UTC。用户本轮02:44起要求三小时有价值证据，目标05:44 UTC；本轮实验证据已闭合，无新automation。
恢复先fetch→CURRENT_DIRECTION顶部→本文件→现场；主线同预算MLE-bench最终收益，不以旧状态替代当前事实。

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
  已credential-scan/逐项回读；标签都已读，只能开发，不得当新冻结测试。正在完成最终安全push。

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
  17项单元测试通过；最终代码/报告/开发ZIP安全push后交付，不把有限池信号包装成最终搜索收益。
