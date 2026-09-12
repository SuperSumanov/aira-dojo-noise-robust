# 短交接：seed15运行，seed14混合结果已公开

2026-09-12。恢复：fetch → CURRENT_DIRECTION顶部 → 本文件 → 现场；不要按旧状态重复作业。
用户要三小时内有价值的真实证据，约02:44→05:44 UTC；保持会话，不建新automation。
目标为同预算上限真实MLE-bench最终收益，不重复G0/验收，不补失败槽。

## 当前唯一e2e作业

- 13128 seed15，两任务×两臂；02:53:37单次提交，最后03:29:12观察RUNNING/gpu28。
  Leaf两臂和Space random均完成，Space critic运行；全为attempt1。未读seed15最终值。
- 根 /research/d7/spc/yzyang4/forets-repeat-20260912-3no2iopd；stage forets-context-s15-stage-20260912-BQv6QexP。
  controller f53ed6693d029070662c50f81ea7146f0a9e4d35；source54e353963a6899965896b2e8ea492207829b3cbd。
  prepared883062309b6edeee43ac93be26042c9376279ab712948e034bceb39dc67dae1e。
  inventory46f64a5012bab52672a43c55d192755c2cfdaaf045c681cac05a0906a3620afc；
  release76d473142e4038962322abc9b10b14fe94bab2246dfa6964a0b88130d29207b9；
  AUTHc623a0236a59df74f9dac1f3641ea724c9f2fdece7266c23aa604e6aaab1bb5e。
- 已build/inspect/16实际全宽度检查/activate/catalog/route/submit，不重复。
  原镜像/单RTX3090/6CPU/6step/300秒/3540秒，max_parallel1，allocation280分钟≤5GPUh。
  Flash生成、Plus/Alibaba双序Borda→原top2/common-priority；两臂skip_redundant_critic=true，小池≤2旁路。
  与seed14仅seed/次序及累计授权身份不同，不改信息包/聚合/平分/任务。
- 唯一ACTIVE账在此根，seed14已SEALED。继承284行、结算1.007137235/责任2.407137235USD/未知2；
  路由后286行。03:07新25API含路由、新结算0.051994787USD，未知3含在途，不释放责任。
  本窗口累计≤5.907137235USD，原100人民币/保守10USD累计不重置。
- 只读观察器exec session88689（observe_forets_context_s15_20260912.py --watch）。
  旧6844于03:29前SSH连接重置结束；立即重连确认真实作业未中断，不重投/补跑。
  实际session为根/forets_environment_session_20260912.py：status只读，watch自动closeout不要用。
  全4终态后单次closeout → stage/verify_forets_context_s15_20260912.py →
  summarize_forets_context_repetition_20260912.py（须两块COMPLETED且独立通过）。
  所有依赖已stage；seed15闭合动作均未执行。

## 下一项真实机制验证：准备好，未提交

- seed14两个critic首池原全部8槽，各新执行一次；保留失败/重复，不与旧执行混拼。
  根 /research/d7/spc/yzyang4/forets-current-pool-20260912-0hz06xtj；
  stage forets-context-pool-s14-stage-20260912-5DgFYoKM。
  plan SHA6bbe805e1113bbd7d899914178da79ef773ae8ae5f1306ba645066c397c0f02c。
  gpu28单RTX3090/6CPU/每槽300秒/原镜像，上限84分钟1.5GPUh，0API/0新模型训练。
  已prepare/deploy/核原执行依赖，不重做。13128终态前submit会拒绝，避免主动增加同机竞争。
  之后本根/forets_current_pool_20260912.py submit --root 本根 --commit d3331edafc4ca3277131e5a5a4f44a1189a72940。
  全8闭合才readout，再本根/verify_forets_current_pool_20260912.py --root 本根。
- 新同池信息消融：2任务×full/omitted说明包×正逆=8个新Plus请求，0GPU，说明包是唯一变化。
  方案FORETS_CONTEXT_INFORMATION_ABLATION_20260912.md；脚本forets_context_information_ablation_20260912.py。
  03:16:46已prepare，根forets-information-ablation-20260912-rwohlohw，stage forets-information-stage-20260912-FN8R41vW。
  commit65f0228d54ac93e281fb6607d84e6b2bac9080b7，prepared SHA42cacb1ed94c71ca09edfb8f7b62c4c8dab68fa9d5512a9d5fc34465964984b6；
  script SHA5915660edbd5a926adb7f59d242a5bf796468533bfe6d6e54bc72492ac5bc60e。
  实际4组配对输入/8请求hash检查通过，仅说明包字段不同；未activate/API，paid.sqlite不存在，不重prepare。
  13128正常关闭且独立通过后才本stage脚本run --root本根 --commit上述65f完整SHA，seal/carry账，新≤3USD且原10USD不重置。
  新8程序结果和裁判排名须完整闭合后合并；已知开发池，不是未触碰确认，不按seed15符号挑任务。

## 已完成实证，不重做

- 13124 seed14，根forets-repeat-20260912-x3pkniqp：02:48:17独立通过，4run/12池完整，3/4有效final。
  Leaf random0.50877 vs critic1.42793（更差）；Space random缺失 vs critic0.81839，不补零。
  两critic首池实际改选代码，小池正确旁路。三个原submission数值复核一致，0.8955555555555555GPUh。
  closeout/verifier已完成，receipt93313ffb7777a549397c08d98716b2373a38224b2d28c7b473e0510fb61571b2。
  新API0.192376990USD，旧账SEALED。FORETS_SMALLPOOL_S14_RESULTS_20260912.md已公开。
  verifier修正仅允许框架已证明附加的validity_feedback，原grader字段仍精确匹配，未改结果。
- seed15门在seed14读数前已发布：技术干净且至少1可比对就两任务均重复，无论收益正负。
- 13123 seed13整组CANCELLED：skip_redundant_critic=false小池rank异常，我方接入问题，非效果。
  .415GPUh，取消未知0.70USD已继承；不重启/补槽/读分。c36qpa1h拒绝构建未激活花费，不用。
- 旧13120 seed11全首池：Leaf0/4有效；Space1/4有效.8069，原8Btop2漏掉；Plus双序均保留但排序不稳。
  仅2开发池探索，非e2e。旧8B两seed Space+5.287pp/−18.966pp，无稳定可归因收益。

## 发布、语料、边界

- 最新已push 65f0228d54ac93e281fb6607d84e6b2bac9080b7；后续待commit项看git status。
  seed15 capsule phase1/releases/forets-context-s15-20260912/release-code-capsule-s15-v1.tar.gz，
  SHA784a535057aad68b1712feedf3f927d50a7b943f4ff77f728f2f721d988b0808，284文件/237真实Git源码/28controller/2许可证。
  已公开，不是待push；无候选/模型/数据/响应/密钥，不重导出。
- 相关工作已查FORETS_METHOD_POSITION_CHECK_20260912.md；强裁判/双序Borda/固定步预算非独立新颖点。
- 0910六包115079888bytes隔离senior-quarantine-0910-20260912；24配置≠24新run，不重下载/摄取原日志。
  03:02 fetch学长分支无新提交：dojo-reproduce065b0fbaa89e0eb663f2834ec768081f5d56394d；
  collect4029f62688b28f2bb979b5dc18a500cc6d669a79。
  LATEST此前759physical/733eligible，非当前重验，无closure；first-960/Target-300/Target-522封闭。
- 不更新agent底座，不恢复旧HCE/多保真/Probe/score-channel/K≥1lookahead/CPU期限筛查。
- SSH linux5；BASE /research/d7/spc/yzyang4；venvs/aira控制评分，venvs/exp GPU；
  网络source /uac/y24/yzyang4/env_setup.sh；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
  gpu28/27原MLE镜像，不是projgpu28/39；不升级Torch/退CPU，不索要gres.conf。
- key仅远端aira-dojo/.env OPENROUTER_API_KEY→worker PRIMARY_KEY，不回显/本地/Git/再索要。
  repo C:/Research/New/my_project/MLEvolve/aira-dojo-codex-20260813；只push myfork HEAD:phase1-value-critic。
  每push扫描staged文件名/内容；保留无关untracked；held12535不碰。
  g0-r5 PAUSED，无新automation。研究盘1TB，2026-09-29到期，续期未知。
