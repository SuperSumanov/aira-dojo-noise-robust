# 当前交接：四run收尾，零GPU定位analyzer接纳错误

更新2026-09-12香港；最后独立观察2026-09-11 21:14:16.028371 UTC。
恢复：fetch→CURRENT_DIRECTION.md最新0L163→本文件→核现场。学长指导ADVISOR_DIRECTIVES.md L/M/N。
用户要会话内实质推进，不新增自动任务；不把旧队列、计划、mock或进程完成冒充当前结果。

## 刚完成的真实对照

- **13113已FAILED并释放/gpu28**，1932秒双卡、1.0733333333333333GPUh；会话watch PTY3061正常完成收尾。
- 两任务leaf/spaceship、新seed10、两selector四run；顺序leaf random→critic，spaceship critic→random。
  worker状态completed/failed/completed/failed；全部保留，未重跑槽位，未改变运行配置。
- 14程序执行、2exit0，但0/4有效最终解、0/2可比成绩对。不是critic打平或收益。
  leaf/random5执行1exit0，leaf/critic0执行，spaceship/critic5执行0exit0，spaceship/random4执行1exit0。
- 环境修复只共同改draft/improve/debug版本/API/原300秒事实；analyze、critic、原镜像/Torch、5fold及预算未改。
- leaf/critic先ReadError，0.70USD预留未知，后两次BudgetStopped没有真正发出API；spaceship/random也预算停止。
  终态48新增真实API（含route2），加前124共172；本轮已结算0.102788283USD，累计已结算0.421563831USD。
  另保留一次0.70USD未知责任，不释放、不当零费用；运行时unresolved会包括在途，不等于全是失败。
- 13个独立ValidationError/response_invalid已结算；重复日志按attempt_id去重。
  MCTS分析异常回退is_bug=True，可能阻断exit0程序进入final；尚不知具体schema字段，历史失败响应未保存。
  禁止补造响应、重分析旧run补分、中途submission挽救或归因critic选择错误。

## 本次执行证据（不可重提）

- 根 /research/d7/spc/yzyang4/forets-env-20260912-edcpizid
- controller dfad1bba2171b62f6d476129e661de66d3c4801b；source tree 0a587f6b220b1aa0bd154f537f36594bc0690cb3。
- prepared SHA 1e0f29be3f48fb376a2ce4a2740da583d5c39fcdefa9c5f6d2bceac7b100eda9；
  inventory0342f6feb8ff7c6fd94b3a04e18d151422ce7738a3fda255d61f030b7f6714c7；
  release0ddfbdd870d005d9123b8fbcb58c6bb614501db830d373ac3683662517f39e45。
- 旧本轮AUTH942afbfc8864bb07dd6580c1d85a71743e35fea47bc1bdc71081666cab32ecb2，总1.818775548USD。
  submit-intent/submission/block-1.route、runtime-manifest、final-readout、diagnostics、runs_cost_work均已存在；不能重跑submit/activate/closeout。
- 独立sacct闭合后统一读数，journal/task-call一致；最终入口复用best_node已外评分，不重跑最终程序。
  300秒超时存在退出开销，实际耗时不裁短。
- 收尾见FORETS_ENVIRONMENT_CLOSEOUT_20260912.md；本地结果results/forets_environment_20260912。

## 正在推进：人工schema诊断，不占GPU

- phase1/forets_analyzer_diagnostic_20260912.py：最多两个公共人工示例成功/失败，同现有analyze提示及schema，
  原生成模型/路由、8192输出、每次120秒、单尝试无retry，0GPU/任务数据/保护集。
  仅输出validator、字段路径/类型；不打印响应或密钥，不改变生产源文件。
- 真实运行须先验证整块关闭；固定analyzer-diagnostic-intent.json防重复窗口。
  完整复制终态calls（含closed_predecessor和未结项），父账仅stopped=1，子账旧scope cap收紧防重复花费。
  新责任上限0.75USD，含旧全部责任仍<=原100人民币/10USD授权。未知预留不可释放或重置。
- --mock已经两个示例通过，不等于线上通过；3项预算/安全字段测试通过。
  首次Windows测试发现sqlite连接未显式关闭，已修复并复测，不是忽略失败。
- 远端脚本stage /research/d7/spc/yzyang4/forets-env-stage-20260912-N2yAD0/forets_analyzer_diagnostic_20260912.py。
  真实接口尚未启动；先核intent，已有则找报告，不重新开窗。
- 若schema确有问题，只在新版本修复并先有界验收；旧0final完整保留。没有方法正收益时不扩大GPU矩阵。

## 不重做/不越界

- 前13088/13112已封闭：8/8worker完成但0/8final、40执行全exit1；124API已结算0.318775548USD，3.2583333333333333GPUh。
  根forets-paid-20260911-oh3np7b8；报告FORETS_PAID_E2E_CLOSEOUT_20260912.md，公开133618ba。
- 13004/13085负结果、旧CPU期限筛查无信号保留；不重开免费失败窗口/G0/12892/13076。
- first-960/Target-300/Target-522标签、结果、预测、私有选择继续封闭；不恢复HCE/多保真/Probe/score-channel/K>=1lookahead，不更新agent底座。
- 学长分支未改，dojo-reproduce最后fetch065b0fbaa89e0eb663f2834ec768081f5d56394d；
  0907/0909/0909-mcts最后文件清单19:51:45 UTC无变化，不代表其他目录无新语料。
  quarantine32配置不等于32runs；LATEST最后759physical/733eligible、closure=false，未重算。
- 只push myfork HEAD:phase1-value-critic；远端最后独立核对7eb85f68d81aad74e578ceb049365867a940b652。
  每次push前扫待推文件内容和env/key/token/secret文件名，仅输出计数。学长branch不改。
- repo C:/Research/New/my_project/MLEvolve/aira-dojo-codex-20260813；保留用户untracked codex_tmp/output/tmp/旧报告。
- SSH linux5；CPU研究根venvs/aira/bin/python，GPUvenvs/exp/bin/python；网络/uac/y24/yzyang4/env_setup.sh。
  SLURM_CONF=/opt1/slurm/gpu-slurm.conf；gpu28不是projgpu28/39，原MLE镜像禁止投projgpu39。
- 凭据仅远端aira-dojo/.env OPENROUTER_API_KEY→worker PRIMARY_KEY，不本地/Git/输出或再次索要。
- g0-r5 PAUSED，无新自动任务；12535 JobHeldUser不碰；不索要gres.conf，不用失修恢复pool或猜设备9。
- 官方研究盘1TB、2026-09-29到期，续期未知。报告/审计应轻量，不替代真实实验。
