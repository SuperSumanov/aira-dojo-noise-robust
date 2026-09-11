# 当前交接：seed11闭合有单次正差值；准备同版本seed12复验

更新2026-09-12香港；整块最后观察2026-09-11 22:57:34 UTC，独立核对22:59:03 UTC。
恢复：fetch→CURRENT_DIRECTION.md最新0L165→本文件→核现场。学长指导ADVISOR_DIRECTIVES.md L/M/N。
用户要会话内实质推进，不新增自动任务；不把旧队列、计划、mock或进程完成冒充当前结果。

## 当前闭合事实与接续（优先于下文运行期观察）

- **13115 COMPLETED/gpu28**，4564秒双卡=2.5355555555555553GPUh，PTY19866已正常结束并自动完成primary closeout。
- 独立验证已实际执行，根下independent-final-verification.json；不是数值重评分，禁止重复写入。
- 2/4有效最终解、1/2可比对；Spaceship random0.74368、critic0.79655，差5.28700pp；Leaf两臂无有效final。
  这是第一条单seed探索信号，不是跨seed稳定收益或clean scaling；详见FORETS_REVIEW_CLOSEOUT_20260912.md。
- 新增62API/0.152156823USD；累计240API、0.574500927USD已结算，旧0.70未知仍保留，总责任1.274500927USD。
- 收尾JSON/CSV已复制到results/forets_review_20260912，远端扫描0凭据命中、本地SHA逐项匹配。
- seed12两任务四run同配方方案已写；新入口forets_repeat_build_20260912.py已准备，**尚未构建/激活/提交**。
  新预算/源码接线6测试、真实controller/readout/route派生2测试通过；不运行Plus或被动submission留档新路径。
- 父账事实已冻结stage/seed12-parent-facts.json：117rows、ledger SHA190dc0f754f6aa4acd0d7e5f147701dc4b966a10320a93f0a5f3d6cc88043e59。
  facts模式已消费该输出，不覆盖。计划新增责任2USD/最多10GPUh，累计上限3.274500927USD；旧unknown完整保留。

## 已关闭seed11包定位及历史运行期观察（禁止重复启动）

- 新包 **/research/d7/spc/yzyang4/forets-review-20260912-csh5q4i8**，source tree
  6ca01fba9892a350cbb24152054b5296dc7095f1；controller **a383c2abb5fa9def7e85e7b3313c3894159e7be3**。
- prepared e6ec9d4c6664a98a6c069b13cb85624ece78b864adf036591ed34f4c8df18718；
  inventory9fbd2e1a336a96c241a03a837649854b38e1fd0d12991d3bac3f94367df28a6a；
  releasecf87a4c186d04c4021d69844c8698de11a80b4c5cf9cc18beaa0c3582f6e4f36；
  AUTH4bbac52d02eb1109aded9aeca4d73cd670fb7893afe5988973ace34a7204d98e。
- 构建成功、STATIC_READY；实际MCTS接纳方法7个CPU人工案例通过，旧错误也复现，不是新GPU/G0。
- 55账本行已完整复制（含1未知预留和历史合并行），dgzmkcqh旧账已sealed。
  新总责任上限3.122344104USD，其中新增最多2USD；旧scope全关闭，route改route_s11，四新scope各1.50USD。
  route检查只容忍相同的历史unknown IDs，任何新unknown都拒绝，不把历史未知当零或初始化掉。
- **13115 RUNNING/gpu28**，提交2026-09-11 21:41:20.187089 UTC；两leaf及spaceship/random进程completed，spaceship/critic运行。
  route两次已通过且结算；工具PTY46886整条正常完成。新根submission/submit-intent已存在，绝不能重跑route/submit/activate。
  新旧累计226实际API，已结算0.537790071USD；观察时2未结包含历史未知及可能在途，不能当作2次失败。
  22:42:46 UTC仅执行元数据：两leaf各五次执行全返回、各0exit0、各4次超时；未读本组final或据中途成绩改配置。
  22:42:52 UTC两个完成run各15个实际API和15个终态事件逐一对应，全部response_returned，无ValidationError。
  原schema问题在这两个真实run未复现，但程序本身仍不能成功，不能称critic收益。
  22:51:26 UTC执行元数据：spaceship/random五次返回有1exit0；critic两次返回0exit0。
  此处只核执行状态，整组final仍未读，不能据此声称有效最终解或两臂差值。
- 新包下forets_environment_session_20260912.py已派生为seed11；billing扣55旧rows计新增，累计仍扣合并1条加历史124。
  会话内watch已启动，工具PTY **19866**；已从启动期转入首个worker。
  优先poll此session；它在整块终态后自动closeout，禁止第二个收尾写入者。
- Stage /research/d7/spc/yzyang4/forets-review-stage-20260912-fQzyb0；本地artifact codex_tmp/forets-review-artifact-20260912。
  原SIF/critic/步骤/超时不动；源代码只变lite_llm.py、review_metric.py、paid_budget.py。
- 收尾后追加独立验证器verify_forets_review_final_20260912.py（当前未运行）：独立sacct终态门、
  最终选中节点/外部grade一致性及累计费用。原task评分后删submission.csv，不能声称本轮数值重评分。
  已scp到上述stage同名文件，SHA37e453bfba90e85616f704c92ecc809093c823a247026597ab49ef0d5e78cd5e；
  等watch 19866完成primary closeout后再运行一次，不作为第二个primary写入者。
  forets_submission_archive_20260912.py仅为未来批次准备的host-only被动留档，尚未部署；不改13115。
  7项本地人工测试通过，原evaluator精确patch锚点/语法也通过；不是新端到端结果。
- 实际source tree不随公开分支可达，已导出纯代码/config capsule（276文件，334064字节），
  本地独立核验全部成员/hash，234个source逐字节匹配Git对象；0凭据命中，无模型/数据/候选/结果。
  见phase1/releases/forets-review-20260912；archive SHA2a33f870ac88b1bf2a2902d7bde7900a18aba8b1c61feb737761bbeb3d3d1f3b。
  不是完整Git历史或跨机器复跑证明，不直接执行历史submit/route。
- 条件后继投资顺序见FORETS_POST_REPAIR_DECISION_20260912.md：尚未选择/提交后继块。
  Plus官方metadata已只读核价；最坏请求责任2.517372USD，不能套用当前0.70预留。未调用Plus。
  forets_successor_budget_20260912.py只做未来源码/预算准备，6项定向测试通过，包含实际发布源码接线；
  未激活新账本、未选择新模型。第一次广域unittest discovery误导入无关包失败，改定向调用后通过，未改无关包。

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
  MCTS分析异常回退is_bug=True；随后人工API诊断已定位metric字符串类型，历史失败响应本身未保存。
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

## 已完成的人工schema诊断与新矩阵构建（不重做）

- phase1/forets_analyzer_diagnostic_20260912.py：最多两个公共人工示例成功/失败，同现有analyze提示及schema，
  原生成模型/路由、8192输出、每次120秒、单尝试无retry，0GPU/任务数据/保护集。
  仅输出validator、字段路径/类型；不打印响应或密钥，不改变生产源文件。
- 真实运行须先验证整块关闭；固定analyzer-diagnostic-intent.json防重复窗口。
  完整复制终态calls（含closed_predecessor和未结项），父账仅stopped=1，子账旧scope cap收紧防重复花费。
  新责任上限0.75USD，含旧全部责任仍<=原100人民币/10USD授权。未知预留不可释放或重置。
- --mock已经两个示例通过，不等于线上通过；3项预算/安全字段测试通过。
  首次Windows测试发现sqlite连接未显式关闭，已修复并复测，不是忽略失败。
- 远端脚本stage /research/d7/spc/yzyang4/forets-env-stage-20260912-N2yAD0/forets_analyzer_diagnostic_20260912.py。
  原人工示例两次均metric:string失败；v1成功例过、失败例未过；v2两例全部通过，历史结果仍不补分。
  修复helper=forets_review_metric_20260912.py，SHA aa919e2635ff866d382c49fcb297aac752651163079a968f93cbb113042fde77。
  明确is_bug=True时文本metric置null，仍是坏节点；其余仅合法JSON数字/null恢复，其他字段/无效值不松动。
- 上轮诊断账本（已被新seed11完整结转并sealed）**/research/d7/spc/yzyang4/forets-analyzer-live-dgzmkcqh**；AUTH
  581f1c378636728df93c6502a4e45513847eed29b86de5a577309d72967f21b5。
  55行包括历史124call的1条合并行，真实累计178API；settled=422344104 nanoUSD，held=1122344104 nanoUSD，1未知。
  ko8vhkcz/lizj2miy两前诊断账本已sealed；新矩阵须完整复制dgzmkcqh所有rows，不能初始化丢掉未知责任。
  初次凭据安装顺序、v1加载类内类型别名两处前置失败均0真实API，已修复；不重复那些窗口。
- forets_review_build_20260912.py已构建/激活：seed11两任务四run，leaf critic→random、spaceship random→critic。
  原gpu28/双卡/镜像/critic/6step/300秒；仅共同parser兼容+每run责任预留cap1.50USD，新增全块cap2USD。
  新增GPU上限10h，加历史实耗4.331666666666667GPUh；原API100人民币/10USD不重置。提交状态看顶部，不照旧13113重投。
  构建/类型兼容/账本共11项本地测试通过；生产方法人工fixture也过。计划FORETS_REVIEW_REPAIR_PLAN_20260912.md。

## 不重做/不越界

- 前13088/13112已封闭：8/8worker完成但0/8final、40执行全exit1；124API已结算0.318775548USD，3.2583333333333333GPUh。
  根forets-paid-20260911-oh3np7b8；报告FORETS_PAID_E2E_CLOSEOUT_20260912.md，公开133618ba。
- 13004/13085负结果、旧CPU期限筛查无信号保留；不重开免费失败窗口/G0/12892/13076。
- first-960/Target-300/Target-522标签、结果、预测、私有选择继续封闭；不恢复HCE/多保真/Probe/score-channel/K>=1lookahead，不更新agent底座。
- 学长分支未改，dojo-reproduce最后fetch065b0fbaa89e0eb663f2834ec768081f5d56394d；
  0907/0909/0909-mcts最后文件清单21:48:14 UTC无变化，不代表其他目录无新语料。
  quarantine32配置不等于32runs；LATEST最后759physical/733eligible、closure=false，未重算。
- 只push myfork HEAD:phase1-value-critic；远端最后独立核对7b1468d89f36d106ca58d485b19ee6e5a758ae08。
  每次push前扫待推文件内容和env/key/token/secret文件名，仅输出计数。学长branch不改。
- repo C:/Research/New/my_project/MLEvolve/aira-dojo-codex-20260813；保留用户untracked codex_tmp/output/tmp/旧报告。
- SSH linux5；CPU研究根venvs/aira/bin/python，GPUvenvs/exp/bin/python；网络/uac/y24/yzyang4/env_setup.sh。
  SLURM_CONF=/opt1/slurm/gpu-slurm.conf；gpu28不是projgpu28/39，原MLE镜像禁止投projgpu39。
- 凭据仅远端aira-dojo/.env OPENROUTER_API_KEY→worker PRIMARY_KEY，不本地/Git/输出或再次索要。
- g0-r5 PAUSED，无新自动任务；12535 JobHeldUser不碰；不索要gres.conf，不用失修恢复pool或猜设备9。
- 官方研究盘1TB、2026-09-29到期，续期未知。报告/审计应轻量，不替代真实实验。
