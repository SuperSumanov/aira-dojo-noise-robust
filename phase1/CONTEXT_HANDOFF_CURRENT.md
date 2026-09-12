# 当前交接：同版本复验未确认critic收益；13120全首池诊断正在运行

更新2026-09-12香港；最新现场2026-09-12 00:09:37.738174 UTC。
恢复顺序：fetch→CURRENT_DIRECTION.md最新0L166→本文件→核现场。ADVISOR_DIRECTIVES.md L/M/N仍有效。
用户要求会话内持续实质工作，不增自动任务，不把旧队列、准备或人工测试称为模型正结果。

## 唯一当前GPU作业：13120
- 00:07:59.332899 UTC提交，00:09:37 RUNNING/gpu28，已有1/8程序回执，finished尚无；没有读结果值。
- 会话内只读观察PTY78873：仅sacct、结果文件数量、finished是否存在；整组终态后退出，不自动读分或收尾。
- 根 /research/d7/spc/yzyang4/forets-current-pool-20260912-wnm9cxd0。
  stage /research/d7/spc/yzyang4/forets-current-pool-stage-20260912-awArkuah。
- controller 0fd4d1a7e76e06760d01027bfb96b0c5793782b5；task source tree 6ca01fba9892a350cbb24152054b5296dc7095f1。
  固定plan.private SHA256 08ac4d511382e78efb1a1c66e5cd4c4b12c3a92712e632068d9c15fb2f9773d9。
- 原两任务seed11 critic臂step1全部4+4原代码，重复slot保留，按任务/slot升序，各执行一次。
  原SIF/300秒/6CPU/1GPU，84分钟分配加停止余量≤1.5GPUh；0生成API、0critic调用、0训练。
- prepare、submit-intent、launch已存在；不要再次prepare/submit、不要改运行中的代码或补跑槽位。
  代码冻结已绑定submit-intent；不能覆盖bin/opencl-vendors或已经复制的native文件。
- 这是全池即时选择质量诊断，不是e2e、不含K≥1lookahead/多保真、不重跑旧13085。
  原方案FORETS_CURRENT_POOL_PLAN_20260912.md；当前启动条件来自13118复验未确认收益，不按候选好坏选池。
- 全部8槽和Slurm闭合后，调用根/forets_current_pool_20260912.py readout --root 同一根一次，
  然后根/verify_forets_current_pool_20260912.py --root 同一根一次。当前两者尚未执行。
  readout要求COMPLETED和完整8槽；基础设施失败则保留失败、解释原因，不重试。
- 当前保留原始submission，未来数值校验按实际sklearn1.6.1/原task规则；4人工例一致不当真实任务结果。
  6个继承绑定文件匹配父manifest，10Python解析/依赖导入及shell语法通过；不是重复GPU验收。

## 已闭合：13118 seed12 与 13115 seed11
- 13118 COMPLETED/gpu28，3337秒双卡=1.853888888888889GPUh；4进程完成、3有效final、1可比成绩对。
  Leaf：random无final，critic logloss0.37782；Spaceship：random0.80805、critic0.61839，差−18.96600pp。
- 13115：2有效final，Leaf双方无final；Spaceship random0.74368、critic0.79655，差+5.28700pp。
  其4564秒双卡=2.5355555555555553GPUh。正差值没有复现，不能宣称稳定收益/clean scaling。
- seed11 Spaceship全池未实际改选；seed12 Leaf全池未实际改选。两处有利表象均不能归功于critic选择。
  seed12实际slot及原字节/AST改选仅Spaceship step1/3；独立生成随机性仍存在，也不能将全部降幅归因于critic。
- 不将缺失补零/称打平，不跨任务混合平均，不反转score或按结果选k。
  两seed完整表/条件中位数/方差见FORETS_SEED12_CLOSEOUT_20260912.md与results/forets_repeat_20260912。
- 13118原watch PTY34987 SSH断开；原PID3678839随后已退出。确认所有primary输出不存在后，
  00:03:01只执行一次closeout；00:03:24独立final、00:03:30独立selection各一次，均已完成。
  只读PTY11591已正常结束。不得重复收尾或再次运行这些只写一次的verifier。
- 13118根 /research/d7/spc/yzyang4/forets-repeat-20260912-zuvnt3oa，
  stage /research/d7/spc/yzyang4/forets-repeat-stage-20260912-qtUUmjQE。
  controller aa4f13c2cc480f7ead84b1970b3511c5b6dd6a30；source35711518b3b7262bccd3bebfdd2b4a4b7c726715。
  两版本源码只差paid_budget.py的授权结转，不是科学旋钮变化。
- 13118本块64API/0.143920179USD；累计304API、0.718421106USD已结算，旧0.70未知保留，
  累计责任1.418421106USD。13120不使用此API账本；后续API仍需逐行结转，不能另开100人民币/10USD总额。
- 8份新导出远端credential scan 0、传输SHA全部匹配。初次本地检查误纳入目录中已有build/parent-seal两文件而中止，
  后按明确8文件范围核对通过；两旧文件Git跟踪且未变，无实际hash漂移/覆盖。
- 独立final SHA 8d7d97426828227bbdd5df758956f8245db74a8d962d9a6fd854012a7341bd9f；
  selection SHA 82498f29b793e7ca43ee0d73bed4296112d3ae16265dfb9bea8692f26188d66a；
  两seed汇总SHA 6d373c97fe91527b081b1b0308ed0c5c43a5876c946192c5ee7b7b5bb245beaa。
- 13115根 /research/d7/spc/yzyang4/forets-review-20260912-csh5q4i8，旧收尾全部完成。
  两e2e块原task删CSV，因此是所选节点/外部grade一致性，不是独立数值重评分。
  代码capsule在phase1/releases/forets-review-20260912，含实际源及匹配LICENSE；不重新打包私有候选。

## 学长上传与长期边界
- 0910六包/115079888bytes已隔离到 /research/d7/spc/yzyang4/senior-quarantine-0910-20260912，
  24配置、2commit、num_children=2/3；不是24新增有效run。未开journal/env/code/outcome、未正式摄取或训练。
  61459c0a提交日期8月26日，上传日期不能当运行日期。根列表50项可能分页，不能称所有上传完整覆盖。
  见SENIOR_0910_INTAKE_STATUS_20260912.md；不要重下载/重写隔离输出。
- 学长分支未改。最后head dojo-reproduce065b0fbaa89e0eb663f2834ec768081f5d56394d，
  collect4029f62688b28f2bb979b5dc18a500cc6d669a79。LATEST最后759physical/733eligible、closure=false，未重新推进。
- first-960/Target-300/522保持封闭；不恢复HCE/多保真/Probe/score-channel/K≥1lookahead，不更新agent底座。
  13113、13088/13112、13004/13085、旧CPU期限筛查的失败保留；不再G0/12892/13076或免费路由窗口。
- 只push myfork HEAD:phase1-value-critic；最后公开核对0fd4d1a7e76e06760d01027bfb96b0c5793782b5，当前收尾报告待push。
  每次扫描staged内容及env/key/token/secret文件名；不全add用户untracked codex_tmp/output/tmp/旧报告。
- repo C:/Research/New/my_project/MLEvolve/aira-dojo-codex-20260813；SSH linux5；venvs/aira CPU/控制，venvs/exp GPU/gdown。
  网络/uac/y24/yzyang4/env_setup.sh；SLURM_CONF=/opt1/slurm/gpu-slurm.conf；gpu28不是projgpu28/39，原MLE镜像不投39。
- 凭据仅远端aira-dojo/.env OPENROUTER_API_KEY→worker PRIMARY_KEY；不回显/本地/Git，不再索要。
- g0-r5 PAUSED，无新automation；12535 JobHeldUser不碰，不索要gres.conf，不使用失修pool恢复或猜物理设备9。
- 研究盘1TB、2026-09-29到期，续期未知。df显示共享盘32T可用不是个人quota；quota -s只列home，不能混为研究盘余额。
