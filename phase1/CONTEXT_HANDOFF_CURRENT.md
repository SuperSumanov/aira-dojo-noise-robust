# 当前交接：seed11观测差尚非critic收益；seed12的13118正在运行

更新2026-09-12香港；13118最后现场观察2026-09-11 23:16:38.137831 UTC。
恢复：fetch→CURRENT_DIRECTION.md最新0L165→本文件→核现场。学长指导ADVISOR_DIRECTIVES.md L/M/N。
用户要会话内实质推进，不新增自动任务；不把旧队列、计划、mock或进程完成冒充当前结果。

## 当前闭合事实与接续（优先于下文运行期观察）

- **13115 COMPLETED/gpu28**，4564秒双卡=2.5355555555555553GPUh，PTY19866已正常结束并自动完成primary closeout。
- 独立验证已实际执行，根下independent-final-verification.json；不是数值重评分，禁止重复写入。
- 2/4有效最终解、1/2可比对；Spaceship random0.74368、critic0.79655，差5.28700pp；Leaf两臂无有效final。
  这是第一条单seed探索信号，不是跨seed稳定收益或clean scaling；详见FORETS_REVIEW_CLOSEOUT_20260912.md。
  **23:09补充限定**：12池选择重放通过，但Spaceship全池均与同池随机规则选择相同；实际改选仅Leaf step3。
  因此不能将Spaceship的差值归因为critic选择，应优先称“观测差”；新生成随机性未排除。结果数值不撤改。
  independent-selection-verification.json已生成；不要重复写入。初次检查器误假设池恒4而失败，已按4/3/1实际规则修正。
- 新增62API/0.152156823USD；累计240API、0.574500927USD已结算，旧0.70未知仍保留，总责任1.274500927USD。
- 收尾JSON/CSV已复制到results/forets_review_20260912，远端扫描0凭据命中、本地SHA逐项匹配。
- seed12两任务四run同配方包已构建、STATIC_READY、账本已激活、route两次通过，**已提交13118**。
  提交2026-09-11 23:05:37.194035 UTC，gpu28；23:07:25 UTC已RUNNING、首个leaf/random worker运行。
  当前会话watch PTY **34987**，整块终态后自动primary closeout；禁止启动第二收尾写入者。
  旧账117rows逐字复制并封存；新账本为唯一活动账本。两route已结算，累计242实际API/0.574654587USD，仍1旧unknown。
  初始串行启动末行因Windows回车被解析为submit\\r，发生在argparse且未提交；只补执行submit一次。
  submit-intent/submission/route均已存在；禁止重复activate/route/submit。不是重新开API窗口。
  根/research/d7/spc/yzyang4/forets-repeat-20260912-zuvnt3oa，stage/research/d7/spc/yzyang4/forets-repeat-stage-20260912-qtUUmjQE。
  controller aa4f13c2cc480f7ead84b1970b3511c5b6dd6a30；source35711518b3b7262bccd3bebfdd2b4a4b7c726715。
  prepared963418d10d5645f7401a85da42d6fc3d5b2f7553e76cf44eecbeb342f17d44d5；
  inventory67516a4d01ddb6093ad405da538add47fbe0f9e64016df1b9b35036d306b9545；
  releasea64e8b24afc538a9446060cf847a5310288a3041ffa6a700b132949340b86bc0；
  AUTH0b74ccfd16ae8e5f5bb3d255ee3d5200e133e6016b0ae6128a3c72504164795a。
  269源码/控制/配置/启动文件扫描0命中；Python全部parse；四配置逐一证明只有seed/机械身份变化。
  后继入口forets_repeat_build_20260912.py；本地artifact codex_tmp/forets-repeat-artifact-20260912；不要重复build。
  新预算/源码接线6测试、真实controller/readout/route派生2测试通过；不运行Plus或被动submission留档新路径。
- 父账事实已冻结stage/seed12-parent-facts.json：117rows、ledger SHA190dc0f754f6aa4acd0d7e5f147701dc4b966a10320a93f0a5f3d6cc88043e59。
  facts模式已消费该输出，不覆盖。计划新增责任2USD/最多10GPUh，累计上限3.274500927USD；旧unknown完整保留。

## 当前收尾接口与已关闭证据

- 当前会话watch PTY34987；13118整块终态后自动primary closeout，不启动第二写入者。
- 最后现场：13118 RUNNING/gpu28，首个leaf/random运行，其余pending。本块8API、累计248，
  累计已结算0.587169648USD、1历史unknown、stopped=false；不是实时余额承诺。
- 13118结束后运行新stage/verify_forets_repeat_final_20260912.py一次（尚未执行）。
  wrapper SHA2853f59cf205fbe0ff942a2c336cb73c6f6ba7e3c513be43ce7890854d0305f8；
  同stage helper verify_forets_review_final_20260912.py SHA13ef06dc5ceabe22eaecd7682b428ae357f60cfe504c26ff2f35e377ed3dd114。
  先等watch收尾；这仍是选中节点与外部grade一致性，不是数值重评分。
- 13115根/research/d7/spc/yzyang4/forets-review-20260912-csh5q4i8；controller a383c2abb5fa9def7e85e7b3313c3894159e7be3，
  source6ca01fba9892a350cbb24152054b5296dc7095f1。PTY19866已结束，primary和两独立回执已存在，不重收尾。
- 13115完整收尾见FORETS_REVIEW_CLOSEOUT_20260912.md，必须带上Spaceship“未实际改选”的最新限定。
  实际池宽4/3/1，critic4可剪枝池中3边界严格、只有Leaf step3改变选择。12池均按规则执行。
  生成温度0.6/top_p0.95；存在池内重复代码，不是零温度，也不是旧语料整体冗余判断。
- 13115新增62API/0.152156823USD；总20执行、3exit0、8次超时。四run60线上调用无旧ValidationError，另2route。
  修复的是analyzer接纳故障，不是新方法。原task删submission.csv，因此没有独立数值重评分。
- 实际源代码capsule已公开phase1/releases/forets-review-20260912：276文件、334064bytes，
  SHA2a33f870ac88b1bf2a2902d7bde7900a18aba8b1c61feb737761bbeb3d3d1f3b；234source逐字节匹配Git。
  tree不随公开branch可达，实际代码看capsule；根LICENSE/THIRD_PARTY_LICENSES匹配原tree，分发时一起携带。
- 后继裁决见FORETS_POST_REPAIR_DECISION_20260912.md和FORETS_RESULT_INTERPRETATION_20260912.md。
  Plus只核公开价格与静态预算，未调用；最坏请求责任2.517372USD，不能沿用Flash的0.70预留。
  top1、完整候选池诊断、submission留档helper均未部署/启动。当前seed12不因中途观察而改变。

## 不重做、边界和外部状态

- 13113 seed10已闭合：0/4final、14执行2exit0、1.0733333333333333GPUh；analyzer字符串metric接纳故障及0.70未知来源。
  报告FORETS_ENVIRONMENT_CLOSEOUT_20260912.md。三次2call人工诊断结束；旧账已逐代封存，不重分析旧run补成绩。
- 13088/13112旧8run全无final，124API/0.318775548USD、3.2583333333333333GPUh；
  13004/13085和旧CPU期限筛查负结果保留，不再G0/12892/13076或免费窗口。
- first-960/Target-300/522仍封闭；不恢复HCE/多保真/Probe/score-channel/K>=1lookahead，不更新agent底座。
- 学长branch未改。最后head：dojo-reproduce065b0fbaa89e0eb663f2834ec768081f5d56394d，
  collect4029f62688b28f2bb979b5dc18a500cc6d669a79。22:46:42 UTC仅0907/0909/0909-mcts清单无变，
  未检查所有目录，不能说全盘无新语料。quarantine32配置≠32runs；LATEST最后759physical/733eligible、closure=false。
- 只push myfork HEAD:phase1-value-critic；最后公开核对aa4f13c2cc480f7ead84b1970b3511c5b6dd6a30，后续修改待push。
  每push扫内容与env/key/token/secret文件名；不把用户untracked codex_tmp/output/tmp/旧报告全add。
- repo C:/Research/New/my_project/MLEvolve/aira-dojo-codex-20260813；SSH linux5；venvs/aira CPU控制，venvs/exp GPU/gdown。
  网络/uac/y24/yzyang4/env_setup.sh；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。gpu28不是projgpu28/39，原MLE镜像不投39。
- 凭据仅远端aira-dojo/.env OPENROUTER_API_KEY→worker PRIMARY_KEY；不本地/Git/回显，不再索要。
- g0-r5 PAUSED，无新automation；12535 JobHeldUser不碰；不索要gres.conf，不使用失修pool恢复或猜设备9。
- 研究盘1TB、2026-09-29到期，续期未知。记录轻量，不能替代实际实验。
