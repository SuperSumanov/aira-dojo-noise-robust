# 当前会话交接：ForeTS 同预算端到端探索

记录更新：2026-09-10（香港）。这是恢复索引，不是新的实验结果。
最近一次作业观察：**2026-09-10 06:33:39 UTC / 2026-09-10 14:33:39 香港**。
**12977已在gpu28运行。** 原SIF的CUDA前向/反向、critic单3090/16K/全参数CUDA-BF16均已通过。
critic同次加载后供搜索。首个随机run在draft阶段APIError失败，第二个critic run运行且已有4个成功接口响应；
其余待执行，无完成run或最终成绩。不是CUDA失败；错误具体HTTP原因未知，不换生成器或重跑有利seed。
12933因PRO6000/任务镜像不兼容在排队时取消；12974启动失败，保留；12973只是test-only预检号。
用户明确指定gpu27/gpu28可跑MLE。原镜像、8run与270分钟不变，不升级Torch、不CPU卸载、不跨节点服务。
新唯一运行根 `/research/d7/spc/yzyang4/forets-e2e-3090-20260910-j6zb6d6i/package-r2`。

## 恢复先读与权威顺序

1. fetch Git；读 [CURRENT_DIRECTION.md](CURRENT_DIRECTION.md) 顶部最新裁决及最新用户指示。
2. 本文件只给当前作业、关键边界和下一步；按需读 [实验矩阵/入口](FORETS_E2E_CAMPAIGN_20260910.md)。
3. 设计与结论前对照 [学长建议](ADVISOR_DIRECTIVES.md) 最新日期段。旧反馈中的临时阻塞不能覆盖较新事实。
4. 当前科学主线是 **同预算下 critic 是否改善最终选中解的外部成绩**；corpus/predictor/audit 为支撑。
5. 不根据旧摘要恢复 HCE、多保真、Probe、score-channel 或 K≥1 lookahead。

## 已完成，不要重做

- 12892 已完成真实单GPU/8B/16K/本机HTTP验收，仅证明模型能接入，不证明排序或收益。
- OpenRouter 平台、地址、模型已经确认；凭据已经按用户明确授权安装在远端，别再问同一问题。
- 两次公开人工输入端点检查：第一次失败已保留，第二次成功；不是 task run，也不是长期服务稳定性证明。
- 8-run 包曾提交12933，后因任务镜像兼容性遗漏在PENDING时取消；不能当作已执行或可直接重投的包。
- 不要重复 G0、下载、projgpu39 critic验收或端点检查填时间；缺的是任务镜像在目标GPU的实际兼容性。
- 尚无新的 critic 收益、干净 scaling 或 e2e 正效果结论。学长旧 scaling 是探索信号，不是本轮发现。

## 当前作业与历史尝试

- 当前实际job：**12977**，入口commit `60bad03096b3340d4fea8dc221f142c965369995`；
  香港14:25:24启动gpu28、2×RTX3090/12CPU、270分钟/no-requeue；正常时限18:55:24，清理可能延迟。
  证据：[submission12977.json](results/forets_3090_20260910/submission12977.json)、
  [容器实测](results/forets_3090_20260910/container.compatibility.json)、[初始状态](results/forets_3090_20260910/deployment.initial-state.json)。
- 原SIF Torch2.5.1+cu124/CUDA12.4，3090能力8.6，CUDA矩阵前向/反向通过；无数据/生成器调用，不等于MLE整轮成功。
- critic16K一次前向通过，peak reserved18.80078125GiB，无CPU卸载；
  [实际搜索启动状态](results/forets_3090_20260910/deployment.search-started.json)含完整8run状态与sacct。
- 12974于香港14:22:06分配后立即FAILED/Elapsed0，无Python产物、日志为空。
  CPU复现并修复缺LD_LIBRARY_PATH导致bash -u初始化退出；原变量未捕获，不宣称原rc的根因完整实证。
  新batch日志含FORETS_BATCH_ENTERED与FORETS_ENV_READY，两阶段已到达。原入口/包不覆盖。

- 更早job：**12933**；2026-09-09 18:14:51 UTC提交，2026-09-10 06:09:40 UTC取消；
  独立sacct确认CANCELLED by 7542、Elapsed=0，无started/runtime/运行日志；没有实际执行或生成器请求。
  [取消证据](results/forets_e2e_20260910/cancellation.json)。取消前核对唯一作业身份/路径及PENDING状态。
- projgpu39 / gpu_24h，2GPU、12CPU、270分钟、no-requeue；名义9.0 GPUh，
  加已观测300秒KillWait为9.166666666666666 GPUh；这是原预算，作业未启动，不是已消耗资源。
- 原香港2026-09-10 19:59:12启动预估已作废。sacct的Start=End=取消时刻不代表实际启动。
- 12932 是 test-only 编号，不是本轮作业。旧12535保持held；不释放、不干预他人12901。
- 12933旧代码根：`/research/d7/spc/yzyang4/forets-e2e-package-20260910-SWMoh2`，旧包`package-c`，不得重投。
- 12933旧入口commit：`8366208fb7e6329627dce90173d0e9583f1200c1`。
- source-v5 tree：`2ff5277ba17327c6c03326a018b59f704402af6b`。
- 提交证据已发布 commit：`684e1c6c4c5ce35ff8e2ecfb6eebdddbb75f9df7`，当时 push/fetch HEAD 一致。
  这不是永久的“最新HEAD”；恢复时以 fetch 为准。
- 安全回执：[submission.json](results/forets_e2e_20260910/submission.json)、
  [initial-state.json](results/forets_e2e_20260910/initial-state.json)、
  [route-readiness.public.json](results/forets_e2e_20260910/route-readiness.public.json)。
  精确入口文件hash在submission中，不在摘要重复维护。
- g0-r5 已暂停，未新建自动任务。不能声称离开会话后有新监控在运行。

## 固定矩阵与结论边界

- leaf-classification、spaceship-titanic × seed6/7 × uniform_random/critic_topk_random，共8run/4对。
- 相同免费 Nemotron：`nvidia/nemotron-3-ultra-550b-a55b:free`，无付费或模型fallback。
- 只改selector，另允许机械run身份/派生路径不同；候选规则、生成器、任务、预算固定。
- 4步、num_children=4、critic top-2再选1；skip_redundant_critic仍false。
- 单次执行300秒；worker1740秒、Slurm step30分钟；每run40次请求，单请求8192输出token/120秒。
- 实验最多320次生成请求；另有已经发生的2次公开端点检查。成本未知写null，不以报价0代替实际账单。
- 现成旧8B critic，不是RL胜出模型或新训练结果；为真实搜索只加载一次。
- 读最终选中解的外部分数，不读最后一次grading_report、不取全轨迹最高外部分、不拿自报分替代。
- leaf越低越好，spaceship越高越好；逐任务配对，不混合两种原始指标。
- 完整保留全部8run，包括失败、未开始和缺分，不填0、不挑有利seed、不看到结果后换模型。
- 两任务四对仅探索；API并不因同seed就确定性。小样本好消息也不能写成稳定确认收益。

## 中断后下一步

1. 只核12977与package-r2；先squeue/sacct，再看critic.ready/campaign.finished/runtime-manifest与runs/srun_pool。
2. 容器计算和critic16K检查已通过，不重复。当前直接跟进实际MLE worker的运行/失败/最终成绩。
3. 旧12933/12974/12973不是当前运行对象。新submission.claim防重复，不因没有finished盲目重投。
4. 运行日志先脱敏；不读保护集、不重跑端点、不加新臂/模型/任务/seed。故障先定位，保留全部8run。
5. 仍保持原镜像和同3090硬件；不能CPU卸载、升级Torch或临时跨节点绕过失败。
6. 作业终态后按 [读出定义](FORETS_E2E_READOUT_20260909.md) 核真实结果/失败/成本；完成率与分差分开报告。

候选后续方案见 [信息负对照与相关工作](FORETS_INFORMATION_CONTROL_AND_RELATED_WORK_20260910.md)：
新seed块比较随机/真实critic/置换分数，区分学习信息与完整策略净收益。仅设计、未实现/提交/新增预算，
当前先修部署，不借取消增加实验臂。现成RM引导agent已有AgentRM等先例；不是全面查重通过。

辅助选择机制诊断已准备，见 [说明](FORETS_SELECTION_DIAGNOSTIC_20260910.md)。本地12项人工测试、远端真实账本
写入器6项人工记录检查通过，不再重跑；尚未读取真实候选，不是模型收益。独立部署目录
`/research/d7/spc/yzyang4/forets-selection-diagnostic-20260910-6uwXNX`，未改12933入口。
旧诊断绑定12933/旧包，不能直接套到12977；实际产物就绪后先显式更新部署身份，不绕过门。
未来仍需独立核实终态；全打平槽位变化不当成区分力，同池重放不当最终分。

## 远端操作与安全速查

- 本地repo：`C:/Research/New/my_project/MLEvolve/aira-dojo-codex-20260813`；
  工作分支 `codex-prospective-decision-v1-20260814`；只发布 `myfork/phase1-value-critic`。
- 学长分支 `myfork/dojo-reproduce` 最近核实 `065b0fbaa89e0eb663f2834ec768081f5d56394d`。
  不改/推学长分支，不改生产代码；本次凭据安装是明确授权的特定例外，不是生产通用修改授权。
- SSH alias `linux5`；SLURM_CONF必须为 `/opt1/slurm/gpu-slurm.conf`。
- 非交互代理初始化 `/uac/y24/yzyang4/env_setup.sh`，抑制输出；之后重新设SLURM_CONF。
- CPU Python `/research/d7/spc/yzyang4/venvs/aira/bin/python`；GPU Python 同根 `venvs/exp/bin/python`。
- 密钥仅远端 `/research/d7/spc/yzyang4/aira-dojo/.env` 的 `OPENROUTER_API_KEY`，0600、未被Git跟踪；
  原PRIMARY_KEY保留，运行时仅在worker进程环境映射。**不存值、不回显、不读整份.env、不提交余额**。
- 学长新outcome/压缩包先credential-shape扫描，必要时远端流式脱敏后读取。
- first-960/Target-300/Target-522标签、结果、预测及私有选择仍隔离；不微调/RL更新agent底座。
- QOS4jobs/8GPU；排除projgpu7/8/33、gpu36/38；复杂SSH逻辑用脚本/scp，避免引号损坏。
- 每个新长实验先给矩阵/总runs/GPUh/ETA并遵守已有授权；既定12933不重复索批。
- push前只stage指定文件，扫描staged文件名及完整内容；数字标题只能用已核实程序输出。
- 保留现有未跟踪codex_tmp/output/tmp等，不能整目录stage或随手清理。
- 官方研究盘1TB，路径 `/research/d7/spc/yzyang4`，已知项目到期日2026-09-29；不推断已续期。

## 记录习惯（2026-09-10用户要求）

每次方向/授权变化、真实提交、开跑/完成/失败、关键修复、有效结果、交接/长等待前，及时落最小记录。
顺序：**事实和观察时间 → 证据/路径/commit → 可下与不可下的结论 → 下一步及禁止重做事项**。
长期规则保存在项目AGENTS；即时状态覆盖本短文件；详细历史留dated报告/CURRENT_DIRECTION与Git。
不把每次无变化轮询写成新成果，不把短入口重新堆成整段聊天，也不以记录代替真实实验。

旧869行交接没有丢失：见Git提交 `684e1c6c4c5ce35ff8e2ecfb6eebdddbb75f9df7` 的同一路径；
旧的“缺凭据/待验收/尚未提交/旧监控活跃”均不得当作当前事实。
