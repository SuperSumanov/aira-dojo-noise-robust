# 当前交接：全首池与通用裁判已闭合，准备新seed真实对照

2026-09-12香港。恢复：fetch→CURRENT_DIRECTION最新0L169→本文件→现场。
用户要求持续会话实质工作，不增自动任务；准备/测试不冒充效果，学长分支不改。

## 刚完成的执行13120
- 00:21:39 UTC观察COMPLETED/gpu28，8/8原程序、805秒单卡=0.22361111111111112GPUh。
  根 /research/d7/spc/yzyang4/forets-current-pool-20260912-wnm9cxd0；stage forets-current-pool-stage-20260912-awArkuah。
  controller0fd4d1a7e76e06760d01027bfb96b0c5793782b5，task source6ca01fba9892a350cbb24152054b5296dc7095f1。
  plan SHA08ac4d511382e78efb1a1c66e5cd4c4b12c3a92712e632068d9c15fb2f9773d9。
- 原seed11两个critic首池各4原代码全执行含重复；原SIF/6CPU/300秒/RTX3090，0生成/旧critic调用/训练。
  Leaf0/4有效（2错2超时）；Spaceship1/4有效accuracy0.8069，原critic top2未保留它。
- readout与独立原submission数值verifier已各一次成功，同物理GPU、原字节/数值一致。
  不再prepare/submit/readout/verifier，不补失败槽。只读PTY78873已结束，GPU已释放。

## 通用裁判4调用已完成
- 根 /research/d7/spc/yzyang4/forets-context-judge-20260912-42qtmhgi；stage forets-context-judge-stage-20260912-VcfwMAFN。
  controller c62033a3eaf737ed195d9b6e2a7781954ea989c6，forets_context_judge_20260912.py。
- 00:26:35请求固定，00:26:58–00:27:04四调用闭合，00:27:26才生成GPU主汇总；裁判未见执行值/原分/答案。
  Plus/Alibaba、完整代码/任务/资源、温度0/top_p1/8192输出，正逆序、无截断/重试/fallback。PTY50160已结束。
- Space两顺序都保留唯一有效程序：有限池random25%、旧critic0%、通用裁判各50%；Leaf均0。
  两任务top2集合均不具顺序不变性；顺序不等于独立seed，强模型/信息两因素一起改变，更不是e2e收益。
- 合并reader已成功一次，独立映射原响应一致。comparison SHA785df0a492c7b850996915f53132147cde5d12fe257d4a4e8152dc7b39c62f49。
  数值回执SHAe25cf89b77e03d90e8beba26cd75646eace1a14d29ed1afbc1d82b239bd53404。
  10公开文件secret scan0、SCP SHA全匹配；原代码/响应/排名/submission只留远端。
- 当前API账为judge根/paid.sqlite，AUTH69e6d156ea7ec0f172edf3f46f432661c1da8ca0c1249301212ac59bac209fbe。
  新4调用0.02417246USD；累计结算0.742593566、含旧0.70未知责任1.442593566USD。
  185账行=181旧行+4新行，含历史聚合行，行数不是总实际API数。
  13118旧账已stopped封存；后继只能从judge账逐行结转，原100人民币/10USD不重置、未知不释放。
  该窗口已结束，禁止再run/失败补问。

## 正在推进（尚未提交/调用）
- 新seed13真实e2e已写定FORETS_CONTEXT_E2E_PLAN_20260912.md：Flash生成不变，两原任务各random/资源条件化Plus，共4run。
  固定双顺序Borda→原top2/common-priority随机选1，仅用于未来新池，不在旧8代码上找最优规则。
  新增≤5GPUh/3.50USD责任，总责任上限4.942593566USD；全API每run共同≤100次。
  代码forets_contextual_rank、forets_context_e2e_patch、forets_context_e2e_build三个20260912模块；尚未build/activate/提交。
  stage /research/d7/spc/yzyang4/forets-context-e2e-stage-20260912-vzIVzZUQ，19测试和远端24父Python派生语法通过。
  下一步commit→local artifact→scp source.tar/artifact.json→远端build→实际import/配置/留档隔离检查→activate→两次生成路由/Plus公开catalog→submit。
- 已读真正父版13118根/code与seed11公开capsule。本地forets_block_runtime等有旧draft文本，不能直接部署旧本地副本。
  当前ForeTS逐候选HTTP取分；新全池裁判应接在batch_runtime完整生成并freeze_pool后，不能假装旧接口已支持。
- 设计新版本不加载8B服务，API裁判在worker内；1GPU/6CPU同硬件两臂，不伪造CUDA服务marker。
  原launcher max_parallel1、每worker1GPU/6CPU、6step/300秒/3540秒、100API/8192输出。
  新judge费用/时间计入共同预算。考虑前瞻双顺序Borda，不能用旧池重算漂亮结果。
- forets_submission_archive_20260912.py将在此新包两臂共用，原镜像/评分/反馈不变，留档host-only，已测未部署。
- 保护集仍封闭，不更新agent底座，不恢复旧HCE/多保真/Probe/score-channel/K≥1lookahead/旧CPU期限筛查。

## 旧真实结果（勿重跑/改写）
- 13118 seed12：3/4final，Leaf random缺失/critic0.37782但无实际改选；Space0.80805→0.61839，−18.96600pp。
  实际改选仅Space step1/3，独立生成随机性仍存在。
- 13115 seed11：Leaf双方缺失；Space0.74368→0.79655，+5.28700pp但未实际改选。
  无稳定/可归因critic收益或clean scaling；不补零、不重写final。旧数值CSV被原task删，只有外部分/选择一致性。
- 13118根forets-repeat-20260912-zuvnt3oa，source35711518b3b7262bccd3bebfdd2b4a4b7c726715，
  prepared963418d10d5645f7401a85da42d6fc3d5b2f7553e76cf44eecbeb342f17d44d5，
  inventory67516a4d01ddb6093ad405da538add47fbe0f9e64016df1b9b35036d306b9545，
  releasea64e8b24afc538a9446060cf847a5310288a3041ffa6a700b132949340b86bc0。
  旧AUTH0b74ccfd16ae8e5f5bb3d255ee3d5200e133e6016b0ae6128a3c72504164795a已封，closeout/final/selection均已完成。
- 13115根forets-review-20260912-csh5q4i8；公开code capsule保留真实source/许可证，不重新打包私有候选。

## 上传与运行规则
- 0910六包115079888bytes已隔离senior-quarantine-0910-20260912，24配置≠24新run，两个commit/children2及3不可混。
  未读journal/env/code/outcome或正式摄取，不重下载。00:19:25新embedded两次与旧及之前列表50项一致、额外0，
  未见0911/0912，不是全上传索引完成证明。metadata根senior-complete-root-20260912-m6u2vavt，无环境升级。
- repo C:/Research/New/my_project/MLEvolve/aira-dojo-codex-20260813；SSH linux5；BASE /research/d7/spc/yzyang4。
  venvs/aira控制CPU、venvs/exp GPU/gdown；source /uac/y24/yzyang4/env_setup.sh。
  SLURM_CONF=/opt1/slurm/gpu-slurm.conf；MLE用gpu28/27，不是projgpu28/39；镜像不升级、不退CPU。
- key只在远端aira-dojo/.env OPENROUTER_API_KEY→worker PRIMARY_KEY；不回显/本地/Git、不再索要。
- 只push myfork HEAD:phase1-value-critic；最近成功094f8ee5308e39b8271f33124d31482c281e4adf，完整池/通用裁判结果已公开。
  staged文件名+内容扫描，不全add用户untracked codex_tmp/output/tmp/旧报告。
- g0-r5 PAUSED，无新automation；12535 held不碰，不索要gres.conf或使用失修pool恢复。
- 研究盘1TB/2026-09-29到期，续期未知；共享df不是个人quota。
