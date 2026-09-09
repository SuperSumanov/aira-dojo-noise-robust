# Context handoff：ForeTS e2e探索（corpus与predictor为支撑）

**Last updated:** 2026-09-09

**Dynamic status timestamp:** 2026-09-09 08:15 UTC，0L126覆盖下文；单GPU20分钟已获批，80G主存申报被调度预检拒绝，仅改--mem=0待确认；尚未提交，g0-r5暂停。

**Purpose:** 给上下文压缩或新会话一个短入口，防止恢复已经关闭的旧方向。

**Authority warning:** 本文件不是科学方向的最高权威。开始任何实验前必须先 fetch Git，再读
`phase1/CURRENT_DIRECTION.md` 的最新日期段；若两者冲突，以后者和用户最新指示为准。

## 2026-09-09 当前入口，覆盖下文历史状态

最新0L126：用户“OK按照你的推荐来”已批准1GPU/20分钟验收，不再重复索要该GPU预算批准。
原--mem=80G在projgpu39被sbatch --test-only拒绝：该节点RealMemory仅登记1MiB，尽管物理可用约478820MiB。
已有本项目脚本使用--mem=0；本轮test-only用它通过，但它取消调度器80GiB硬限，因此**只等该主存申报变化确认**。
没有真正提交，test-only虚拟编号12890不是作业；当前实际用户队列只有旧12535 JobHeldUser，不释放。
两卡均占用、现有作业剩余上限约10小时，不保证等待时长。入口/模型身份预检正常，未重跑CPU/G0/15GBhash。
回执gpu_acceptance_scheduler_preflight.json在results/forets_bounds_20260909，实际0GPU/0模型load/API。
若用户同意--mem=0，先更新原脚本/方案资源语义，再在原单卡20分钟预算内提交一次；不要创建更多重复准备任务。
以下“单GPU尚未批准”为历史状态，已被本段覆盖。OpenRouter安装仍缺，与无API的GPU验收分开处理。

最新0L125：forets_pilot_plan.py新增free_route_overrides(显式client)，接在基础/有界launcher overrides后；四算子统一免费模型、
tools、零prompt/completion/request价格上限、禁fallback和环境导出。静态检查两模型不等于授权双模型真实扫参。
真实SDK发现嵌套DictConfig不可JSON序列化，在发HTTP前失败；0014仅把bounded GenericLLM生成参数解析成原生容器。
新组合tree0d64733e34f287e44df838accef3e082dcd423f9；接原059328树，generic blob f8aaefbb9578f20d184b75da271653de0826c625。
隔离source=/research/d7/spc/yzyang4/forets-free-route-20260909-6627x2/source-v3；未改学长/生产目录。
4项新检查通过：16份配置逐对仅selector不同；8次真实SDK→本机人工HTTP请求有正确free模型/tools/零价格请求体。
回执free_route_checks.json及free_route_initial_failure.json，位于phase1/results/forets_bounds_20260909。
0外部API/GPU/model-load/真实任务；不是收益或供应商账单获证。不再重复这些检查。
远端两.env复查仍无OpenRouter凭据，必须用户/学长直接安装；单GPU20分钟矩阵仍待明确批准，g0-r5继续暂停。

最新0L124：学长已确认PRIMARY_KEY应使用此前OpenRouter key。学长065b两client配置映射为
nvidia/nemotron-3-ultra-550b-a55b:free和poolside/laguna-s-2.1:free，base_url=https://openrouter.ai/api/v1。
不再重复询问平台/模型。两个工作目录aira-dojo与aira-dojo-reproduce的.env只读形状检查显示没有OpenRouter变量/形状值，
PRIMARY_KEY均不是该形状；不能把说明使用哪把key当作已安装。需用户/学长直接安装远端OPENROUTER_API_KEY，
未来只在隔离进程内映射PRIMARY_KEY，不能覆盖生产全局配置，也不把聊天凭据经命令/本地文件搬运。
官方免费端点会记录/可能训练输入，初始接口检查只用公开人工样例；无私有语料或保护集。
零价格上限、禁付费/模型fallback、失败照记；两臂保持同生成器。0L123GPU矩阵仍待批准。
本轮0真实生成请求/GPU/model-load/任务；只是新事实核验。g0-r5已实际暂停并验证PAUSED，未准点暂停，不能声称02:10准点完成。
无自动任务续期，无学长branch/生产代码改动。以下0L123及更早“接口对应仍等学长”为历史状态，被此段覆盖。

最新0L123：forets_8b_acceptance.py及FORETS_8B_ACCEPTANCE_PLAN_20260909.md已准备；批脚本prepare_forets_8b_acceptance_20260909.sbatch未提交。
独立待批矩阵1GPU/projgpu39/6CPU/80GiB主存，allocation20分钟/step19分钟/process1050秒/两段5秒cleanup，
名义0.3333333333333333 GPUh，加已观测KillWait为0.4166666666666667。不是此前G0或9GPUh条件规划已授权。
0真实GPU/API/model-load/任务/保护集；仅4项准备检查+shell语法过，执行分支没有验收，回执名acceptance_preparation_checks.json。
固定现成8B+16K/BF16/batch1，人工short/long、seed6/7，warmup后测两次及本机HTTP；不是科学收益/新训练。
GPU包元数据torch2.11.0+cu128/transformers4.57.1/accelerate1.11.0/safetensors0.5.3，模型和loader原位置不变。
等待独立GPU预算批准以及学长API对应事实；不要重复要key/模型、试送endpoint、重跑检查或扩展工程审计消磨时间。
必要准备已完成，等待期间只查有意义的新回复/上游变更；02:10 UTC后备暂停，不延长。还不能说真实8B或e2e已开跑。

### 此前worker接入（0L122）

最新0L122：0013接0010+0011+0012，tree059328196ca359965732308eebf7e57eb9c9ecd8。
新worker独立预算库/排他标记、进程限时、正常及本地超时后归档；Slurm launch显式step时间，重放在dispatch前拒绝。
需要明确关闭logger.write_env_vars；默认不启用的入口不变。source在forets-bounded-worker-20260909-xobxuu/source-v2。
新7项检查PASS（真实无害CPU子进程+伪Slurm identity/Popen），0真正Slurm/GPU/API/model-load/任务；不等于集群验收。
初版子进程8秒启动超时、0intent，诊断复现一次后把预算逻辑从重LLM包移到dojo.utils，旧import留兼容，不增加时限。
最终轻量child未导入litellm/torch，正常/超时都保留预算；失败诊断及最终结果在results/forets_bounds_20260909/bounded_worker_*.json。
只读Slurm config：KillWait300、OverTimeLimit0、cgroup、UnkillableStepTimeout180；270分钟2卡9GPUh是名义值，
加KillWait为9.166666666666666但仍无故障下绝对结束保证。step30分钟/worker1740/终止余量330/剩余门2130是提议。
测试cap40请求/8192输出非正式批准或美元cap。预算归档不覆盖SIGKILL/节点故障，标记未知，不自动恢复/重建。
下一步只准备一次8B真实GPU验收的明确预算/预检；API映射和价格等学长，不催问、不试送密钥。不重跑旧检查填时间。
后备截止02:10 UTC不变。暂无实际模型收益或e2e结果。

### 此前整轮额度（0L121）

最新0L121：新增0012接0010+0011，tree49fd8698e6a5a3377224a2d92c65f354cb1eefa0。
node-local SQLite共享adapter-attempt额度，dispatch前落intent，不因失败/取消/重启退款，不自动建库/重置。
四算子统一bounded且required-budget；8份真实Hydra完整配置4组仅selector不同，metadata.seed=6/7确实落位。
新6项CPU检查PASS，4进程24次竞争仅7次放行；没有GPU/外部API/模型load/任务/保护数据。远端exit0已捕获。
目录/research/d7/spc/yzyang4/forets-runbudget-20260909-cyPIf2，回执results/forets_bounds_20260909/run_budget_checks.json。
准备入口forets_pilot_plan.py不是launch脚本；正式max_attempts/美元上限未定，8192/120为配置验证提议值。
worker每run独立初始化/保留同一预算库、Slurm step硬限及真实8B预算还未接入。不要把节点本地库当跨节点/跨allocation恢复。
上游重复log handler会重复显示event，按DB或attempt_id去重，不按日志行数计API。本轮未改上游handler。
不重跑本轮6项或下文旧检查。接口等学长，不重复问；g0-r5原截止02:10 UTC不延长。

### 此前有界入口（0L120）

最新0L120：用户睡眠6小时并要求中断后续接，g0-r5已更新，截止2026-09-09 02:10 UTC后暂停。
新增forets_bounded_process.py及最终6项Linux进程检查通过；它只包POSIX进程组，不是Slurm/cgroup保证。
残留子进程回收后不能把父进程0当完整成功；初版已修为completed_with_leftovers。预算计两段grace。
新增0011显式单次传输补丁接0010，tree73fe9803cab2d325373dcc656842dfa35cf7d682。单独新backend已通过9项人工检查，
真实SDK+本机HTTP服务的4种情况各1次HTTP；0外部API/GPU/fit。未知cost=null，不是美元cap或provider取消证明。
结果results/forets_bounds_20260909；源码/测试位于远端forets-bounded-20260909-79jvTk，未改生产或学长分支。
后续只补未完：四算子统一显式配置、全run请求/费用上限、Slurm硬限/真实8B预算。不要重跑6/9/4、10/8、G0或旧审计。
API平台/地址/模型仍待学长，不能试送PRIMARY_KEY；无价格时不把费用0写成已核实免费。

### 此前已完成接入（0L119）

先读CURRENT_DIRECTION0L119。模型已到位，用户明确“我等一下学长回复”API对应关系；不要再问或发送PRIMARY_KEY试错。
0009离线raw loader的10项CPU检查已完成：真实tiny Qwen3 seed6/7前向/RewardScorer一致，真实8B仅400键/形状及tokenizer。
回执已取到，但旧SSH连接reset退出1；无遗留进程，不重复旧测试，也不宣称真实8B已加载/前向。

学长最新065b0fbaa89e0eb663f2834ec768081f5d56394d。用累计0010独立应用于该commit；**不叠0005—0009**。
完整集成tree83ffe50f517dde409baba3a73e69ef5872dab1ac，Dojo在远端独立
forets-e2e-dev-20260908-IMuJx6/upstream-065b0fba；critic两文件仍在该根的critic-offline-v1中，逐blob等于新tree。
修复了新集成的未选候选重试重复导出，以及JSON helper误改代码字符串/原文日志；人工前后复现+修后8项通过。
真实Hydra seed6/7仅selection_policy不同，实际save_checkpoint分离执行/未选日志；无GPU/API/真实任务/新收益。
脚本与结果见scripts/check_forets_upstream_065b_20260909.py和results/forets_e2e_pilot_20260908。
首次测试脚本SQLite读连接未显式关闭导致NFS清理异常，已修正，非生产ledger连接泄漏；详情0L119。

不要把等待变成G0/旧选择器/来源/语料审计循环。接下来先按学长建议轻任务+确认的免费endpoint做真实集成，
完成硬预算后运行小型e2e随机/critic对照。endpoint未回复；真实8B GPU推理及8run硬cap/费用表尚未完成。
当前候选9GPU小时只是规划；不释放旧12535，不恢复已关闭方向，不动保护集，不改学长分支。

## 2026-09-08 历史入口（0L118，加载状态已由上文更新）

先读CURRENT_DIRECTION0L118。用户已给模型下载链接；Qwen3-8B.tar.gz完整下载12051153651 bytes，
SHA256 01dda87a6dfaf77a6c454efcb1a9d5a88964f11f7b4dd88edea1f331be84f1d6，远端目录
/research/d7/spc/yzyang4/forets-critic-incoming-20260908-3lcjjcwq。不要再次索要模型链接或重复下载。
解压已exit0（338.4秒，中途研究盘I/O等待），不重复启动。实际路径为本目录
unpacked/Qwen3-8B_reward_seed1/checkpoint-100，15136866890-byte model.safetensors SHA256
bb0c6a1801cf0a753bb1f8aa1c923f9fcc7fff81fd654ae9d3a932ee280dfb74；400 BF16 tensors，backbone.*与head.weight [1,4096]。
未读训练状态/评测值，另2个非必要文件跳过。没有随包rm_meta/config/tokenizer；底座配置/分词器已按
49e3418fbbbca6ecbdf9608b4d22e5a407081db4只下载约7MB到base-metadata，无底座权重重复下载。
上游raw loader仍会先取底座权重；完整state从固定配置构造的strict本地加载入口尚待接入/实际验证。
尚无模型load/GPU/API；API路由和有界运行预算仍未完成。三份简要回执见results/forets_e2e_pilot_20260908/critic_*.json。

### 此前模型回复（下载位置现已由0L118补齐）

最新用户交接：学长确认Qwen/Qwen3-8B-Base/16384；RL没得到更好模型，当前只是任选现成旧critic试运行。
不等RL/不重训，不称最佳checkpoint或scaling结果；仍未提供共享绝对路径/下载地址，API路由也待回复。
不再询问已确认模型/上下文，只补实际位置；尚未读权重，不自动解除具体旧模型的撤回禁用。

先读CURRENT_DIRECTION0L117。学长c4285499新增asyncio.run等待分析；我方新0008修复request_guard触发的循环导入。
新组合c4285499+0005/6/7/8，tree b146ac436fbd6616ed7573ee48df5eb5140dfe17，源码位于
forets-e2e-dev-20260908-IMuJx6/upstream-c4285499；旧源码未覆盖，不改学长branch或生产目录。
两种导入入口的新CPU进程均过实际_analyze/analyze_op人工异步LLM检查；旧TypeError复现，新正常返回和异常透传。
初次循环导入ImportError属于我方问题，已记录；非真实API/模型/e2e收益，不重复旧验证。
外部模型路径/API路由仍未补齐，继续等待；收到事实后才完成硬预算/有界GPU集成。新文档未给新模型路径。

### 此前状态（0L116）

先读CURRENT_DIRECTION0L116和E2E_EXPLORATION_PILOT_20260908.md。集成tree6f7e650在远端独立目录
forets-e2e-dev-20260908-IMuJx6，真实aira环境已导入ForeTS、两臂配置validate通过，仅selection_policy不同。
候选首轮leaf/ spaceship，seed6/7、两臂8runs；完整300秒执行、4次执行含debug、软搜索1800秒。
条件9GPU小时尚非硬限/批准预算，API费用未定；未运行模型/任务，GPU/API调用0，不能称e2e已跑通。
已问用户转学长：可用未撤回critic共享路径/底座/上下文；正确API服务或远端安装OpenRouter凭据。
文档checkpoint本地对应位置不存在；.env PRIMARY_KEY不能无验证地发往OpenRouter。秘密未回显/传输。
外部事实未回等待，不重复同一路径、G0、旧测试或语料预算。回复后继续有界真实集成；不重启严格四fit。

### 此前状态（0L115）

先读CURRENT_DIRECTION0L115和ADVISOR_DIRECTIVES的L节。用户转达学长：corpus只作proxy，最终目标e2e；
探索阶段提速，GPU用一次有界交互分配连续debug，停止过细的shard/失败回执/恢复重复验收。
我方已暂停本轮未开始的TF-IDF扩展，下一步先查未撤回的可用critic与真实开发任务，准备小型e2e探索预算表。
共同batch随机vs critic只改选择器，固定底座/资源/执行规则，观察实际任务成绩与整体成本；不能用pair准确率代替。
不再把历史完整provenance作为所有探索的前置，但不解除原严格四fit门，不触保护集，不将探索数据洗成确认集。
必须保留最小config/seed/成本/结果/失败说明；额外审计要针对具体风险，不能继续占据主线。
SSH实查12535 PENDING/JobHeldUser、Priority0、RunTime0，是过时恢复测试，未释放/取消；G0已完成不再运行。
学长head仍54929；本轮无GPU/API/fit、无新语料观测或模型收益，未修改学长分支。

### 此前状态（0L114）

先读CURRENT_DIRECTION0L114。共享Drive最新可见仍0906（46项/40日期），学长head54929无变化；只有旧12535 PENDING。
小sibling成本已用排序与独立子集DP核对，固定84run/24组件/15任务，不读程序/成绩/保护集；库存712组/1757程序实例。
6个双组件支持任务，每任务一个假设dev组件内1/2/4组的执行cap为39600—218400 /79200—436800 /158400—873600 GPU秒。
对应11.00—60.67 /22.00—121.33 /44.00—242.67 GPU小时，仅假设1GPU/程序，不含初始化/评分/IO/祖先重放/训练。
无角色/程序选择、无准入/执行；小工作量备选不是加速，组数不等于独立样本数。原严格四fit仍待外部事实。
记录results/sibling_reexecution_bounds_20260908，本项完成别重跑；后续可推进未完TF-IDF/身份/全成本，不启动GPU/API/fit。

### 此前状态（0L113）

先读CURRENT_DIRECTION0L113。0007新增uniform_random/critic_topk_random必填policy，前者零critic调用；
先整批生成冻结再评分，候选篡改拒绝。selector v2的同池k=全池控制精确一致，旧批次不得重选。
新16项Windows+实际Git tree6f7e650e5ecfd8dac7369a954ac16e01f258daa1通过；源码82242e68e6d5f5584972ae7f892236d0454e64b1的Linux16项全过，
2.483947792003164秒，独立核16唯一case、7源码/8输入hash、零stderr/锁。本项完成，不重复新16或旧16/69/G0。
远端forets-selection-20260908-YyGg83UH，receipt84c2fd00c33ba35b34f0dc3e0bb81ccfd5ed9c477cdbfd8fafc0d2afcc7c7cdb。
不执行实际模型/程序、不改学长branch/生产checkout；详见results/forets_selection_20260908。
pool hash不能代替相同父状态或自动证明真实同池，成本/资源/TF-IDF adapter未齐、正式来源仍等外部事实。

### 此前状态（0L112）

先读CURRENT_DIRECTION0L112。新增0006独立task-return回执接在0005后；主执行/debug分别记录，
在analysis之前落盘，未知执行不重试。15 Windows通过/1 Linux-only跳过，真实tree a999d8aaf8e9278e4e1eab57e5e45d2b0f87aa48相同。
源码28531549eb34fee78c4d198112688b250ab6cda4已Linux16全过，包含人工print真实解释器进程，3.9597221879957942秒，
独立核16唯一case/4源文件等于Git/5输入不变/0遗留子进程；receipt dbafd1f906e5d0ca5829230cc745ec08d825fc9f279844c59771aede513f9873。
远端forets-execution-20260908-dw7WTqrL，本项完成，不再重跑16/69/G0；不开GPU/API/fit。
下一步完整费用/实际资源和来源事实仍待补，未知外部事实等待，不用工程通过当科学收益。
未部署，不是模型效果/全成本/完整恢复；严格四fit外部开发原记录仍待事实。

### 此前状态（0L111）

先fetch/read CURRENT_DIRECTION 0L111。学长新head54929de4ac92cb1a1a2fd75e31843a223c10c859，
只改ForeTS的task_name引用+critic server统计，无新outcome/data；4个blob先scan0再读diff。
已准备0005累计兼容补丁，针对54929单独应用，不能再叠0002/3/4；实际tree08d78ba2b0cf71c44cbd9eda34df15ae60049409，
11接入文件等于此前验证tree34424...、新server保持学长原样、其余文件无改动。
此为Git应用/字节兼容性，不是新head运行69项/server/GPU；此前69项仍绑定旧8b621/2920b14。
后续先读最新upstream，再推进真实执行/资源边界；独立开发原记录仍待外部，不改原四fit来源门。

### 此前状态（0L110）

先fetch/read CURRENT_DIRECTION 0L110。新增0004把guarded包顺序固定并核对实际client.query输入，
留请求前意图和每次逻辑返回usage，未知成本不记0；原0002/0003不变，schema2不混用旧ledger。
Windows69项（14新+55旧）通过；实际应用tree34424d6a137729df6f9d6e0e0fcd5b63bce57262同14项通过。
Linux最终源码2920b14ddc471942ba19972f687458d339adff62已69项通过，8.896084904001327秒；
11源码等于Git、12输入hash不变、69唯一case全通过。远端forets-request-r2-20260908-Uah5sBkn，
receipt6f031733de0e2a5074c9ced68f35bcb4bb80e1a65261324172649bdcc6a6d7b3，
XML0e72d38e1f8c08de6d0ab73c8ded42036ff4a419f125ba0ec3b10ec8a0fe26de。初轮61过/8失败为测试缓存接线，原记录保留，guard/0004未改。
这项完成，不再重复验收；后续真实执行/恢复与资源边界仍待处理，来源事实不足等待外部。
不是完整费用/真实生产模板/搜索恢复/模型效果；实际开发来源依然等外部事实。正式对照两臂必须共用包顺序契约。
记录results/forets_request_boundary_20260908。避免再重跑已结束的0L109或G0；学长分支未改。

### 此前状态（0L109）

先fetch/read CURRENT_DIRECTION 0L109。源码ed14932b740b6ac9790ccaf5ebe000dd80989b0b已实际Linux55项通过，
7.792306003000704秒，7个源文件逐字节等于Git，8输入hash不变，独立新进程核XML55唯一case全通过。
远端/research/d7/spc/yzyang4/forets-state-final-20260908-2sFlhEkg；
receipt1fa4a9c66d4dcd55bf51da6b4cb50a9b61d4723561359bfa63cce3e29f9199c4，
XML4f229573cc39d89d9b88093eb9d35718b19467715e046bb4d181f4d462d12ce7。
结果results/forets_candidate_state_20260908，首次CRLF-only运输和旧别名2失败都保留，修复未部署学长branch。
候选批次定向验收完成，不重复测试冒充进展；完整搜索/解释器恢复与实际渲染prompt/全成本边界仍未验收。
下一安全项固定批次实际输入/成本接入；外部开发来源事实不足则等待，不打开原四fit或保护集。
后备已ACTIVE/15分钟，只用于中断续接，不重跑G0、不续旧摄取lease。本轮无GPU/API/fit和新语料观测。

### 此前状态（0L108）

最新补充：73fbb822初版Linux52项已通过；Git archive需命令级core.autocrlf=false才与Git blob字节相同，
首轮CRLF转换和修复回执均保留。后续发现我方候选台账list别名，已在旧tree复现2失败并深拷贝修复；
当前Windows55项（27新+28旧），新tree e2c7bcd42c69b6dac00602758bf6dda4c0c93a4c同27项通过。
下一步冻结新commit后在新远端私有目录复测55项，不能重复使用旧52项证明新代码；无GPU/paid/fit。

先fetch/read CURRENT_DIRECTION 0L108。SSH恢复且有界成本核算两次一致，安全receipt已存
results/forets_candidate_state_20260908/development_cost.json；六任务双完整组件最小条件cap2091.6666666666665GPU小时，
不走默认全量路线、不把组件隔离等同全量重执行；真实开发来源仍等外部记录，原四fit不准入。
ForeTS原0002不变，新增0003候选台账/已执行journal分离、执行前有限恢复/未知状态停机，
24新测试+28旧回归通过；独立Git应用tree af2489d55e174a73f9f92dbb416062f43dd55994，同24项通过。
没有生产部署/新GPU/API/fit/学长branch更改。完整checkpoint恢复被明确阻止，不能启动长实验。
下一步在远端新隔离目录传7个hash-pinned source blobs和测试模块，以300秒CPU上限复测，
不改生产checkout、不复制真实数据。Linux runner为phase1/forets_linux_validation_20260908.py，结果未完成时不声称通过。
中断后备automation g0-r5已更新为当前主线提示并ACTIVE/15分钟；不得执行已废弃G0提示/旧12535/过期摄取lease。
733eligible未在本轮重新观测。

### 此前状态（0L107）

先fetch并读CURRENT_DIRECTION 0L107。学长新head8b621851a87d20382feefe8c8458a7db2a1fabea新增ForeTS/E2E说明，
无新outcome，数据payload未读。现有候选框架归学长，不重复造；我方有精确提交的可选hotfix与28项定向复现。
真实临时Git index应用4文件42增11删，tree c180d1358bc03a9893b1a3a5c5678d3b006be08b，加载该tree同28例通过。
未修改学长分支/部署/启动GPU/API；测试仅Windows模拟I/O函数体，不是端到端验收。
仍有未执行节点进入journal的memory空值崩溃；下一步候选台账、已执行状态、恢复和公平批次输入接入，禁止伪造失败标签。
来源优先实际独立开发记录，备选另登弱监督训练+新标签dev，不改严格四fit准入；融合暂不拟合，保留同池TF-IDF。
本轮SSH两次关闭，scripts/inspect_parallel_source_budget_20260908.py尚未实际运行，预算角色未冻结。
详细事实与原始日志见PARALLEL_EXECUTION_AND_FORETS_20260908.md与results/forets_hotfix_20260908。

### 此前状态（0L106）

先fetch并读CURRENT_DIRECTION 0L106。用户回复“可以”不是开发记录路径；严格四fit仍无已准入实际来源。
fresh_grade_capture opt-in helper实际Linux29测试、6真实grader×31-case×A/B及各自独立重评分通过；
未部署producer、未改学长分支、无模型效果。源码6b945b6e5af738d702f493f988d7e3f10b011bd1，
summary dd0fcde699234fce9de30d200ebed33a1c97a784b66eef26e3b4ae02f6199eec；results/fresh_grade_capture_20260908。
首轮33ebc8dc测试setup命名冲突导致29初始化错误，改名后同矩阵新目录成功，失败保留。
不重跑G0/输入分词/通用测试。下一关键动作实际独立开发来源，或明确无记录后冻结新开发生产范围；不能拿前瞻包填训练。

0906poll000–007及各自post-audit全部完成，759physical/733eligible/19609endpoints/4426pairs/59tasks，closure=false。
LATEST1b44e898bbae7ffc9098bbfa584ba842e0db2be5ae6bb8b5da0475d8ab34239f，summary971d5bf25df0824ac69d28c7c88900218992b5fdb41e2e12e80403733f489baa。
入口/tmp/dispatch_0906_foreground_r2_20260908.py，output session-0906-intake-20260908，source28a139f481764951485ad6d278920a2fa3efe62c。
原窗口UTC03:40:46–05:40:46/max8/2700秒每call不变；8次额度已用完，无未完成调用，禁止第9次/自动扩lease/后台续跑。
tmp/export_0906_eight_calls_20260908.py已执行，远端safe-0906-eight-calls-20260908保留，不能覆盖或重复运行导出器。
原始回执results/session_followthrough_20260908/intake，manifest a4d0d0f0a8a01f3e26dae52ea80fefdb1029964fe6f61ea9208010ce40c43662。
本窗口新增22eligible、258endpoints、46pairs；共733/960，还差227，6新事务不等于11归档全部完成。
04:36 UTC共享Drive最新可见仍0906，11归档本地同名齐、无0907/0908目录/新config-v2；只是元数据检查，不声称新内容认证。

### 当日此前记录，动态状态由0L106覆盖

首先fetch并读CURRENT_DIRECTION 0L105。用户已批准研究汇报后直接执行；报告SENIOR_STRATEGY_AND_EXECUTION_20260908.md已推送。
原四fit仍缺合格独立开发来源/实际评分记录，尚未训练；不重新做已完成G0/CPU验收，不挪用保护人口。
本轮84历史run全部3447非空代码输入诊断完成：16K零截断，最长12533 tokens；原始安全回执results/session_strategy_20260908。
0GPU/API/model fit；这是输入事实，不是模型收益。学长最新代码的候选执行与task评分环境需要分别留记录，已写入报告，未改学长branch。
0906原协议foreground已完成poll000/001/002及各自独立post-audit；最新740physical/714eligible/19382endpoints/4384pairs/58tasks、closure=false。
LATEST76da588f6d4bc2a981f0697d0c95c0e3fdb5873dc58484516e61f4319701a706，summary85207d638b909cbf7ee1f1facaf4d49250fc90b1edec0273f3da2a4f68487735。
摄取source28a139f481764951485ad6d278920a2fa3efe62c，入口/tmp/dispatch_0906_foreground_r2_20260908.py，
输出/research/d7/spc/yzyang4/session-0906-intake-20260908。新窗口UTC03:40:46–05:40:46，2700秒/调用含核验，最多8次。
下一次最早UTC03:59:57.196054；未启动第四次/后台任务。恢复先核当前poll/post-audit/PID/锁/LATEST，不能重跑已完成事务或调用旧0905窗口。
本轮source deployment首失败因bundle缺祖先，另r2补齐；输入诊断首失败因私有manifest0600不符错误0400假设，另r2只读副本成功，旧证据保留。
这里只完成一次新摄取事务，不声称0906全部11归档均已入库。

### 当日早前记录，已由上文覆盖

首先fetch并读CURRENT_DIRECTION 0L104。12664及CPU分段验收全部已完成，不重跑构建/G0/验收。
旧12535仍JobHeldUser，不释放；正式四fit尚未开始，ADMITTED_RELEASES为空。
本轮0906新增11归档已复制/独立SHA与0400复核，总118981762bytes、归档总量354。
所有文件六小时时龄下界UTC09-08T03:40:45.566210（香港11:40:45.566210），不倒填mtime。
未调用摄取，旧0905 lease已过期，未另建monitor。恢复后先核当前状态，满足时龄并明确新有界窗口后才复用原intake/delta链。
现snapshot仍737physical/711eligible/4380pairs/58tasks、closure=false，LATEST6db37288ac0fe2ca1b833ff63c3b10318cd13610c023a9d2412c194a67dfd116。
source cef7ac01b1fa5745a733bc2b3dad3af42bb1c6d6，回执results/senior_0906_copy_20260908/README.md。
学长branch40d7dea无新outcome；旧config-v2补丁可无冲突apply-check，但未部署且不解决历史评分环境认证。
主线仍Lbudget对G-reuse→L-full四fit开发筛查；不能拿新前瞻包填训练、把历史test重命名或恢复HCE/Probe等旧路线。
来源解锁见NEXT_REAL_DATA_ROUTE_20260907.md和SENIOR_MINIMUM_SOURCE_HANDOFF_20260905.md顶部；不再追已删除snapshot。

## 2026-09-07 历史入口，仅保留追溯

最新覆盖：actual Linux 224+38测试分别通过，源码4cb39e0/6b2af78，6份原始安全回执已导出results/session_progress_20260907。
poll6实际完成，685eligible/711physical/4320pairs/58tasks，LATEST8fbc640c2c86f171509fb072dd30f2c46550a6eb639efb1e89f42403cc1e38eb，
下一最早UTC09-06T23:30:22.708955。保留过早调用错误及独立日志重命名证据，runner/科学门未变。
12648仍RUNNING，后继双卡未准备；终态检查器/tmp/verify_fa2_r4_terminal_20260907.py已上传但未执行。
无重复submit/release。确认构建及独立核验后用4cb39e0入口prepare/held独立review/release；不使用旧R3入口。
benign隔离通过、187grader代码与记录Git一致，14/15任务数据目录可用；历史timeout30分钟—4小时，不能缩成probe。
历史来源与四fit仍未准入；准备grading JSON来源字段检查，只有已核84旧run，成绩不参与选择，不碰保护cohort。
此前“UTC23:07更新”系编辑时间误写，4cb39e0提交实际UTC23:04:29，旧状态下文保留。

以下为0L93历史状态：12641已FAILED/2126秒；不是仍运行。12648 R4续编已独立核验6608原源码/32对象并release，
UTC23:01 RUNNING/gpu37。ROOT flash-attn-build-20260907-r4，submission-v7，source15402474dec5b5da1e376d3c812f53fe416c5c0b。
不重复submit/release，旧12535held。构建≤4800秒，后继双卡尚未准备/提交，须先完成独立构建/Slurm核验。
新后继入口已显式改R4/12648、submission-20260907-fa2-r4、6GPUh工程上限；模型/driver/数学容差不变。
本地65通过/3平台依赖跳过，实际Linux待做；不能调用旧R3绑定入口。
0905原12压缩字节全部与Drive相同且原位0400只读；manifest6b84ee91f1c0652842db57635942f8ebc85ff15c039e4041883302ef7b3582be。
foreground dispatcher /tmp/dispatch_0905_foreground_20260907.py保持现有hash，不重部署。
out=session-0905-intake-20260907，source78fdd47；poll4已完成独立postaudit，681eligible/707physical/4300pairs/57tasks。
LATEST47b1b594d1785eb78d6cf83d2094cd9dce1455a83a3db93b07d9175461cd85c2，closurefalse，下次最早UTC23:08:40.711460。
tiny实际payload独立18个checkpoint-rank/六role通过，e5756c4，actual-tiny SHA2126a6faffb96ef5586dbddb6b95c1ef74f33a35bfa90ca1ee7c3f6834f3b402；不是1.7B验收。
固定84run无已支持预测表可重评分，ADMITTED_RELEASES仍空，未实际四fit。不得因此放宽门/读取保护cohort。

以下0L89为历史记录，仅保留追溯，不作为实时状态：

当前六小时会话用户已批准，UTC开始09-06T21:53:36、到09-07T03:53:36（香港11:53）；未到期不能因job运行就结束。
远端已恢复，/tmp重启清空过。12641已独立释放并在gpu37运行，f1f4741固定官方FA2构建。
不要重投/再次release；ROOT=flash-attn-build-20260907-r3。真实构建限2100秒，保留1GPU/4CPU/40min。
后继双卡入口785c329：prepare_pivot_fa2_shape_20260907.py及新approval/sbatch；56文件/196真实Linux测试通过。
它保留原1.7B/16K/8×8/seed6/2PRO6000/26min driver，新增绑定FA2 overlay及两卡kernel数值门。
必须先12641成功及独立artifact/Slurm核验，才能新exclusive准备/提交后继；当前尚未提交。
旧12535仍held，12577失败记录保留；工程实际7297加当前构建实际，后续总上限13897≤14400。

固定84run/24archive已有预测文件header诊断已完成，5Linux测试、A/B与48回执/24archive独立复验通过。
只发现84grading JSON，扫描格式内无预测表，不支持现成预测重评分捷径。12commit/9代码清单事实保持。
5份早先安全来源/compiler回执及本轮header/CPU回执已安全复制并hash，不再是尚未导出。
ADMITTED_RELEASES仍空，不改来源门，不把新前瞻run当历史训练。

UTC22:17:51 metadata刷新：Drive0905有12包，本地同名12；本轮不是下载者，不能假定字节同一或下载来源。
新verify_senior_0905_existing_bytes_20260907.py先做固定清单压缩字节hash-only GET比对，≤1GiB/900秒，无payload解析/覆盖。
11项CPU检查通过，固定metadata SHA4da094a253a9e635c21d709e88ff7b38310486cae6971360923e1a2e65c4c992。
通过后再原credential-first稳定摄取；此时尚未执行字节检查。最新LATEST仍cdae57...25f2，673eligible，closure=false。
学长head40d7dea...22a3无变化，未改branch/未读新outcome。无新critic/scaling收益。

下文0L86仅作历史：

最新CURRENT_DIRECTION 0L86：远端SSH返回pam_nologin系统停机；不得绕过，R3准备/提交和header诊断上传均未执行。
12635FAILED89秒(cc1plus)；12638FAILED1秒(login/node compiler hash不同)；12639COMPLETED5秒，
实际gpu37 /usr/bin/g++13.3.0 SHA52f1ddb33fe78b9441e0f42e9cd22c571f1101938e046c8a26582494e041cc73，sm120对象编译成功。
固定新构建commit34343b8ff7dbe4107ccced6781df627afce7c988；目录flash-attn-build-20260907-r3尚未准备。
本地tmp/prepare_fa2_r3_20260907.py和submit_fa2_r3_20260907.py已上传/tmp；运行被登录限制拒绝。
本地tmp/run_historical_saved_headers_20260907.py上传失败，尚不在远端；固定84run/24归档A/B header-only待做。
先恢复后只读核对目录/队列/终态；不重投12635/12638/12639，不release12535。
Linux15项CPU检查通过；FA2完整构建/两GPU数学/1.7B尺寸均未过。费用实际7297，后续保守合计13897≤14400GPU秒。
数据独立核验完成：84run/12commit/9代码清单/24strata；每stratum1组件、12种同task配置组合均有非commit差异。
不要误加“train/dev必须同配置”门；跨配置开发有不同estimand，仍必须满足完整experiment/evaluator/来源与隔离，不能冒充同配置scaling。
私有投影留远端，不下载；新安全原始回执因停机未复制。结果目录fa2_host_compiler_20260907仅终端观测整理。
本轮没有修改学长branch、读保护cohort、启动效果四fit、刷新共享盘语料或创建monitor。

下文0L83仅作历史：

最新覆盖CURRENT_DIRECTION 0L83。学长说大多数snapshot已删除，metadata.git_commit_id可用；
独立核验固定84候选run对应12commit全部Git可读，不再等待24物理snapshot恢复已提交代码。
676历史run/24commit中22可读，两个缺失均在84范围之外；resolver只记录HEAD，不证明未提交文件/实际evaluator。
ADMITTED_RELEASES仍空；后续按确切Git版本补experiment/开发隔离和同版本构建，不能把代码恢复当训练收益。
12577已FAILED 1:0：UTC09-06 08:09:11—08:10:49，projgpu39两卡98秒/196GPU秒，缺FlashAttention2。
在模型初始化失败，没有轨迹summary；171CPU检查漏掉真实attention依赖，不重投旧路径/不自动降级后端。
12535仍PENDING/JobHeldUser。本轮没提交GPU/安装环境/训练/API。12575 tiny验收维持，不等于1.7B尺寸验收。
学长提供projgpu39两卡最长24h的srun入口；已有batch实际获配，不再重复申请交互任务。
学长branch fetch到40d7dea10738f159fc97cad8487ab4ada88022a3（09-05提交）；路径变化无新outcome，未读新train/test。
回执results/recorded_commit_recovery_20260907，两个独立脚本exclusive输出均已完成，禁止重跑覆盖。
本轮未检查新共享盘语料/实时intake，不能把下文旧673/960称为本轮新核验；保护cohort保持不揭盲。

## 2026-09-06 历史入口（已被上文覆盖）

最新覆盖：CURRENT_DIRECTION 0L82。容量恢复后的新job12577已经独立held核验并release，
现PENDING/Resources；暂估19:38:15开跑，非保证，旧12535继续held。
训练源码固定50f2967ad2637850742075454440aea2c5fa8a28，准备目录submission-20260906-capacity-recovered；
171项Linux CPU/49源文件/真实64GiB分配通过。单次2PRO6000/projgpu39、26min；不自动retry。
这是1.7B/16K纯合成G→L两更新保存/新进程恢复资格检查，不是模型效果或干净scaling；尚无GPU验收。
状态脚本/tmp/status_pivot_12577.py只读该作业；submit/release都已完成，不再运行。
真实四fit仍因ADMITTED_RELEASES为空而未启动；必须等学长真实历史snapshot/experiment/evaluator事实和开发范围。
学长head b8d095180415957aa1bab31fa53ead1bba261c03、上传日期最新0904，本轮未见新payload。
清理已完成：85旧Git副本+pip缓存，合计69931454464分配bytes，64GiB真实分配通过；不要重跑cleanup。
0L80空间失败与下面旧运行中/未提交动态状态均仅作历史，不能覆盖本段。
可选共同候选请求层wire验证已完成：f5b3f6f4e262e19f0045d15957f93d8223d03af2，34项Linux通过，
210源文件独立核对，0网络/保护路径尝试；仅client/遥测/凭据加载边界替代，无默认solver变更。
完整回执results/frozen_native_wire_20260906，先前失败均保留；不要重跑完成的exclusive检查。
12577已释放到Slurm后不依赖本地连接；当前未新建heartbeat，也未承诺本回合结束后由会话持续轮询。

最新覆盖：CURRENT_DIRECTION 0L80。新1.7B/16K shape准备已因64GiB实际分配EDQUOT停止，未提交GPU。
source ef19d100ac6cb1a747c332eb1b8596051f47a695；160项真实Linux CPU及模型哈希门通过，但空间门没有通过。
原submission-20260906是完成的失败路径，不重跑、不手工绕过。只清理自己的空probe，没有清理其他资产。
证据results/pivot_space_failure_20260906；正式四fit仍因来源未准入而不能启动。
12575已完成独立payload/FINAL/trace/只读全部验收，不能再等或重跑。
终端SHA14dae4dbc7e1497695d1081517a1603833f4a6f97bd8ac3d534b5e0debdffaa2，原失败检查器证据保留。
新pivot shape代码已发布、准备失败（不是排队）：实际1.7B/16K/2PRO6000、26min单作业；纯合成token/目标，
目标为G更新保存→新进程恢复L更新保存，但尚未发生。不读真实数据，不是四fit/源准入/方法收益。12535保持held。
可选frozen_candidate_requests原型正在本地核对，仅请求准备，无默认solver修改、API或GPU。
以下08:36/08:43的12575运行中状态已由上面终态覆盖。

先fetch并读CURRENT_DIRECTION顶部0L77及以后。12573、12574均FAILED，禁止重跑旧controller或FINAL。
12574完成full/prefix2/resume2及六checkpoint，但FP32 master最终差异最大3.725290298461914e-09，严格验收失败。
真实CPUAdam诊断找到未序列化native beta-power缓存；生产helper已过A/B八case独立验证，仍不能替代GPU逐字节验证。
准备新submission-20260906-3090-native-cache，2RTX3090/12min，2160GPU秒上限；此前817，合计2977≤3120。
08:43核验：source1c211b87880a1110e3a67cc1dc7d277e5db18441已通过Linux CPU/45源文件/独立held门。
新job12575在08:42:00开始RUNNING，仅一次；等待实际五轨迹及独立payload/FINAL/trace验收，不能提前称通过。
12535旧源码已可逆hold为JobHeldUser，不得直接放行。
以下12573/12574运行中、12535普通排队及旧预算均为历史状态，不能作为当前任务。
用户约02:29入睡，要求本会话持续工作；
约10:20–10:29才到八小时，不能提前声称已工作八小时。不要新增heartbeat或任务。

- 本夜摄取已真正完成：14事务（0903八档、0904六档）+最后空队列检查，623→673 eligible。
  当前699physical/18696endpoints/4275pairs/57tasks，closure=false，距960仍287。
  LATEST=cdae57a622cfa8e83b40e93f60dbd90045b4670c4e9050bf552ef689745a25f2。
  results/intake_backlog_session_20260906保存154份安全原始回执，A/B、独立验证和逐字节发布复核完成。
  两个旧intake session均已终止；不得再调用其wrapper/export/import或把ready=0当确认关闭。
- 冻结WL覆盖517→673已完成，新增156/移除0/共同3325pairs保持。原模型/协议不变，0GPU/API/model-fit。
  source4395e1800bf8350cecc0ecd6513bf0c11722d3c2；原child2896379退出，三个阶段rc0，实耗4350.789625179023秒。
  本地43756早前SSHreset，原远端wrapper存活并完成；不要再等待该本地session或重复启动。
  独立postcheck已通过：50manifest成员/52只读文件/24trace，安全0命中；安全13文件已导入
  results/wl_frozen_coverage_673_20260906。补算、exclusive postcheck/export/import都已完成，不得重跑。
- 最新12573 Socket作业已放行，sourceb84e8baea4de65a16038b4136cee094d29716964；137项Linux CPU/38源文件/独立held核验通过。
  submission-20260906-3090-socket；2RTX3090/18min/driver900s；同4433参数5轨迹，NCCL_NET=Socket/IB_DISABLE=1。
  新作业上限2880GPU秒，原已结束12570+12571+12572实际153，合计上限3033≤原3120。
  12572最终FAILED 73秒/146GPU秒，两个rank在RDMA枚举后SIGSEGV，0checkpoint/0完成轨迹；不得再等原12572或重启。
  独立failure audit/export/import均已完成；安全原始记录results/zero3_private_failure_12572，真实失败不可抹去。
  Socket是工作假设下的transport workaround，不是驱动修复，也不是模型收益；等待真实终点再独立检查payload/trace。
- 旧12572提交时通过134项Linux CPU测试、35源文件，source11ff14a7f6fe9a4a2ab9b830a9829f07b0249b2c。
  2RTX3090/18min/driver900s，同4433参数5轨迹；私有CUDA12.8修复成功，prefix1728files/7links独立核验。
  安装与修复均终止，不能重复执行；原默认gcc9编译失败回执保留。原始证据见results/private_cuda128_toolchain_20260906。
  旧submission=.../critic-zero3-engineering/submission-20260906-3090-private，07:44:57实际开始、07:46:10失败；不再运行。
  GPU工具链预检通过，不等于实际GPU恢复通过。
  新job上限2880GPU秒；此前12570+12571实际7、组合保守3062≤原独立3120。不自动重试。
- 原12535仍PENDING/Resources（07:38实查），26min双PRO6000 tiny ZeRO3工程验证，不能称1.7B/16K生产验收。
  不更改/重复提交。独立双3090尝试12570已失败：gpu28缺固定CUDA12.8 nvcc，1秒、2GPU秒，模型未启动。
  失败见results/zero3_3090_portability_12570；其原授权无自动重试。后来显式私有环境修复见上，不改写原失败。
- 正式训练ADMITTED_RELEASES仍空。唯一神经主候选full G-reuse→L；四fit开发screen尚未开始。
  学长24份真实snapshot/评分/experiment事实、合格开发范围和可用GPU窗口仍未到位。
  不用新增确认语料当训练集，不用合成/工程测试冒充critic或scaling正收益。
- 07:38学长head仍b8d095180415957aa1bab31fa53ead1bba261c03；07:04目录名检查0903/0904无新增，未下载/打开新payload。
  新metadata helper用站点env_setup现行代理；旧hardcoded代理helper已失效，勿重用。
  不读取protected值/候选身份；旧receipt/transition PID号被其它uid复用，不得signal。
- 研究盘官方到期2026-09-29。quota RPC不可用；共享磁盘free不是个人quota。
  私有CUDA1.5GiB分配检查通过并释放，实际工具链约1.4GB，不表示完整训练quota解决。原4GiB不足完整1.7B AdamW resume checkpoint。

## 2026-09-05 历史入口，已由上节覆盖

先读CURRENT_DIRECTION.md 0L11：DS分支恒报未skip已修，新begin/finish核验步前后状态且不自动重试。
code d6b569e，18回归、48源方法体+非数值stub控制流、24旧假成功负控、3类注入异常通过；receipt6a2e8c83…2f056b。
r1路径guard拒绝保留，r2只绑定已观察的selective→overlay目标和原源码SHA。没有真实模型/数据/GPU数值运行，
不把旧CPU恢复回执迁移到新源码。G0源仍5f3bc36未动，17:42UTC排队、估计香港12:39:11非保证。
学长head/316归档/619eligible未变；下一步仍实际GPU数值与保存恢复、同版本来源/config/split和正式fit预算。

先读CURRENT_DIRECTION.md 0L10。固定前向微批次换边已完成并按事前门关闭：分组后seed6/7/8仅改变
122/118/112对，各仅2个task达到20对；双生产+独立验证相符。不放宽规则再试、不申请其训练。
code064f48a、receipt10b5d604…b8850，结果目录results/fixed_forward_20260905；无模型效果。
G-reuse→L仍待同版本来源包、config/experiment-closed及正式预算。只可主张整体监督组织方案，
不把端点集合相同说成频次相同，不把Ghash受损说成正迁移；旧五臂和收益门未改。
17:16UTC G0 12377仍PENDING/Resources、Runtime0、sourceclean；估计香港12:39:11非保证。
学长fetch成功b8d0951无变，316archives/619eligible、LATEST bc9833d8…19456未变。
摄取3884166在9月4日07:04:03UTC正常完成145轮已退出，六小时heartbeat窗口已过期；不得称仍在持续摄取。
当前无新GPU/API/fit、无新clean scaling或跨seed收益；不要重跑已有候选诊断或自动重投G0。

## 2026-09-04历史入口，动态状态已被上节覆盖

先fetch，再读CURRENT_DIRECTION.md顶部0L9及更新的ACTIVE_WORK_SESSION_20260904.md。
当前唯一已提交GPU作业是G0 12377，2卡117分钟只计价；06:02UTC仍PENDING/Resources，估计香港9月5日12:38:50，
不保证。旧12288启动前失败已保留；新作业不要重投。正式五臂15fits未获预算，不能把G0说成收益实验。
新候选是同一已执行端点集合上的G-reuse→L；两个历史train真实诊断支持3058个新增比较/28tasks，
假设54407806validtokens，但143配置不一致/193来源未明，不能物化成训练池或说有模型收益。
完整来源、双验证、hash与方法限制见LABEL_REUSE_FINDINGS_20260904.md；旧冻结v2和历史开发v1字节不改。
需要同版本producer包+权威来源/config+experiment-closed划分、G0实测和新预算；不得自行过滤问题样本。
最新结构619/960eligible、645physical、316归档、16844endpoints/3910pairs/51tasks，closure=false、config-v2=0。
LATEST=bc9833d834fba65adbbf174301fe968c2c12da4eb8190a8f418ece58d0219456；摄取PID3884166在06:02UTC存活。
学长head=b8d095180415957aa1bab31fa53ead1bba261c03，无新outcome。首次960/Target300/522仍盲态；旧失败链不恢复。
复用候选的30个消费计划、独立重放和6组跨臂前缀检查已完成，receipt5a8ddba9…ff12a88，不再重跑。
L1是Lbudget前37次更新；未来若真实checkpoint绑定验证，可保留15评估单元、以12训练流少约12.9%重复tokens，
未验证真实GPU节约或模型收益。详见results/historical_reuse_execution_20260904/README.md。
没有新clean scaling或跨seed同预算模型收益。六小时窗口06:12:22—12:12:22UTC内原heartbeat已更新并恢复，
只做接力，不以巡检或重复已完成计划冒充实验；正式source/config/split及fit预算门不变。

## 0N. 09:53 动态覆盖（历史记录，已由2026-09-04状态覆盖）

- 当前唯一主线仍是 Decision Corpus + Predictor Benchmark + Audit Protocol；旧 HCE/多保真/probe/score-channel
  effect/K≥1 lookahead/conformal stop 均关闭，不得恢复。
- 2026-08-21 新提交的 COTA（arXiv:2608.21027v1）已经直接实现 exact-prefix branch、same frozen continuation actor、
  0.5B A/B/T pairwise comparator、双顺序一致性与在线 winner-count intervention，并在 9 个 actor×environment 设置报告
  正收益。因此“比较两候选谁会通向更好结果”“tiny comparator 指导强 actor”及 pairwise-to-gate 均不再是我方方法
  novelty；不恢复 K≥1/lookahead。保留边界是 MLE 完整程序 decision corpus、即时 pristine score 与 run/component/
  config/时间前瞻审计，并明确它与 COTA 的 actor-conditioned continuation return 是不同 estimand。
- 联合边界：2024 Guided Evolution 更早已覆盖二元 ML-program discriminator、跳过候选执行及 PAM/PAM-RT 搜索引导；
  CPRD/BoN 又已覆盖 comparison distribution→deployment estimand 的一般理论。COTA 的新增直接重叠是 exact-prefix
  continuation advisor。故 comparator、execution skipping、runtime gate 与“pair construction 决定 estimand”均非我方
  通用 novelty；只保留完整 Python MLE sibling distribution 上的 run-clean、连续分数、盲态时间前瞻领域实证。
- 最新 immutable snapshot=`ad0b624d636cb5e89f94d8887a7abe99f7b9ef6ce77bbde7da704b0275dedb0e`：first-960
  provisional=404/960 runs、11,310 endpoints、2,884 structural pairs、31 tasks；closure=false、label vault=false、
  outcome files=0。target-300 独立支持人口=129 runs/41 archives，remaining=171，truth 未读；两个人口不得混池。
- historical-v11-train↔future identifier-erased audit 已在 5,519 historical endpoints 与 11,299 可 fingerprint future
  endpoints 上完成；5,923,921 exact candidate checks、Jaccard≥0.85 links=`0`，cross-run/cross-task=`0/0`。这是
  benchmark-integrity 正资产，不是 predictor effect，closure 后必须重跑。
- opportunity-yield 404-run 外延按预注册正式 NO-GO：E1/E5 PASS，E2/E3/E4 FAIL；最大单-drop attribution=
  `1.0617531614480789`，删除 dominant OSIC 后反转不保留，run→pair TV 的 yield fraction=
  `0.44105064109821923`。只保留 run-level coverage 与 pair-micro task weight 背离的描述性诊断，不 rescue 机制主张。
- 学长 `dojo-reproduce` 最新精确 HEAD=`61459c0a1248900079dafed7c505afa87e476b40`，没有新的 clean scaling outcome。
  latest future producer 仍未观察到真实 `*.config_v2.jsonl`，旧 archive 禁止回填。
- 已针对该精确 HEAD 交付 config-v2 producer auto-hook patch，SHA-256=
  `56a3e4b61918e1b06830712d418ed27ef5135017eab2b9e833b92c626054c9a5`。fresh Linux focused/full=
  `19/84 passed`（full 另有 1 skipped）；128 个合法变体与独立 v2 exporter 字节全等，4 个非法变体共同拒绝，
  secret=`0/0`。状态仅为 `PATCH_VERIFIED_NOT_DEPLOYED`；学长 review/cherry-pick 后的下一批才可形成真实 sidecar。
- 历史 schema-only compatibility smoke 又用 metadata-only 规则冻结 20 个真实 `dojo_config.json`：20/20 两实现
  row/bytes 全等，覆盖 7 tasks、2 clients、2 solver fingerprints、9 strata；forbidden opens=0、sidecar writes=0。
  这不读取 env/outcome，也不回填 provenance，只排除 synthetic fixture 与当前可见真实 config shape 不兼容。
- 下一动作：保持盲态摄取和 prediction escrow monitor；等待真实 v2 sidecar 后做 source/expected/config composition 与
  support audit。只有 support gate 通过，才提交模型×数据×seed×GPU·时矩阵请求 clean scaling 重训；当前不启动 GPU。

## 0. 15:50 动态覆盖（覆盖下文冲突的旧 monitor/coverage/task-balance 状态）

- task-balance v1 的输入链已确认下游继承 withdrawn prediction matrix：旧 guard 直接读该 matrix 的逐任务
  pair counts，旧 forward 又绑定该 guard 与另一 value-reading matrix。因此 v1 的 `657→645` 算术虽未被证明错误，
  但其“first-960+closure 前严格零 prediction-value access” provenance 已撤回；旧 artifacts 原样保留，只作历史记录。
- structural-only v2 已从独立 structural gate、snapshot-bound accumulator summary、其 SHA-256 绑定的 first-960
  ledger 和 receipt-only independent receipt 重建同一算术。正式 fresh Linux focused/full=`4/1113 passed`；
  baseline/current pairs=`2635/2755`、debt=`657/645`、delta=`-12`，current OSIC share=
  `0.308529945553539`，25% cap 与即时 route-away 遵从仍失败。该结果只恢复结构算术，不恢复 v1 provenance，
  也不是 predictor effect。
- 公开结果 commit=`b90429ddc817c72bae81eadd32f444174326babb`；fresh public post-push worktree 又通过
  focused/full=`8/1117 passed`、结果包 inner manifest=`12/12`、检出前后 `git clean=true`，post-push
  manifest=`5d645f21aa9fe61f88c90c350e75bf3f8acfb5680c7c5d232e18c1943e39fcb4`。分支可能有仅文档后继，
  每次接手仍须先 fetch。
- 14:27 metadata-only 复核：first-960 仍为 366/960 runs、10,683 endpoints、2,755 structural pairs、30 tasks，
  snapshot=`8579d7cd...d9248`；closure=false、label vault=false、outcome/scorer-prediction opens=`0/0`。
- 当前顶层进程：intake watchdog=`2247187`、replacement intake monitor=`2400213`、transition snapshot-chain=
  `2320379`、WL snapshot-chain=`2374019`、receipt-only join=`2374760`、future config-v2 readiness=`2385217`。
  旧 intake PID `2247183` 已被 replacement monitor 接替，不应再作为存活判据。
- 学长 archive source 最新仍是 0824；`myfork/dojo-reproduce` 精确 HEAD=`2b22f3102a2a64cb89ebcae9ede4d8eb72e1430d`，
  `src/mle_critic/docs/outcomes` 仍只有 0812/0817/0820 三批文档。metadata-only 搜索仍未发现
  `*.config_v2.jsonl`，故 future exact-stratum clean scaling 尚不能启动。
- clean-provenance Decision Corpus Evidence Index v7 已从未污染 v5 重建，不读取 v6 或 withdrawn matrix/guard/crosswalk
  路径；14 entries、37 JSON artifacts、3 bound files、434 assertions 全部独立通过。fresh Linux focused/full=
  `10 passed, 1 skipped` / `1127 passed, 1 skipped, 47 warnings`，A/B 均逐字相同，production forbidden opens=0。
  source commit=`a83bebfdb8dcf59bea21a1b84269b2e87bf7a02e`；结果包位于
  `phase1/results/decision_corpus_evidence_index_v7_20260826_a83bebf/`。
- replacement ABC crosswalk v2 已从公开 source commit=`c97371d7433b808933624b706a848a644991139c` 的 fresh
  Linux worktree 通过：24 items、29 clean evidence files，删除 6 个污染 IDs、加入 11 个 clean IDs，人工状态仍固定
  `9/9/5/1`。focused/full=`11 passed, 1 skipped` / `1144 passed, 1 skipped, 47 warnings`；production removed
  evidence/prediction/outcome path hits=0，GPU/API/model-fit/base-update=`0/0/0/0`。crosswalk/independent SHA-256=
  `65cbf6cf...1487ee` / `242ef697...5dd06`，formal manifest=`1552c911...ffcef`；结果包位于
  `phase1/results/agentic_benchmark_checklist_crosswalk_v2_20260826_c97371d/`。这是审计来源修复，不是 predictor
  effect 或 D&B 合规总分。
- 新增的 outcome-blind fuzzy-clone audit 在公开 source commit=`cb368f95c5374fd2ab7448455b3ba3af054d02ec`、
  snapshot=`8579d7cd...d9248` 上 formal 全门通过。10,683 endpoints 中 10,674 可 fingerprint（coverage=
  `0.9991575400168492`）；Jaccard≥0.85 有 7,069 near-duplicate pairs，但全部在同一 physical run：
  parent-child/sibling/same-run-other=`4078/50/2941`，cross-run/cross-task=`0/0`。0.95 下 2,758 pairs 仍无
  cross-run edge。producer/verifier A/B、384-doc brute force、focused/full=`13/1163 passed` 和禁读/密钥门均通过。
  这是“高相似演化严格 lineage-local”的 D&B 正资产，不是 semantic uniqueness 或 predictor effect；closure 后重跑。
- 下一项 historical-v11-train↔prospective-first960 bipartite fuzzy-overlap 已在真实 similarity 前冻结：历史侧固定
  5,816 train rows/5,519 unique endpoints/333 runs/23 tasks；同一 token-5gram、0.85/0.95 定义，成功门为两侧
  coverage≥0.99、future affected≤1%、cross-task≤0.5%、无大跨任务 component 与 256×256 brute-force 一致。
  producer/non-importing verifier 的 14 项合成测试已通过；尚未计算真实 edge。只读 historical identity/code，前瞻
  label/outcome/prediction 仍为零访问；通过也仅是 lexical train→future independence 资产，closure 后重跑。

## 0A. 13:31 历史动态状态（被上文覆盖）

- GitHub 发布分支精确 HEAD=`ff9d42672da138a7bf9283e3704ef741567a2a94`；最终 fresh Linux 已通过
  checked-in inner manifest、focused/full=`24/1109 passed`，复现 manifest=
  `3fa4e2451a6eef55cb9d82e1d53828d7ac303ec4ce02fc64d29b8d68c2ea5384`。
- first-960 仍为 366/960 runs、10,683 endpoints、2,755 structural pairs、30 tasks，snapshot=`8579d7cd...d9248`；
  closure=false、label vault=false、outcome opens=0。
- 旧 coverage matrix 会打开 prediction pair files、解析 margins/selections 并聚合 tie/eligibility；其
  `prediction_values_aggregated=false` attestation 为假。0FT/0FU/0FV 的“预闭包合规 coverage”及 evidence-index v6
  相关项已撤回为 historical-withdrawn。旧 artifacts 保留，但不得再引用 orientation/tie/eligibility 数字。
- replacement receipt-only 正式件已认证 WL/transition 对 2,755 canonical structural pairs 的 exact common support：
  pair-file opens=0、prediction values accessed/aggregates=`false/[]`、identity/orientation 未重开、outcome/effect=0。
  这是 benchmark integrity 正资产，不是 predictor accuracy/effect。
- 新 monitor 精确存活：intake PID=`2247183`、intake watchdog=`2247187`、transition snapshot-chain=`2320379`、
  WL snapshot-chain=`2374019`、receipt-only join=`2374760`。旧 WL/value-reading coverage PIDs `2288648/2288649`
  已在 replacement live 后 TERM，历史输出未删。
- WL exact replay focused/full=`22/1094 passed`，producer 与 one-shot current artifact 逐字相同，manifest=
  `ba152f6171a87cc72ec805c8c4ecacd07bd0462b9a93e063709ce19b798e121d`。
- 学长 `dojo-reproduce` 仍为 `2b22f310...`，没有新 outcomes 文档；archive source 最新仍是 0824。metadata-only 搜索
  未发现任何 `*.config_v2.jsonl`，而我方可见原 run root 的最新 `dojo_config.json` 只到 0813。因此 future
  exact-stratum clean scaling 当前阻断于 producer-side outcome-before config-v2 sidecar，不能启动 GPU 矩阵或把 0824
  事后回填成 exact-stratum。
- 当前下一动作：持续盲态摄取；新 snapshot 由 transition/WL 各自重算后，receipt-only monitor 只通过 receipts 合并支持；
  等学长 future batch 在归档前随包上传 config-v2 sidecar，再做 frozen support audit，并在另报矩阵/GPU-hours 获批后训练。

## 1. 项目目标与当前唯一容器

- 目标：发布大规模、富标注的 MLE-agent 搜索树数据集和 predictor study。
- 优先投稿：NeurIPS Datasets & Benchmarks；ACL R&E/ARR 与 ICML 为后续选择。
- 论文容器：**Decision Corpus + Predictor Benchmark + Audit Protocol**。
- 实验台：`facebookresearch/aira-dojo`。MLEvolve 只作现状对照或快速 sandbox，不能作为公平主实验台。
- agent 底座 LLM 不做微调或 RL-finetune；独立 critic/predictor 可按批准协议训练。

## 2. 当前冻结人口与盲态

### First-960 confirmation cohort

- 唯一确认人口是按预注册时间全序排列的 first-960 eligible physical runs。
- 必须另有独立 accrual-closure receipt；1,500 structural pairs 只是支持门，不是提前停止门。
- 最近一次只读状态为 366/960 runs、10,683 endpoints、2,755 structural pairs、30 tasks。
- 仍为 `PROSPECTIVE_COHORT_COLLECTING`，closure 未成立。

### Target-300 support cohort

- target-300 是 score-channel dual-truth 的独立支持 cohort，保留 boundary-archive overshoot。
- 它与 first-960 estimand 不同，不能混池，也不能因达到 300 自动授权 replay/effect。

### 绝对盲态

- first-960 + closure 前，禁止读取 prospective label/outcome vault、accuracy、search utility 或 prediction values。
- 固定 scorer/WL/component extensions 只能写 prediction escrow。
- 最近一次安全证明：label vault 未打开，outcome files 与 scorer prediction files 的 opened list 均为空。

## 3. 最近确认的正面资产

### 3.1 Structural weight trajectory 与 opportunity-yield 分解

在结果前固定 9 个时间点、Shapley 分解和四个主张门后，对 first-240→first-339 做 outcome-blind 双实现复算：

- run-HHI 增量 `-0.007095167549882084`，pair-HHI 增量 `+0.05270955007531816`；
- run→pair TV 增量 `+0.06200795825017402`；
- 260/280/300/320/339 共 `5/5` 个晚期检查点保留反转；
- `30/30` 个 leave-one-task-out 和删除主导 OSIC task 均保留反转；
- opportunity yield 解释 pair-HHI/TV 增量的 `0.6446576519060645` / `0.5951060527094302`。

单批次稳健性门失败：一个 5-run OSIC drop 的 attribution=`0.9641733656841007`；删除后反转符号仍在，但 pair-HHI
增量只剩 `+0.001888405775504004`。因此只能称“符号可泛化、幅度受批次影响”。证据：
`phase1/results/structural_weight_trajectory_7cda_20260826/`；源码 commit `57561d8`。

精确重加权恒等式为 `q_t=p_tY_t/E_p[Y]`；`TV(p_run,p_pair)=0.337082500713674` 也是任意 `[0,1]` task-level metric
在这两种聚合下的 sharp worst-case 差，即 33.71 pp 结构 leverage。它不是已观察 accuracy 差或 expected bias。

### 3.2 Closure-time opportunity-yield aggregation audit

- outcome 前把 `run → final informative pair` 冻结为两级：`R_t → S_t → I_t`；
- structural opportunity yield=`S_t/R_t`，informative retention=`I_t/S_t`；
- closure 后对每个冻结 arm/contrast 精确分解 structural-yield 与 informative-filter 两段聚合影响；
- 每段和总差同时报告 task-metric range × weight TV 的 sharp bound，但不得称 observed/expected bias；
- first-960+closure、frozen registry、exact common support 和 full task universe 是硬 entry gate；
- alternate weighting、decomposition、subgroup 或 sign flip 均不能挽救失败 primary。

fresh Linux focused/full=`17/1064 passed`，18/18 independent checks PASS，verifier A/B 逐字节一致；源码提交
`f970262`。informative cluster size 理论已有先例，本项目只主张真实 MLE-agent chronological sibling benchmark 中的
outcome-blind 证据与预冻结机器审计。

公开结果包 commit `bad6ec5` 的 post-push fresh Linux 复现进一步为 focused/full=`20/1067 passed`，结果包 inner
manifest 全通过，verifier 双跑与 committed receipt 三者逐字节一致；formal `SHA256SUMS` hash=`06832278...3ee246`。

### 3.3 历史：Frozen task-balance guard v1 的首次 forward audit（provenance 已撤回）

> 本小节保留旧 v1 当时实际报告的数值，但其输入链继承 withdrawn prediction matrix，不能再作为严格零
> prediction-value access 的证据。可引用的 replacement 是本文件 0 节所列 structural-only v2。

- `7cda→8579` 新增 27 runs / 120 structural pairs：27 OSIC、93 non-OSIC；
- frozen debt identity 精确：`657 + 3×27 - 93 = 645`，债务净减 12；
- descriptive pair-HHI / run→pair TV 分别下降 `0.0025179437619996525` / `0.009224557381629972`；
- 但 OSIC share 仍为 `0.308529945553539`，25% cap 失败；route-away immediate action 也明确未遵守；
- 只能称 outcome-blind accounting 与结构改善，不能称 causal acquisition effect、producer compliance 或 method effect。

339 个旧 runs 全部保留、旧顺序为新序列 subsequence、同 ID 行不变；2 个新 runs 因冻结总序插入旧 tail 前，故 raw file
byte prefix 不是正确 invariant。fresh Linux focused/full=`15/1080 passed`，双 producer/verifier 逐字节一致；源码
`76bdaad`，formal hash=`688f8b4f...eb45721`。

### 3.4 Provisional first-960 snapshot-chain 完整性

- append-only source 不推出 chronological first-960 membership append-only；960 后迟到的较早 run 可进入并挤出 tail。
- 旧 WL/transition prior-support-subset 检查会误拒绝合法 churn；prefix 不变时旧 WL 还会误拒绝 stasis。
- 新 verifier 固定 immutable snapshot binding、source set/subsequence/row identity、共同 prediction row exact，以及所有
  增删必须由固定 rank 解释；不改 scorer、activation、模型、预测或 estimand。
- 合成 append/stasis/churn 与篡改反例通过；真实 362→366 shadow 为 added/removed=`4/0`、共同/新增 pairs=`2728/27`。
- 不传 legacy prior 的真实 monitor replay 与旧 `8579` 2,755-row predictions 逐字相同；focused/full=`25/1090 passed`。
- 公开结果 commit `9db2d9f` 的 fresh post-push focused/full=`11/1093 passed`，原 7-entry manifest 全通过。
- churn-safe monitor PID=`2320379`，300 秒×72 polls；旧 artifact 全保留，intake monitor 不变。
- 当前真实 removed=0，不能声称真实 churn 已发生；closure 前 support gate 仍 provisional，outcome/effect 未读未算。

证据：`phase1/results/provisional_first960_snapshot_chain_f21a76c_20260826/`；control commit `f21a76c`。

### 3.5 Structural dependency atlas

对 provisional first-240 与当前 339-run 快照做 outcome-blind 双实现复算：

- run-weighted 最大任务占比：0.1083333333 → 0.0914454277；
- run-weighted inverse-HHI：17.8660 → 20.4595；
- pair-weighted 最大任务占比：0.1714990746 → 0.3123339658；
- pair-weighted inverse-HHI：12.0427 → 7.3666；
- 当前 run→pair task-distribution TV：0.3370825007；
- pair 主导任务相对其 run share 的放大：5.0419625915 倍。

结论：新增 runs 的任务覆盖更均衡，不代表 pair-micro benchmark 的隐式任务权重更均衡。这是
D&B benchmark-design 正结果，不是 predictor accuracy 或 search-utility 结果。

2,635 pairs 来自 2,593 physical decision-parent groups；只有 42 个 pair 超过 one-pair-per-parent
基线，因此集中现象不是少数 parent 大量重复枚举造成的简单假象。

证据：`phase1/results/structural_dependency_atlas_7cda_20260825/`；源码/确定性修复/发布提交为
`e19f5f3`、`b8ea5f7`、`1e3ea6d`。

### 3.6 Outcome 前冻结统一 estimand panel

- generic benchmark headline：pair credit → physical parent 内平均 → task 内平均 parents → tasks 等权。
- 强制并列、不得 rescue：task-pair macro、task→run→parent→pair macro、pair micro。
- 所有 arms 必须 exact common pair support，并先算 pair-level arm difference 再聚合。
- 推断：20,000 task bootstrap，seed `20260901`，固定 SHA index，LOTO，run-cluster sensitivity。
- pair-i.i.d. CI 不能做 headline；alternate aggregation/truth/subgroup 不能挽救失败 primary。
- 既有 scaling 与 component-breadth primary 保持原 authority，不被 generic panel 改写。

证据：`phase1/contracts/DECISION_PREDICTOR_ESTIMAND_PANEL_V1.md`、
`phase1/results/decision_predictor_estimand_panel_v1_20260825/`；提交 `1763030`、`b7e90fd`。

### 3.7 Benchmark checklist 与其他数据资产

- ABC/NAS-Bench-style 24 项 crosswalk：PASS_LOCAL 9、PARTIAL 9、INHERITED_UPSTREAM 5、N/A 1。
- 语料唯一性：12,383-card 审计中 raw 99.47%、AST/skeleton 98.96%，0 个 duplicate group 跨 run/task。
- label-noise ceiling、query/init/execution cost、run-level leakage、撤回链、真实 sibling protocol 已有证据。
- 这些资产提高 D&B 完整性，但不能替代 prospective method effect。

## 4. 方法侧最强但仍未确认的信号

学长 2026-08-20 experiment 内 value-pair 两 seed final mean 随 Qwen3
0.6B/1.7B/4B/8B 为 58.64%/60.67%/62.01%/64.68%；8B 比同数据 TF-IDF 61.18%
高 3.50 pp。decision zero-shot transfer 为 56.25%/56.25%/59.06%/59.38%，8B 仍低于
TF-IDF 59.90%。

只能称探索性 capacity/scaling 信号，因为旧实验存在：

- cross-exact-config mixing；
- shared endpoints；
- 周期性 outer-test evaluation；
- 部分大模型未正常结束；
- checkpoint direction/version 问题。

确认只能使用 future exact-stratum producer、train-run-disjoint dev 选择的新 checkpoint，以及从未触碰的
immutable frozen cohort。任何 GPU 重训仍需先报精确矩阵、总 runs、GPU-hours 与 ETA，获得用户批准。

## 5. 已明确关闭或撤回；不得自动复活

- 旧 `decision_pairs_runsplit` test 与 v11 b0/b1/b2 是同一 2,087-row multiset；旧 Qwen3-4B/8B
  checkpoint 的 frozen scoring 已撤回，禁止定位或运行。
- score-channel 排序优越性已预注册 KILL；execution cliff 只留作 missingness 数据诊断。
- 旧 HCE、TD/RL、多保真、Probe-First、E2-A、early-trace、conformal stop、旧 K≥1 lookahead。
- Parent-conditioned patch critic、source-choice、global→local、component/data scaling 等历史候选均须按
  `CURRENT_DIRECTION.md` 的最新撤回链解释，不能因旧 memory 或标题看起来正面而恢复。
- 不把结构支持、工程通过、prediction escrow、support gate 或调度完成写成 method effect。

## 6. 当前运行与数据摄取

最近一次远端只读状态：

- senior archives：226；最新观察到 `0824/osic-pulmonary-fibrosis-progression-8seeds.tar.gz`；
- latest snapshot：`8579d7cd32091a11089b935217f7189e321b1d623dbaa69233182ba2fedd9248`；
- 226 个 archives 已被互斥分为 128 baseline、86 accepted transactions 和 12 structural rejections；当前 ready/pending=0；
- intake、transition、WL graph、coverage matrix、component closure、target quiescence 六个核心监控存活；
- intake/transition/watchdog 以及 component monitor 均存活；watchdog 使用精确命令行检查确认，而非旧的错误 pgrep pattern；
- WL graph、coverage 与 target 在 `8579` baseline 后重启并存活；target recovery postflight 已逐哈希通过；
- 主 intake 每约 5 分钟轮询，最近 `ready=0`、`rejected=12`、`transactions=86`；
- 用户 SLURM 队列为空；没有 GPU 实验正在运行；本次监控恢复 GPU/API/model-fit 均为 0。

动态状态会过期。恢复时使用 metadata-only 脚本重新检查，不能直接沿用本段数字。

若生产维持约 60 eligible runs/day，剩余 594 runs 约对应 9.9 个生产日；这不是日历承诺。

## 7. 学长最新分支状态

- `dojo-reproduce` 最近观察到 `2b22f3102a2a64cb89ebcae9ede4d8eb72e1430d`；
- 新增 RL-judger message 构造、上下文统计、Qwen2.5 0.5B/1.5B/3B/7B mixed
  decision/value full-FT 脚本，以及避免复制/缓存完整数据的 prompt 约束；
- 没有新的 outcome 文档，不能称新 scaling 结果；
- train/test 参数当前指向同一 runsplit 文件；源码审计确认普通模式会按 `intask_split` 分流，因此路径相同本身不构成行泄漏。
- 但 outer test 被作为 Trainer `eval_dataset` 每 10 steps 观察并参与 best-checkpoint 保存，故只能作 dev；旧 scaling 仍是探索性，
  不能称 untouched frozen confirmation。LOTO 还会绕过 `intask_split`，必须与 run-clean frozen-test estimand 分开。

贡献归属：语料生产来自学长；structural dependency atlas 的问题、代码、双实现复核和 benchmark 主张来自
我方；0.6B→8B 探索性 scaling 来自学长。

## 8. 仓库、路径与分支

- 本地 worktree：`C:\Research\New\my_project\MLEvolve\aira-dojo-codex-20260813`
- 本地工作分支：`codex-prospective-decision-v1-20260814`
- 发布分支：`myfork/phase1-value-critic`
- 最近已验证的公开结果包：`bad6ec5428c62b6a213b0d75fa0d1e58d858b5d4`；恢复时最新分支 head 仍以 fetch 为准；
  contract source=`f97026221e099c11fa1ca8f2c13a95c389bea743`
- task-balance forward formal source：`76bdaad398da675aa62614260d63a019594f172c`
- GitHub：`https://github.com/SuperSumanov/aira-dojo-noise-robust`
- 远端 alias：`linux5`
- prospective state：`/research/d7/spc/yzyang4/prospective_decision_v1`
- senior archive metadata source：`/research/d7/spc/yzyang4/external/senior_data/mle`
- 远端 Python：`/research/d7/spc/yzyang4/venvs/exp/bin/python`
- `codex_tmp/` 是保留的未跟踪操作文件，除非明确判断，不删除、不整目录 stage。

## 9. 安全与远端硬规则

- API keys 只放远端 `.env`；不在聊天复述，不写本地、memory、日志或 Git。
- 学长 tar archives 可能含原始密钥；只读 metadata/listing。任何内容读取前必须先做 blind redaction。
- push 前执行 staged filename secret scan：
  `git diff --cached --name-only | grep -icE 'env|key|token|secret'`，并做内容扫描。
- 非交互脚本先 `source "$HOME/env_setup.sh"`，之后再 `set -u`。
- 所有 SLURM 命令必须 `export SLURM_CONF=/opt1/slurm/gpu-slurm.conf`。
- QOS 上限 4 jobs / 8 GPUs；避开 `projgpu7`、`projgpu8`、`projgpu33`、`gpu36`、`gpu38`。
- SSH 内层引号会被剥；复杂逻辑写成 LF 脚本、scp 到远端再执行。
- Windows 不跨 shell 拼接删除/移动命令；任何递归删除/移动前核验绝对路径。
- commit 标题若含数字，只能复制程序打印并验证过的数字，不能心算。

## 10. 实验纪律

- 每个长实验先完整执行 13 项 preflight，给目标、硬件/软件、固定项、成功/kill gate、矩阵、总 runs、
  GPU-hours 和 ETA。
- 新代码路径先做 CPU/tiny smoke；声称改了旋钮必须从 run artifact 反验。
- 保存 commit、版本、全部 seed、完整命令/config/environment；一行一个 run 写 CSV。
- 报 task/run 分解、median、跨 seed 方差和 clustered inference；不只报均值或单次数字。
- 训练期禁止访问冻结 test；任何外部 evaluator 使用 pristine code 与访问审计。
- 保留失败、INVALID、KILL 与撤回记录，不能只留下漂亮结果。

## 11. 恢复时的安全顺序

1. Fetch `phase1-value-critic` 和学长分支，读取 `CURRENT_DIRECTION.md` 顶部最新日期段。
2. 只读检查 Git drift、archive metadata、latest snapshot、六个核心 monitor、intake log 与正确 SLURM 队列。
3. 不打开 tar bytes、outcome/prediction vault 或旧 checkpoint。
4. 若有新 archive，让既有 append-only intake 与 stability gate 处理，再报告精确增量。
5. 没有 first-960 + closure 时，优先做 outcome-blind benchmark/integrity 工作；不要制造新的后验 effect 假设。
6. 如需 GPU，先提交精确实验矩阵和预算给用户批准；当前没有自动授权的 GPU effect 主实验。
7. 结果与代码完成后做 fresh Linux reproduction、独立 verifier、secret scan，再 commit/push。

## 12. 关键入口

- 唯一方向：`phase1/CURRENT_DIRECTION.md`
- 学长建议：`phase1/ADVISOR_DIRECTIVES.md`
- 给学长的近期汇报：`phase1/实验记录/2026-08-26/近期进展汇报_2026-08-26.md`
- 结构时序分解：`phase1/results/structural_weight_trajectory_7cda_20260826/README.md`
- 重加权恒等式：`phase1/实验记录/2026-08-26/OpportunityYield_重加权恒等式与影响上界.md`
- structural atlas：`phase1/results/structural_dependency_atlas_7cda_20260825/README.md`
- estimand panel：`phase1/results/decision_predictor_estimand_panel_v1_20260825/README.md`
