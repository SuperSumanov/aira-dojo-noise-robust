# 短交接：两seed质量不支持收益，完整池13129运行

2026-09-12，最后更新03:55 UTC。恢复：fetch→CURRENT_DIRECTION顶部→本文件→现场。
用户要求约02:44→05:44 UTC三小时内真实有价值证据；留在会话，不新建automation。
主线同预算上限真实MLE-bench最终收益，不重复G0/模型验收、不补失败槽。

## 唯一运行GPU作业

- 13129单次03:43:10.736990 UTC提交，03:47观察RUNNING/gpu28，2/8结果文件，仅看结构。
  root /research/d7/spc/yzyang4/forets-current-pool-20260912-0hz06xtj。
  stage forets-context-pool-s14-stage-20260912-5DgFYoKM。
  controller d3331edafc4ca3277131e5a5a4f44a1189a72940；source f70eb4859c48c61bba37b298fbf8e32e367644ae。
  plan SHA6bbe805e1113bbd7d899914178da79ef773ae8ae5f1306ba645066c397c0f02c；
  实际主脚本SHA40e082a64ecddd79f16f72dd122ec1b58e350fc447a5612219292bc319b1c772。
- seed14两critic首池全部8原槽各新执行一次，保留重复/失败，无新生成/critic调用。
  原镜像/单RTX3090/6CPU/300秒每槽，最多84分钟1.5GPUh；13128已结束，避免主动同机竞争。
  已prepare/deploy/submit，不重做、不向冻结根添加文件、不重跑。
  all8+COMPLETED后单次root/forets_current_pool_20260912.py readout --root本根；
  再root/verify_forets_current_pool_20260912.py --root本根；均未执行。
  只能有限池即时选择诊断，不能当8独立搜索seed或e2e确认。

## 已完成8调用信息消融，等待执行值

- root /research/d7/spc/yzyang4/forets-information-ablation-20260912-rwohlohw；
  stage forets-information-stage-20260912-FN8R41vW。
  controller65f0228d54ac93e281fb6607d84e6b2bac9080b7；
  scriptSHA5915660edbd5a926adb7f59d242a5bf796468533bfe6d6e54bc72492ac5bc60e；
  preparedSHA42cacb1ed94c71ca09edfb8f7b62c4c8dab68fa9d5512a9d5fc34465964984b6。
- 03:16:46冻结早于seed15揭盲，03:43:44.493263全部8调用ranked，无新未知；旧session86066已结束。
  2任务×full/omitted×正逆，Plus/Alibaba，同完整代码/说明/聚合，唯一变化为整个环境资源/API说明包。
  排名未读；新执行全8闭合并独立通过后，stage脚本readout --root本根 --commit上述65f完整SHA，单次。
  不能重run/补调用/改请求；不是未触碰确认，两个已探索开发池、一次程序执行。
- 当前唯一ACTIVE账在本root，seed15已SEALED。
  AUTHf799ccb82373b1a3d4bcaf5ea1031b5cc67207f30270f8b25212d95a693f3344。
  362账行、累计settled1.213580368USD、责任2.613580368USD、未知2，新增0.035282USD。
  本窗口累计cap5.578298368USD；原100人民币/保守10USD不重置，旧两个0.70未知责任不释放。

## 已闭合真实结果，禁止重复读出/校验器运行

- 13128 seed15 root forets-repeat-20260912-3no2iopd，stage forets-context-s15-stage-20260912-BQv6QexP。
  COMPLETED，2873秒/.7980555555555555GPUh；4attempt1完成，4有效final，20程序/5正常退出。
  closeout03:42:39、独立原submission数值复验03:42:55通过，汇总已生成，不再运行。
  Leaf random.33670/critic.46435；Space random.80575/critic.79655，两个质量对均critic更差。
  source54e353963a6899965896b2e8ea492207829b3cbd；controllerf53ed6693d029070662c50f81ea7146f0a9e4d35。
  prepared883062309b6edeee43ac93be26042c9376279ab712948e034bceb39dc67dae1e；
  verifier receipt SHA4ca4ff5e5f8c5f666d109f41763562a66ae9f16ff60a24e6a8e7413a6a105fd5。
  新70API/0.171161133USD，账已SEALED；readonly observer88689结束。
- 13124 seed14 root forets-repeat-20260912-x3pkniqp，独立数值通过；Leaf random.50877/critic1.42793；
  Space random缺失/critic.81839。3有效final，.8955555555555555GPUh，新70API/.192376990USD，账SEALED。
  receiptSHA93313ffb7777a549397c08d98716b2373a38224b2d28c7b473e0510fb61571b2。
- 两seed合计3可比对均random更好，critic4/4有效vsrandom3/4，小样本不称稳定有效率收益。
  不再扩同一配方；两臂独立生成，不能把所有差异归因具体改选。缺失不补0。
  汇总代码SHAed211e50fc840198f298e7170ab45ca2690021c4170029c0d0c122973076443d，8行CSV+JSON在root15。
  6个安全公共产物已下载phase1/results/forets_context_s15_20260912/，报告FORETS_CONTEXT_TWO_SEED_RESULTS_20260912.md。
- 13123旧整组取消源于小池flag接入缺陷，不恢复/读效果；旧seed11/12相反差值不是稳定选择收益。

## 发布与约束

- 最近已push c8b91882f0d54efed0fd47b6b46a1a312ef68791；本次新报告/交接/结果待下一push，查git status。
  seed15源码capsule已公开284文件，不重导出；无任务数据/模型/候选/响应/key。
- 相关工作FORETS_METHOD_POSITION_CHECK_20260912.md：CEB经验critic、ReASearch经验搜索、CHIME分离记忆有强重叠；
  强裁判/环境说明/双序Borda或泛称经验记忆不是新颖性证明；未据此更改当前冻结协议。
- 0910六包115079888bytes隔离senior-quarantine-0910-20260912；24配置≠24新run，不重下载原日志。
  03:02 fetch学长分支未变：dojo-reproduce065b0fbaa89e0eb663f2834ec768081f5d56394d；collect4029f62688b28f2bb979b5dc18a500cc6d669a79。
  LATEST此前759physical/733eligible，非当前重验，无closure；first-960/Target-300/Target-522仍封闭。
- 不更新agent底座，不恢复HCE/多保真/Probe/score-channel/K≥1lookahead/CPU期限筛查，不升级镜像或静默退CPU。
- SSH linux5；BASE /research/d7/spc/yzyang4；venvs/aira控制评分，venvs/exp GPU。
  source /uac/y24/yzyang4/env_setup.sh；SLURM_CONF=/opt1/slurm/gpu-slurm.conf；节点gpu28/27非projgpu39。
- key仅远端aira-dojo/.env OPENROUTER_API_KEY→worker PRIMARY_KEY，不输出/本地/Git/再索要。
  只push myfork HEAD:phase1-value-critic，每push扫描staged名称/内容；保留无关untracked，held12535不碰。
  g0-r5 PAUSED，无新automation。研究盘1TB，2026-09-29到期，续期未知。
