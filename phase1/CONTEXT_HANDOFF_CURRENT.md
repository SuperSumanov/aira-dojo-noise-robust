# 当前短交接
更新：2026-10-07 06:01香港。R14继续；用户本轮睡眠六小时，开始约05:22香港，目标11:22。下述16624预算已闭合；本轮尚无新GPU提交/候选执行/API/模型训练。

## 10/7最新状态（覆盖下方10/6历史现场）
- 已fetch；HEAD及myfork/phase1-value-critic仍4790620cd91ec41819cf2a3c6dad01869ce08b4f，dojo-reproduce仍dfff0efb9daf1d4a63c74492f138c19c1fd8440e；学长调研仓库HEAD仍d82dcd845e30e9771750510028d38a6d1d979c43。没改学长分支。
- SSH正常；05:26队列只有旧12535 PENDING(JobHeldUser)，不操作。05:44 gpu27混合占用、gpu28 CPU全占；不是未来可用保证。Slurm RealMemory=1的配置异常不能当物理RAM或据此盲交正常--mem请求。研究盘授权4TB至2027-08-30，不是剩余配额。
- 已提出限定批次请求，**尚无回复**：6固定开发程序、至少2任务含真GPU计算，单执行/双并发×3原样重复=36次，1×3090最多90分钟，含资格/失败总上限1.5GPUh；无API/底座训练。不拿一般继续授权替代逐批批准，不延长16624。真实清单/依赖/隔离也尚未过门。
- 用原sample/trace pins只读检查并作AST白名单算式验证，候选执行0。158程序中5有mem_get_info，4个相关程序确认数值响应：Tweet低于8GiB batch32→16；Herbarium4/8GiB→48/64，PowerShell独立一致；未测真实共置或分数。DetShare/Pollux已覆盖资源耦合宽概念，仍是R14等价性检查，不改主线/不重开R13。
- 16370控制器为9波×2worker/波间barrier，与2执行卡相同；没有第三个已就绪候选证据。345 ready=321 result+19拒绝+5缺回执（非有效评分）；LLM ready136/result113、已记exec1509.2269575512037秒、返回gen4642.254533703439秒。旧22.72%窗口不能推出可兑现节省。证据sandbox_scheduling/qualification_notes_20261007.json；不读评分。
- 合法回放资格还不足：旧Petfinder四程序结果只读复核，唯一rc0是CPU LightGBM；另三神经程序是接口/文件错误，不当新失败，不修代码冒充原样调度。Tweet/Quest所需预训练依赖在四个定向缓存位置未找到，不等于所有位置/镜像都不存在；未下载。继续检查固定公开样本中无需外部权重的原程序。
- 后续补查cache/hf[/hub]、cache/huggingface[/hub]仍无对应模型目录。静态初筛4个无外部权重torch程序实际是用torch检测CUDA的XGBoost，不是神经网络；Dec2021另有2个CatBoost、数据文件元数据已在mle-bench-data/prepared/public定位，但尚非新dev split、未读数据行/执行/冻结清单。不是CPU-only结论。后续live A0/A1须相同rolling补位，不能只赢旧波间barrier。
- 最近一次包版本/fit接口核查因SSH连接超时没有执行回执；06:01有界重试也在banner exchange超时，当前远端不可达（最后观察），不据此重复作业。GitHub fetch成功；网络恢复后再核，不能说GPU正在跑。
- 兜底一次性跟进已复用automation，ACTIVE，FREQ=DAILY;BYHOUR=11;BYMINUTE=22;BYSECOND=0;COUNT=1；工具与本地配置已核。不是后台实验，不越过待批预算，不声称六小时已完成。g0-r5仍暂停未动。若用户暂停，服从新要求。
- 当前改动仅我方短文档与只读检查JSON，尚未提交/推送；后续发布须再核所有hash及secret scan。下方16:36/旧状态均是10/6历史，不当实时事实。

## 当前优先级与已做
- 重要纠正：完整调用链确认INTERPRETER_MAP使用JupyterInterpreterFactory，MLEBenchTask.step_task在factory模式主动close；旧16370也在finally关闭解释器。不能把底层run()保留kernel说成默认生产泄漏。真正待测机会是run级GPU槽位贯穿生成期保留。
- 限定批次根/research/d7/spc/yzyang4/scheduling-lifecycle-20261006-v1；16624单gpu27，同原镜像/64MiB张量、seed130601；keep_10s/close_now各3。plan SHAcbece7bc34c10a99e9d65e39ccbb3623d20d047894b94616fa35052e434cda86；脚本SHAcdcfbed92ef58f42cd95a13b5cfa21092beeec193a62af5e393ddc1ed1515101。实际0.04416666666666667GPUh；未重试，源运行文件未改。
- 六次fixture SHA全同；keep窗口额外372MiB（3次一致）vsclose窗口0；最终6次都恢复4MiB基线且无GPU client。立即close到观察无client中位1.2214048644527793秒，含teardown/query的上界。首条冷启动保留，窗口10/9样本不作等时AUC；不是生产泄漏、需求预测或调度收益。Python与独立PowerShell复算一致；sandbox_scheduling/lifecycle_readout_v1；源回执SHA0943cc3889d940aca5261090952075aa7320b87b8ac77001805ec77f1dc7c724。
- 已发布的16370 mechanism-cost二次时间分析：12条LLM续跑、2任务，返回生成调用4642.254533703439秒=77.37090889505731 task-slot分钟；总时长可用9条的生成比例中位0.7335919914285632，另3条缺失不补。独立PowerShell复算一致。证据sandbox_scheduling/closed_timing_v1；不是实测GPU空闲率、可省时间或全池收益，生成服务另占2GPU。
- 又用native+sacct独立核全部12条：返回生成/实际step分配时长中位0.6296993658295438（含启动清理，另一个实测分母）；Pizza/Spooky各6条中位0.7302769590187579/0.6003422932016333。18 worker各1GPU与2GPU生成服务隔离；全池4GPU×5107秒=5.674444444444444GPUh，上述窗口占全池0.2272495855543097。allocation_audit.json SHA0c0930bdcf0defe89a9603d050366637addcfa61a0907ca9a60a7dc0d155241c；复算一致，CANCELLED不自动标程序失败。
- 16370生成服务只解析聚合计数，log SHA5a9fd51078e02cc8b0496d5ce8efdc58c74a97c8d03c79a1fc55f0acc7584182、scan0；354条统计中Running至多2/Waiting均0/KV最高2.9%。这些不是全时间等间隔遥测，KV也不是计算占用，不能断言生成GPU空闲或增加并发必然获益；未导出原始日志/提示词。
- 固定公开样本AST资源语法盘点：40任务80父子对158去重程序，0解析失败；30对资源设置清单变化、13对提示flags变化，112含cuda availability条件，31有CPU数量查询，7有all_cpu字面旋钮。证据sandbox_scheduling/census_summary.json；不等同动态需求变化/峰值或生产分布，不执行程序不读评分。
- 最低强参照必须新增“仅执行阶段借还整卡”再比较固定共享、廉价准入、语义。若简单解除run级绑卡已解释收益，不硬做LLM调度。
- 已只读取学长autoresearch_project@d82dcd845e30e9771750510028d38a6d1d979c43（10/6 12:19香港）shared_sandbox三篇及proposal，scan0。修正版是未知生成程序、忙碌池、难获隔离profile下的语义/经验辅助准入，而不是直接共享写workspace或任意MIG切分。
- 原仓库C:/Research/plan/autoresearch_project停在旧本地提交且有用户untracked；未checkout/修改它们。完整fetch挂起后只停本轮确定PID；所需确切提交已单独成功取入活跃checkout对象库，不新增分支、不改学长仓库。
- 新直接近邻SchedMate（arxiv2510.03334）已覆盖源码语义、历史检索、免部分profile与干扰撤销；2024poster还有版本差异跟踪。宽概念不能作创新，完整对应缺口未证实。ElastiCo/AgentCgroup/AIRA2已补核。详见CURRENT_DIRECTION和ROUTE_DECISIONS R14。
- 新补Cortex全文§2阶段资源池/借用、SpecBox§3–5沙箱预热/预取、Agentic CPU-GPU Scheduling§3–5 profile/三选/重测；不能称阶段解绑定或LLM调度首创。优先级仍是A1普通借还→固定共享→廉价准入→才问语义，未知一次性生成程序的累计测量成本是待验证窄问题。
- 可检验窄点为：无匹配历史、无统一进度/恢复接口、晚发资源峰值的生成程序，语义是否真能超过廉价准入/检索基线。不能因设定不同就说创新已成立。
- 代码核到学长LocalGpuPoolLauncher为run级固定整卡FIFO；当前ExecutionResult/journal没有完整资源时间序列。两个最近开发根仅做文件名元数据检查未发现遥测文件（nvidia.icd是假命中），没有读候选/分数/凭据，不据此给出空闲率。
- 已实现phase1/sandbox_scheduling/observe.py及test_observe.py、README：独立只读观测，不改src/或学长分支。只采显式同用户PID身份和可选设备；未知不补零，身份变化停止记录器，不改变候选。候选范围恒标记不完整，GPU数据是整卡非候选。
- 工程验证：整目录本地44测试、43通过/1项Linux跳过；原型observe远端23/23、census10/10、pilot3/3另通过。原型单测不查询GPU；真实GPU/容器仅16624六次fixture。测试不能冒充系统收益。
- 源码SHA94290bfc020825415acc454622c8e2d6c2da593075f2f86a5c5877a26400ed91；测试SHA5a1b24ee8773a9add005e0c313115aafcbb824ec3b4d0803e46cde1fac7a6e92。回执sandbox_scheduling/validation_windows.json和validation_linux.json；基底e5e83b6e，新文件未提交，哈希绑定实际测试内容。
- 上传初次被审查拦下后未绕过；确认linux5为yzyang4、官方研究盘及临时目录均同用户700权限，再由安全复审批准原复制。后续同目录小分析器/限定批次正常获批。收尾26文件scan0，运行源SHA未变；没有原始候选/模型/标签/凭据导出。长期教训已加到旧checkout的EXPERIMENT_LESSONS。

## 推荐实施边界
1. 完成独立v0后，下一缺口是可信kernel/子进程或专属cgroup归属及arrival/start/end/release事件；不能只测worker/server低占用当候选空闲。Jupyter与FreshContainer接入点已记README，不为易观测暗换后端。
2. README已列A0 run级整卡/A1执行级借还/B固定双并发/C保守准入；先排除简单机制，再讨论D语义。新收益批次尚无冻结程序清单/获批GPU预算，不能延长16624。保持同生成服务/CPU预算/镜像/代码/写隔离；不恢复关闭的旧恢复逻辑。
3. 只做事前准入、等待和完成回收。初期不抢占、不把SIGSTOP当显存释放、不依赖3090 MIG；MPS和cgroup实际权限另核。
4. 先从同环境已知可执行、合法开发程序确定固定清单；CPU/神经/混合覆盖，不能只用最近两个CPU文本任务自证GPU收益。资格失败和排除有完整分母，不按增益挑样本。
5. 第一关是系统净收益，第二关是语义超越强参照，最后才固定search的live E2E。成本计整个保留资源池+调度器+失败；吞吐不能因偏爱便宜候选代替质量。具体新批次矩阵/预算未批准，不提交GPU。
6. 继续按用户AGENTS规则先给设计/diff预览获准再落生产代码。本轮仅新增旁路原型/测试和简短使用说明，未另写长汇报。遵照此前可同步产出授权，已快进推送我方研究分支；不触学长分支。

## 当前远端/Git状态（最后观察，不自动当未来实时事实）
- 16:27香港队列只见旧12535 critic_zero3_resume PENDING(JobHeldUser)，未操作。16624已完成且全部step退出，当前没有我方新实验在跑。
- 16:35–16:36推送成功：我方phase1-value-critic为4790620cd91ec41819cf2a3c6dad01869ce08b4f，基底e5e83b6e；未强推/建新分支。学长dojo-reproduce在提交前fresh fetch仍dfff0efb9daf1d4a63c74492f138c19c1fd8440e，未动。
- 26文件已发布（源码、结构回执、方向），staged filename敏感匹配0/凭据形状0；工作树仅这份post-push状态更新未提交。旧checkout经验文件只加本轮长期教训，未收进公开提交。
- 活跃checkout C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001；旧aira-dojo-codex-20260813的用户dirty不动。

## 旧限定批次已闭合，不重跑
- 16582 COMPLETED/0:0；原16槽、4事前安全排除、12执行、0有效评分、0完整比较，结论inconclusive_no_valid_comparisons。分配2004单3090秒=0.5566666666666666 GPUh。
- case1四条XGB.fit early_stopping_rounds接口错误；case2四条字典multi_class错误；case3四条代码执行阶段超时。exec约310秒/worker约440秒，不能称严格300秒；外部评分调用0。预检遗漏由我方承担。
- v1/16580执行前取消、分配0；原case0四槽因已知Pizza结果代理排除不替换。v2单卡90分钟、≤1.5GPUh已在原授权内结束；未采用待批150分钟方案，迟到回复也不能扩大闭合批次。
- 根/research/d7/spc/yzyang4/natural-opportunity-20261006-v2；执行7def7a86e4ba01354a924ebaefc353d6ee4fdcd2；plan SHA210dede263d211177806ce501fb2cbe725861cbe71a8b4c7289f67e49f8d134b；summary SHA2cd9ccd869f109a96e521569b273fa403b2fc97ed1dcf2acf574143dfebc9c60；runs SHAbc6010254980b47128b30d9680409db8ae3f08a684ee728d76b36fd8053ae1a1。
- 主/次分析与兼容覆盖已公开于087b68ec66297beaf480dd23fd5e7187c272fb4e，随后e5e83b6e记录发布状态；无有效比较≠没有改善机会。readout-v1不可覆盖。不同Trace不证明独立run，原样重启不等于跨训练seed。
- 16560数值导出曾被审查拦下且仍待单独授权，禁止借新方向绕过。其他历史完整记录在Git e5e83b6e版交接与各结果目录；R11/R12/R13停止配方不重开。

## 安全与恢复
- SSH linux5；Python /research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。任务镜像gpu27/gpu28 RTX3090，不投projgpu39。研究盘4TB至2027-08-30。
- 不读first-960/Target-300/Target-522、D_val/官方test；不训练agent底座；不恢复旧HCE/多保真/Probe/K≥1。密钥只在远端，不能回显/下载raw凭据。
- 每次恢复fetch方向入口，分清已读提案、已实现、真实运行与收益；不从旧聊天自动恢复已闭合预算。
