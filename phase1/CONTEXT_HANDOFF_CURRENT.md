# 短交接：定向内核排障；e2e已闭合，本地生成器待共享访问

2026-09-12 12:39 UTC更新；恢复先fetch→CURRENT_DIRECTION顶部0L183→本文件→核现场。
最新用户：继续工作，并转达学长后续多数run用本地qwen3.8 27B AWQ INT4、旧API数据继续利用。
不得重跑13156、首次读出或已闭合生成池；不得重复G0/旧模型验收。

## 当前一小时推进

- 用户12:13 UTC要求一小时内推进实质工作。根因定位与已揭盲机制分析；不追加同配方paid seed。
- 13161单卡gpu28诊断已COMPLETED/114秒，root /research/d7/spc/yzyang4/forets-kernel-wire-20260912-joepk5ej。
  commit316667d0e5bbac31f7d286c3f847c966170de4f6；32次fresh gateway均ready/marker，但通道trace仅loaded。
  generic jupyter CLI换进程导致hook丢失；不能算有效通道诊断或故障修复，原回执保留。
  修正独立诊断入口后13164 COMPLETED/101秒，32次均ready/marker且真incoming/reply可见，仍未复现，不扩循环。
  修正版root /research/d7/spc/yzyang4/forets-kernel-wire-20260912-qSZRVKYS，commit c22250b39ea94eef3ee5addab9e74db3e6963eef。
  result SHA 0b2b236e2623546116674d2b2553439b167fbdc6cf1a401c56c9ee90488ac6a7。不是根因修复或e2e验收。
  两次原ZMQ non-socket发生在握手超时和开始清理之后，不能说是失败原因。旧12次测试只复用一个gateway。
- 旧并发e2e和本地模型状态见下；队列动态以重新检查为准。
- 12:39:15单次提交13165：补齐13156全部四个critic首池中未尝试的12个程序，不重跑旧选中项（含握手失败）。
  root /research/d7/spc/yzyang4/forets-pool-completion-20260912-2u45zbx4
  source e07cb8c61bca347c61bb8253c84eda826b1add6a，controller7b706ab1c69469b4c6c31bdd52161c441466476c
  prepared959590741963d55dc60d53d45b604bd5e0344fb31b221e0a2d2deb34812d4d16。
  gpu28单3090/6CPU，原镜像，300秒程序/120秒握手，最多90分钟allocation，0API；首infra错误停止、不重试。
  四项本地隔离/无重复/旧执行默认值测试和实际生产导入通过；不拿这些称模型结果。
  当时冻结的排名不变、全12闭合后独立数值复验；新reader尚在准备，不运行旧readout。
  原Space25选中项仍unknown，不能补0/冒充完整池。是开发机制分析，不是新e2e/干净scaling。

## 本轮真实结果

- 13156全8闭合，Slurm FAILED/4009秒/gpu28，实际1.113611111111111GPUh。
  600秒科学截止/程序300秒/原Flash生成+Plus裁判/单3090/6CPU/seed24,25，两臂共同最多4路生成在途。
  5份合格原submission独立数值复验一致；技术合格6/8。
- Leaf24：random缺终点，critic logloss .47866；Leaf25：random握手故障，critic .71343。
  Space24：random accuracy .81839，critic .80230（−.01609）；Space25：random .75402、critic握手故障。
  全8有效random2/4、critic3/4；不称稳定正效果/干净scaling，不追加同配方追显著。
  条件统计、所有缺失和局部有效性信号见FORETS_PARALLEL_RESULTS_20260912.md。
- 51次内嵌握手中两次失败，均120请求、0匹配reply/idle、仅3条无关parent消息。
  不是只缺idle；kernel/server/WebSocket根因仍未知。不能靠放宽成功条件、重试或合成测试称解决。
  两条random cutoff中尚有未闭合task调用，时间归因余量包含它，不能全算critic/生成。
- 8搜索API .547526252USD（排名 .178036040USD）；累计账658条、结算2.200861988USD、
  责任3.600861988USD、仍两条历史未知，新8无新增未知。账路径不变、未清零。
  客户端129计时覆盖非排名请求，另23排名无此计时；不能相加并发时长或声称服务端加速。

## 完成位置与恢复事实

- ROOT /research/d7/spc/yzyang4/forets-wallclock-20260912-cxb9p0og
  原STAGE /research/d7/spc/yzyang4/forets-parallel-stage-20260912-ykh87_no
  source e07cb8c61bca347c61bb8253c84eda826b1add6a
  producer/controller 8df9858fa6f746e598b6fe56527d081fe51383aa
  prepared 96e624e811e8152627e93bcb8976cb2ae9218f5f15361901178f08dd19d6b077
- PID4016707早已退出。自动收尾08:38:53遇SlurmDB连接超时，closeout-finished.json失败且readout_called=false。
  原失败记录保留，不把它改成成功。核全终态/8槽无running/四固定SHA/无原readout intent后，原固定reader首次调用通过。
  recovery-readout-finished.json verified于11:55:43；recovery-attribution-finished与diagnostics-finished于12:00完成。
  新补充工具只在ROOT/recovery-tools；原stage四文件未改。不可再次调用已有输出的一次性读出/归因。
- 本地结果目录phase1/results/forets_parallel_s24_s25_20260912，已下载完整CSV/summary/原失败及恢复回执/归因/安全计数。
  summary SHA a127831408688b545e3d666b790fe1f75b65e82f9324d21c8c4cfc0243d39e90
  CSV SHA b535b6a439cefdcb29ada9d5ef26baeb3e8b0793f90bca0fa31c5c79bda37f81
  attribution SHA 3a144d4db72f5889cefee2704a689a1198e99426d7d4d89669a891919a99154c
  diagnostics SHA c1bb304c8d1ffa4be487100bf14c75d67eb93eef63984ec8235e79c0e0b79a36
- 旧13152也全闭合：Space22单对+.03218但Space23 critic缺失，不能只引正例；旧结果不重跑。
  已公开24开发程序包和四盲池结果继续保留，不能改为新的冻结评测。

## 学长最新安排与可继续工作

- 新head113e25e7fa2570cb5f60401d051a1de3cce307c2已fetch，只读且credential-first远端脱敏。
  新本地模型YAML/部署文档；0911 outcome这次仅变链接，不是新scaling结果。
  模型served名qwen3.8-27b，双卡cyankiwi/Qwen3.8-27B-AWQ-BF16-INT4，单卡AWQ-INT4不同来源。
  文档3处凭据形状命中，绝不回显/复制/使用。ADVISOR_DIRECTIVES O节记录新反馈。
- 文档镜像、两份权重snapshot目录对我方PermissionError，未绕过权限。
  http://127.0.0.1:8000/v1只在计算节点本地；已异步询问可读共享路径或共用服务安排，不再问密钥。
  不擅自占用学长allocation、修改他server、下载大模型或升级MLE镜像。
- 长draft文档约12分钟，不能直接套当前600秒搜索/120秒API上限；命令上下文131072与表格262144也不一致。
  下一份新对照先按真实可用配置/延迟定共同预算，全算子同模型，服务GPU/初始化/缓存负载计账。
  历史API训练/开发数据继续利用，新本地run可检验跨生成器转移；不是直接合并成干净scaling。
- 已准备本地认证保护补丁与不联网构造器测试，尚未部署；模型专用凭据缺失停止，不回退全局PRIMARY_KEY。
  4项本地认证、29项截止/读出/归因、6项并发测试分别通过；不是模型效果或实际本地服务验收。
  详细见LOCAL_GENERATOR_TRANSITION_20260912.md。没有新GPU/API/model-fit；12:07:26 UTC队列仅旧held12535。
  可继续定位内核无回复根因，但不再重复无指向的短验收/同配方扩seed。

## 操作硬边界

SSH linux5；BASE /research/d7/spc/yzyang4；venvs/aira/bin/python；
网络需source /uac/y24/yzyang4/env_setup.sh（不回显），Slurm /opt1/slurm/gpu-slurm.conf。
复杂远端命令Python stdin，避免PowerShell→bash CRLF/SSH内引号坑。gpu28不是projgpu28；
原MLE镜像不得投projgpu39、不升级Torch/CPU回退、不传--mem8G（Slurm登记内存不可信）。
现有OpenRouter凭据仅远端aira-dojo/.env的OPENROUTER_API_KEY，运行PRIMARY_KEY；本地模型必须专用凭据。
first-960/Target-300/Target-522仍封闭；不恢复HCE/多保真/Probe/score-channel/K≥1 lookahead，不更新agent底座。
旧held12535不碰，g0-r5 PAUSED，无新增automation。1TB研究盘2026-09-29到期，续期未知。
只正常push myfork HEAD:phase1-value-critic，先内容/文件名凭据检查，核remote SHA；绝不改学长分支。
保留无关untracked codex_tmp/、output/、tmp/、旧tests.xml与2026-09-01实验记录。
