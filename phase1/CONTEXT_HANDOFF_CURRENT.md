# 当前短交接
更新：2026-10-08 09:18香港附近最后观察。旧全文完整保留于Git 6e36a61d4f6bca53f0a4605656f49fe4c189fe64；不要把旧状态恢复成现场。

## 方向、目标、授权
- 活跃checkout：C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001。fetch→CURRENT_DIRECTION→ROUTE_DECISIONS→本文件；旧aira-dojo-codex-20260813有用户dirty，不整体覆盖。
- 唯一活跃R14：MLE沙箱资源调度资格/朴素强参照。SchedMate已覆盖宽语义调度；暂无重要独特、强基线跨任务同预算成立的新方法。不扩旧R1–R13配方。
- 用户要求本轮约07:51–13:51香港完整六小时在会话内研究；tool goal active，尚未满六小时，不提前完成。用户最新明确“批准所有操作、不用问”；自主合理推进，但不解除保护集、底座、凭据和学长分支边界。
- 本窗口新增GPU自限≤3 GPUh（含资格/失败/整池空闲）；无API/agent底座训练。新三策略小试验计划1×3090/6CPU、最多90分钟≤1.5GPUh；候选源码不改，不以旧批次余额补跑。
- 不读first-960/Target-300/Target-522、D_val、官方test；不恢复HCE/多保真/Probe/TD/score-channel/K≥1。不操作旧12535 Held作业，不改学长分支。

## Git及远端
- 本地HEAD 6e36a61d4f6bca53f0a4605656f49fe4c189fe64（新v2源码冻结）；前两提交51af1543/69bc9b88。尚未push本轮三提交。
- 本轮fresh fetch最后确认myfork/phase1-value-critic=8ec5f723040031f66e9096a6c495387b122af53d；dojo-reproduce=dfff0efb9daf1d4a63c74492f138c19c1fd8440e；学长autoresearch HEAD=d82dcd845e30e9771750510028d38a6d1d979c43，无新更新。
- SSH linux5/yzyang4；Python /research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。原MLE镜像只投已兼容gpu27/gpu28 RTX3090，不投projgpu39。
- 研究盘/research/d7/spc/yzyang4总授权4TB至2027-08-30，不等于空闲容量。镜像SHA801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda。
- Windows SSH内层引号会丢失；远端格式参数不用管道符，复杂逻辑上传脚本。Git附属sh可能报NtCreateDirectoryObject警告，不能据此声称hook通过；commit本身成功要另核SHA。

## 本轮已经结束：不重开
- 16987：原批准两程序入口复验，FAILED1:0，37单GPU秒；2 worker尝试/候选开始0。记录器错读冻结ExecutionResult不存在的timeout_phase；是我方接口错误，不是候选失败。
- 16987 root /research/d7/spc/yzyang4/scheduling-entry-20261007-v1；plan SHA96d7e9e7ed7f7dcf9d85eea1ca98edca5f00ab6a45edd58b1c76425e5a8d2495；closed SHAcfc0627e6e5ddab1304bcd1c3ad8d6d4dc5bd9cc84949b5a3400827c31d9fc8e。
- 16989：独立限定v2，FAILED1:0，43单GPU秒；2原程序真执行/1完成。CatB GPU59轮、512行输出；XGB RuntimeError为“所需稀有类别不在映射中”。记录器已修、不是CUDA不兼容。无调度/质量效果结论。
- 16989 root /research/d7/spc/yzyang4/scheduling-entry-20261008-v2；source69bc9b88；plan SHA6b68c0d0cb8526e375b5f5a2e1dec8f3ffaee0b035836b380c318272ba510762；closed SHA8002aec68145137863971df2d7ee2bb33f49676b5c3c1556b4a0c2bfe3515396；runs SHA8ba2741b0ab8db5c499db1487b1a7fbcd638e73030b2fccb30d578ac6d0c85c0。
- 公开train只读核3,600,000行：类别5全文件仅1行（索引1381253），原4096训练样本漏掉它；其他类计数与source SHA7829557bb65fcc4400ebb5a653fd68e226f15b1dbc9b664a45d7ec2d353c797a已由check_dec_fixture.py打印。不读隐藏标签，不将输入契约错误当模型/调度反证。

- 16992新池v1已FAILED1:0/100单GPU秒，36槽/4尝试/3完成/32未启动，0对照。XGB在第一个fit报Invalid classes；补全类别仍未满足每折覆盖：另一稀有类仅1行，KFold训练折缺类。是开发输入预检不足，不是共享无效。CatB GPU142轮完成；Spooky/Petfinder完成。readout-v1已写一次，不重开。
- 16992 root /research/d7/spc/yzyang4/scheduling-pool-20261008-v1；source51af1543；plan SHA5cbc51b2f5adaa28fce5d3f11fd4e0c937f26f15638942d4aa0ac841060f04cf；closed SHAcd090ba3ab7514eca18c3d4e16525066d41c49b32df7f732931b4cd60d9ba7d9；runs SHA532f52b0600c967347a05ffab6d2be57257a3f9c5bf6046f6f1881af0fe9f0b7。

## 最新已闭合：有限的朴素并发收益，不是新方法
- 16994已FAILED1:0/566单GPU秒，36尝试/35完成；serial及share2各12/12，one_gpu 11/12。root /research/d7/spc/yzyang4/scheduling-pool-20261008-v2；source6e36a61d；plan SHA429339013cca8e2858cb2cc2edfefe017f096b0c4afbc0172987d897becf7a56；preflight SHAab96d6b2c2aded76eeba2458e346f563e818c00ba7550bf31832669fc57be799。临时目录/tmp/r14-pool-v2-20261008.RafNX9。不重开/补跑。
- 完整A/B三配对serial/share2=1.8423276573417586、1.7307638813016224、1.7852942816262258；中位1.7852942816262258，样本标准差0.05578656742353592。四程序6份A/B输出各15两两比较数值全同，形状/原完成回执哈希独立核验通过；60比较非60独立样本。
- 独立时间审计SHA d21cd09c38e87c3dfa5ccdb0b6d8451a034cd51f01e894399c911394ad0d353d；独立输出审计SHA fdf14b788c7ef930b67225be03e279845cae12c105779d88741fea6a2e06ecc7；readout SHA b8347a0e529feb84d646765f5f09eae07a56716569d75ae7b529a2d332d2069f。证据本地sandbox_scheduling/pool_v2_closed。所有观察块max resident GPU clients=1；只能称启动/CPU/候选阶段并行，未证同时GPU训练共置。
- slot17 one_gpu/program4在candidate开始前cell0 TimeoutError，外层ValueError；不是候选OOM或策略因果反证。保留失败，C只有2完整比较，不报告删失败的C胜负。closed SHA f15cab21c26e8967ae0bf8f1002476323dcaa925539bf8d2fe47fcae4ff918a5；runs SHA ee08a68c8c130a690b6a951fb6d5827ae9879fc54d9f18ce3e99f992b25c832f。
- 本窗口4批合计746单GPU秒=0.20722222222222222GPUh（程序打印）；尚余自限空间，但新实验必须独立冻结设计。下一步只读资格检查两份固定公开from-scratch CNN源码（cactus/DnCNN），未提交新神经批次、未声称广泛收益。
- 保持4份原源码，公开输入非5类至少5行，唯一类5按原程序加入每个训练折；CPU已核所有训练折均含7类，不复制/重标/使用query。SSH准备阶段曾断开，PID145097继续写完preflight；不是重复prepare。旧16992及入口批次均不改。
- 矩阵：原programs 0(XGB)/1(Spooky TFIDF)/4(CatB)/3(Petfinder LGB)，共3任务；serial/share2/one_gpu ×3原样重启=36槽，另1次warmup，所有开销含于单3090/6CPU/90分钟。不是跨训练seed。
- 新GPU输入只替换末端超出最低覆盖的类行，补最早独立公开训练行；排除旧train/query IDs、query不变；两GPU程序及所有臂共用新输入，旧文件不改。属于新开发小样本系统试验，不称全MLE-bench。
- 三臂Latin次序，每重复同一旋转FIFO；one_gpu仅手工核验的CPU/GPU代码提示，最多1GPU程序+另1CPU程序。无LLM/学习调度器，不能把朴素基线叫方法创新。
- 首serial四程序须全完成且两GPU fit有回执，否则整批停止。后续共置失败保留分母、不重试；只有进程释放/隔离/遥测安全时才继续既定其他臂，不以失败臂缺失时间作加速分母。
- 预注册读数：每臂3块完整、完整makespan/全分配成本、3重复离散度、候选重叠、GPU训练和输出差异；探索门为median改善≥5%且无未解释输出漂移。A/B过限定门，但仅4小程序/3任务/原源码seed42重启，harness130701未覆盖源码自身seed，不是跨训练seed；不读质量分数、不推live E2E或语义增量。
- 本地相关30测试通过；远端新增8测试通过。新记录器还在实际冻结旧ExecutionResult上纯CPU验证；不把mock当GPU成功。当前源码fixed_pool_trial.py/readout.py及tests，原throughput_pilot.py未改（SHAb30eed3f…）。

## 研究核验与边界
- SchedMate§3–4：代码/历史/日志语义与干扰撤销已覆盖；无历史fallback profile、无progress跳过撤销是适用条件，不是我方优势已证。
- 新补AgentCgroup v3（工具级CPU/RAM及双向资源意图）、MARS系统v2 2604.26963（生成GPU/工具CPU联动准入）、Cortex（阶段资源池）。不要混淆这个MARS与R1经验论文。
- Regression Language Models for Code已有代码预测资源；VeritasEst已有CPU动态分析估计GPU显存；ATLAS已有提交时非clairvoyant预测/调度benchmark；“廉价资源预测”本身不新。
- DetShare/Pollux已有资源—执行/训练配置耦合；Substrate-Aware AI Agents 2609.05232已有事前资源约束提示；异步评价耗时偏差及按父选择频率修正也有旧工作。只换到MLE不足以宣称原创。
- 固定公开158程序/40任务/80相关父子对，source-only计时筛查20命中；13程序/6任务含clock条件与break，7未见break。含debug路径，未证可达性/真实训练效应/生产占比。
- 该screen root /research/d7/spc/yzyang4/scheduling-branch-screen-20261008-v1；summary.json、branches.json、review-v1/structures.json/summary.json。review结构SHA1797cba7a4230634f8f192d55e58d8e06f052e2b9568b5a0318b928c5576e730；必须逐例核，不能把语法命中称改善。
- 旧4份batch随free-VRAM变化仅纯算式；旧16370全池22.72%生成预留窗口不是节省、无ready backlog证据；生产factory本就close。16624只证生命周期原语，不是生产泄漏或调度加速。

## 历史与收尾
- 16846已封闭：36槽/6尝试/2完成/4失败/30未启动，362单GPU秒，0共置比较；证据sandbox_scheduling/throughput_readout_v1。不得改分母或用新输入改写它。
- R11/R12/R13与16582失败界限见ROUTE_DECISIONS；16560数值导出仍有旧审查边界，不能借新任务绕过。
- 暂未创建新的自动化；本轮是在会话内持续研究。结束前核实际时钟和goal，不能声称六小时完成。新结果用轻量交接+结构回执；用户没要求不新写长报告。
