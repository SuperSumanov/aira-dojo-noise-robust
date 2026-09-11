# 当前交接：ForeTS 同预算端到端探索

更新：2026-09-12香港。动态状态均为注明时刻的最后观察，不能冒充实时。
恢复：fetch → CURRENT_DIRECTION.md最新节 → 本文件 → 核现场。学长指导见ADVISOR_DIRECTIVES.md L/M/N。

## 当前目标与授权

- 科学问题：同预算下，固定现成critic是否改善最终选中解的外部成绩；不是训练/G0或干净scaling。
- 固定8run：leaf-classification / spaceship-titanic × seed8/9 × uniform_random / critic_topk_random。
  两臂共同Qwen3 Coder Flash（OpenRouter / Alibaba）、原SIF、gpu28 RTX3090、6步上限、width4、top2选1、
  common_priority_v1、执行300秒、worker3540秒、每run最多100传输/8192输出；只变选择规则及机械身份路径。
  步数上限含root，不能未经实际计数称每run执行6个程序。历史critic训练模板未知，固定既有部署输入，不途中改。
- 用户2026-09-11批准100人民币生成API总上限，包括检查/失败/重试/正式生成。
  现有唯一paid.sqlite总10USD、每run1.10USD、route共1.20USD；完整上下文每请求预留0.70USD。
  原始usage.cost核销，未知费用保留预留；禁止重建/复制初始化账本、fallback或绕过停机门。
- 原8run共19GPUh封顶，不扩矩阵。第一块实际3135秒双卡=1.7416666666666667GPUh；
  连同第二块280分钟及300秒KillWait最坏合计11.241666666666667GPUh，仍在原批准内。

## 实际进度（不读取第一块成绩后调整第二块）

- 第一块seed8 / 13088：2026-09-11 19:29:53.826635 UTC独立查询COMPLETED/gpu28/0:0，
  allocation实际3135秒；4run均completed、各1attempt。控制器completed，清理issues为空，
  local_srun_exited与remote_step_cleanup_confirmed均true。终态回执19:30:23.122596 UTC。
  pool：runs/srun_pool/74b760b75c87/manifest.json。最终成绩尚未读取。
- 第二块seed9 / 13112：已提交，started时间19:31:50.001290 UTC。
  20:02:42.950856 UTC观察pool：04/05 completed，各1attempt，06 running，07 pending；共6/8run完成。
  pool：runs/srun_pool/b7f9c9287661/manifest.json。
  使用同一源码/模型/镜像/预算；第二块路由2/2 READY，不再检查或重提。
- 20:02:42.950856 UTC现有账本：94次全部结算0.233775672USD，0未结，stopped=false。
  含90真实生成调用及两块4路由检查。这是当时费用，不是最终账单。
- 两块都已提交；禁止重复route、submit、execute或恢复旧campaign。当前在会话监督第二块，
  两块独立终态后统一读取全部8槽位最终结果；失败不删，不取轨迹最大分。

## 唯一活跃根与冻结身份

- /research/d7/spc/yzyang4/forets-paid-20260911-oh3np7b8
- 入口code/forets_native_run_20260911.py；controller commit f051cfded55259d5320407a9e0269ab9141ab345。
- source tree f9087ae47470f7f1868c61405c3b827327f31c2c。
- prepared SHA 58558eed5abe1f793c77049572549c66de8c104255f8a13fa3c48e0a8b4d3593。
- source inventory SHA 6857f18c60fecaa745710960c0f2f9dfd50d485717ca8a7e86faa47dedc10c1b。
- release SHA 819621d75c9c95efe1e337866884b8701ad5f3f71cf5ea7e849f2b6ab0dd8798。
- monetary authorization SHA c274cfc456296b85a8cb2b85ba9f66d28f738132462119e6fbb7f58d6c2e5c1e。
- 我方公开HEAD最新push核实为35d291ec4de0dcf8f66b256db87c5e4e766a78d0；不要将报告commit当执行commit。

## 收尾方式与结论边界

1. 只核作业/控制器/pool结构状态、现有账本；不在第二块完成前看第一块结果。
2. 两块终态后用本根code/forets_block_collect_20260911.py生成独立runtime-manifest，
   再code/forets_block_readout_20260911.py在新目录统一读最终eval.jsonl；本地旧版本绑定旧根，不能混用。
   20:04:52 UTC本会话已启动最多30分钟的只读等待/收尾链，session25007（不是新GPU或自动任务）。
   两块独立终态后生成runtime-manifest-20260912.json、final-readout-20260912/和cost-work-20260912/。
   恢复先查这三处及链是否结束，不能并发/重复写同一读出；超时只退出观察，不取消13112。
3. 独立复核最终selected-node外评分、进程成功、配对方向；leaf用random−critic，spaceship用critic−random。
   按任务报告两seed差值/中位数/样本标准差、有效配对和失败；不混平均原始指标、不声称确认性结论。
4. 只读实际调用/执行次数、打平/剪枝机会及费用补充已准备；6项小测试在本地和Linux通过。
   代码在本根post-closeout-20260912/forets_paid_measurements_20260912.py；只在两块终态后运行。
   不改运行代码、不读取保护集、不加GPU/API。
   候选ledger只作该开发包结束后的计数核算，私有代码/中间critic分不导出；配置步数不是实际执行量。

## 已关闭与不能重做

- G0/12892、critic8B/16K接入、13076原SIF双步骤CUDA/OpenCL隔离已完成。不再索要gres.conf或重验。
  旧设备9误映射adapter已撤回；当前native UUID→minor适配是新验证版本，不能恢复旧副本。
- 13004单开发对照及13085全池诊断负结果保留；不反转分数、事后选k或救跑。
  CPU限时完成筛查25-fit无投资信号已关闭，不重训/部署。详见20260910/11对应报告。
- 免费Nemotron/Laguna失败窗口已关闭；本轮100人民币收费后继已替代阻塞，不能再说缺API授权/密钥。
- first-960/Target-300/Target-522标签、结果、预测及私有选择仍隔离；
  HCE、多保真、Probe、score-channel、K≥1 lookahead不恢复；agent底座不更新。
- 12535 JobHeldUser不释放/取消；g0-r5自动监控已PAUSED，不恢复或新建，当前按用户要求会话内推进。

## 语料与操作

- 新包最后安全检查：senior-quarantine-20260911-v1，manifest SHA
  67ac5406b789fa7a5a39f41e9483a095f671f2d25ba47ccf69af4f98264c7cb4。
  32配置头不等于32合格physical runs，未读env/journal/结果、未并入训练。
  2026-09-11 19:51:45.958128 UTC复查已知0907、0909、0909/mcts网盘目录，三者列表均无变化；未扫描其他新目录。
- LATEST最后759总physical / 733 eligible，closure=false；本轮未重新计数。
  SHA 1b44e898bbae7ffc9098bbfa584ba842e0db2be5ae6bb8b5da0475d8ab34239f。
- repo C:/Research/New/my_project/MLEvolve/aira-dojo-codex-20260813；只push myfork HEAD:phase1-value-critic。
  学长dojo-reproduce最后fetch 065b0fbaa89e0eb663f2834ec768081f5d56394d，不改学长分支。
- SSH linux5；网络先source /uac/y24/yzyang4/env_setup.sh；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
  CPU Python=/research/d7/spc/yzyang4/venvs/aira/bin/python，模型同根venvs/exp/bin/python。
  复杂SSH用脚本/scp。归档只取src/aira_core src/dojo，core.autocrlf=false；禁止整树archive触发无关大LFS。
- 凭据仅远端.env OPENROUTER_API_KEY→worker PRIMARY_KEY，绝不写本地/Git/输出，不再索取。
  新outcome先credential-shape scan；push前扫描明确暂存名单及完整内容。
- 不升级任务Torch/SIF、不静默CPU回退；MLE用gpu28，不是projgpu28/39；两臂同硬件。
  QOS4jobs/8GPU；排除projgpu7/8/33、gpu36/38；保留用户未跟踪codex_tmp/output/tmp等。
- 官方研究盘1TB，/research/d7/spc/yzyang4，到期2026-09-29，续期未知。
- 旧交接全文留Git5cbf2a6a；详细失败/撤回留dated报告，不把无变化轮询重新堆入交接。
