# 短交接：共同起点全八已闭合，有一个正信号但无稳定收益

2026-09-13 HK / 09-12 20:05:08 UTC独立读出；恢复先fetch→CURRENT_DIRECTION顶部0L188→核现场。
本轮用户要一小时内有价值结果，始于19:12UTC。详见FORETS_COMMON_START_RESULTS_20260913.md。

## 已闭合，禁止重跑
- 13190/13191已终态，本轮无活跃GPU。8个起点和8个终点原提交独立评分通过，每对起点一致；6条技术合格/3对。
- Leaf28/29起点1.51485，random .36598/.39201，critic均1.51485，两seed均不利于critic。
- Space29起点.79655，random .79310、critic .81034；合格正差+.01724，但只有一个seed，不能说稳定收益。
- Space28两臂均不合格、终点均起点.79655：critic后续调度前KernelReadinessError；random BudgetStopped于62.85574474791065秒。
  该对不得纳入合格均值或补跑；原冷启动random2/4 vscritic0/4不覆盖。
- 实际3693allocation秒=1.0258333333333334GPUh；搜索API .464261850USD、含route增量.464489298USD。
  ROOT账本981条，结算3.162067233/责任4.562067233USD，2旧未知、0新增未知，stopped=False。不能重置账。
- source 1ec18564f176d58a3a7ac3a46852ad92044777b5；controller a46dbd189d6f74cf7357377ba41fcc065b1d414c。
  reader a81f0c44416f8adc6cadaf4231d9b9f7f18b821d只执行一次成功；5正式文件本地SHA匹配。
  summary SHA3b1322cea5406d5e0197694f6b9e9af85a466bd005d590416f6070989a4ce408；
  CSV SHA19b01ae9034fdaac22412586410abc4288e7094cf6c6d40e60d1ac77e9ae8112。

## 接着做什么
- 先针对实际两类退出处理，不重复无关G0/标记测试。内核就绪故障在Space critic28后续调用再现，不能声称已解决。
- 预留拒绝scope仅4次结算.007792122USD/cap4USD、无新未知。共享并发预留压力是推断，缺瞬间账快照。
  Flash预留.7USD/请求、Plus2.6USD；初始8路可容纳不代表费用累计后仍可容纳。考虑有界等待瞬时预留，仍守截止/责任帽；尚未实现修复。
- 旧4份Space真实图是单链；debug自动接树，不是节点丢失。审计v1误把step边当UUID，假悬空数作废；v2与原件并存。
- 优先后继FORETS_EXECUTED_BRANCHING_NEXT_20260913.md：新30/31×两任务×random/critic全8，两臂execute2。
  入口和实际batch CPU接线通过（首步1、后续2兄弟、0API/0GPU测试），未部署；新账/来源/多slot读出仍须完成。
  旧单slot verifier不可直接用。incumbent-parent和single-proposal备选也准备未部署，不一起混改。
- 本轮是Plus API critic而非学长8B模型、不是训练或干净scaling。不凭单个好数扩大主张。

## 位置与边界
ROOT /research/d7/spc/yzyang4/forets-wallclock-20260912-2o9mw39n
STAGE /research/d7/spc/yzyang4/forets-common-stage-20260913-I7fhYJJa
本地 phase1/results/forets_common_start_s28_s29_20260913/
SSH linux5；Python /research/d7/spc/yzyang4/venvs/aira/bin/python。
MLE原镜像仅gpu27/gpu28兼容3090，不能投projgpu39/升级Torch/静默CPU回退；旧held12535不动。
19:47 fetch学长dojo-reproduce仍113e25e7fa2570cb5f60401d051a1de3cce307c2，未改学长分支。
本地模型共享上次PermissionError、已有问询待回复；不重索要key。Key只在远端aira-dojo/.env，OPENROUTER_API_KEY→PRIMARY_KEY。
first960/Target300/Target522封闭；无底座更新；不恢复HCE/多保真/Probe/score-channel/lookahead。
只正常push myfork HEAD:phase1-value-critic，先内容/归档secret扫描，不force；保留无关未跟踪目录与旧实验。
研究盘2026-09-29到期、续期未知。本会话未建automation。
