# ForeTS 真实端到端探索：首轮配置与实际缺项

2026-09-08建立，2026-09-09更新，按用户转达学长反馈执行。此页是待完成的探索运行表，不是已开跑或收益报告。

## 要回答的问题

固定生成器、完整执行规则和实际资源，critic 选择能否比共同 batch 规则下的随机选择取得更好的 MLE 结果？
复用学长 ForeTS，不把“加入 critic/top-k”归为我方首次方法。训练/语料来源不完美可以在探索中明示，
不要求补造旧环境；但保护集不开放，探索看过的数据不再作为未触碰确认。

## 已落实

### 最新状态：有界作业入口（0L122）

0013继续接0010→0011→0012，tree059328196ca359965732308eebf7e57eb9c9ecd8。
step时间/worker墙钟/每run预算初始化与归档、环境导出禁用、重复启动拦截已接入；7项新CPU检查通过。
首次预算模块冷启动超过8秒且0intent，保留失败诊断；将同一逻辑移到轻量utils模块后原时限通过，不导入litellm/torch。
这是人工输入与无害进程测试，不是真Slurm强制结束/GPU/真实API/e2e验收。归档无法保证覆盖SIGKILL/节点故障。
只读Slurm确认KillWait300秒/OverTimeLimit0，故9GPUh只能称名义270分钟2GPU；若加终止宽限为9.166666666666666GPUh，
也不保证故障/不可中断IO下绝对结束。官方时间语义：https://slurm.schedmd.com/srun.html。
提议worker1740秒、step30分钟、剩余时间至少2130秒；真实矩阵和费用仍待冻结，测试cap40次请求不是批准预算。
源码仅隔离forets-bounded-worker-20260909-xobxuu/source-v2；tar SHA256
fd34ba0e454d90b3f9857882269ee1aa9fcf52b2ffe004715bff63c1d614196d。
后续一次真实8B验收须单独给资源预算/预检；接口对应关系及价格仍等待，不发送现有key试错。

### 最新状态：共享请求额度与完整两臂配置（0L121）

0012接0010+0011；完整tree49fd8698e6a5a3377224a2d92c65f354cb1eefa0。
四算子统一有界请求，并要求同一run预算数据库；节点本地持久intent在dispatch前计数，
失败、超时、取消不退款，客户端重建不重置，缺库/损坏拒绝。并不是NFS/跨allocation恢复方案。
新6项CPU检查通过：真实GenericLLM四算子共享额度、多进程竞争无超额、8份完整Hydra配置4组只差selector。
配置准备模块forets_pilot_plan.py的输出token上限/请求deadline须显式传入；本次仅以8192输出token、120秒验证结构。
没有生产费用价目，真实max_attempts未定；不能把测试用7次额度或cost=null当批准预算。
Slurm worker每run独立初始化/归档预算库、step硬限和真实8B GPU验收仍未接入；无真实API/任务/模型收益。
source-only tar SHA256 31cb7f9d9bab502e7cc37fcd041fd2a0ba33b6411c05b150d1c61ec054639b40。
目录/research/d7/spc/yzyang4/forets-runbudget-20260909-cyPIf2；回执results/forets_bounds_20260909/run_budget_checks.json。
学长API对应关系仍等待，不重复催问；不要按重复日志行数计请求，使用DB或attempt_id去重。

### 最新状态：离线loader与065b上游集成（0L119，覆盖以下历史描述）

- 模型接收不再阻塞。0009新增`offline_base_dir`/`--offline-base-dir`，从本地固定config/tokenizer和完整raw state加载，
  不需第二份base pretrained权重。10项CPU检查通过；其中tiny真实Qwen3 seed6/7的state/前向/RewardScorer与参考一致。
  真8B只验证400键/形状及分词器，不是8B加载/推理。中断的SSH退出1，但完整回执已落盘并取回，进程已结束。
- 最新学长commit `065b0fbaa89e0eb663f2834ec768081f5d56394d`；新增6文件先凭据形状扫描0。
  集成配置继承/独立未选日志/JSON解析改进。旧补丁冲突不强套，最新入口为独立累计
  `0010-ForeTS-cumulative-for-065b0fba-20260909.patch`，不用再叠旧0005—0009。
- 完整tree `83ffe50f517dde409baba3a73e69ef5872dab1ac`；独立应用复建完全一致。
  Dojo source-only tar SHA256 `9b890878a5d5597582ca216ff6dc061e0d1e965e6fee415e8236ca3988897444`，
  部署于`/research/d7/spc/yzyang4/forets-e2e-dev-20260908-IMuJx6/upstream-065b0fba`。
  critic两个文件在同一根目录`critic-offline-v1`中，与新tree完全相同；未覆盖生产源码或学长分支。
- 修前实际源码人工输入：两臂首次执行前中断重试均把3个未选候选导成6条；JSON修复会改动字符串内`, }`，并记录原响应。
  修后8项定向检查通过：导出幂等、改变已有导出内容则拒绝、执行树不含未选、字符串内容保持/schema拒绝，
  实际Hydra在seed6/7下都只差selection_policy，继承MCTSSolverConfig且uct_c=0.25。
  测试使用真实ForeTS/MCTS/Journal/后端解析/配置代码，生成器、critic响应和task返回为人工替身，无实际API或任务。
  初次测试因测试自身未关闭SQLite读连接触发NFS清理异常；显式关闭并改用/tmp夹具后通过，未改生产ledger。
- 回执：`offline_loader_cpu_check.json`、`upstream_065b_before.json`、`upstream_065b_after.json`，位于本页同名results目录。
  不重跑已完成loader/旧矩阵。这些结果是接入修复，不支持模型变好、scaling或端到端胜出。

用户正等学长确认API对应关系；不重复询问。采纳新文档的轻任务/免费endpoint调试建议，但不可擅自换路由/模型。
真实8B GPU推理、外部硬停止和准确费用表尚未完成；下面8runs/9GPU小时仍是条件规划，不是已启动或最终预算。

### 用户提供模型链接后：实际权重已接收（0L118）

Qwen3-8B.tar.gz完整下载12051153651 bytes（312.1秒），SHA256
`01dda87a6dfaf77a6c454efcb1a9d5a88964f11f7b4dd88edea1f331be84f1d6`。下载前对实际目标预留空间成功，
文件只落远端，未改生产目录，私人下载链接不入公共Git。仅提取模型必需文件，解压338.4秒，exit0；
中途研究盘I/O等待，不是GPU排队。实际checkpoint绝对路径：

`/research/d7/spc/yzyang4/forets-critic-incoming-20260908-3lcjjcwq/unpacked/Qwen3-8B_reward_seed1/checkpoint-100`

唯一提取文件model.safetensors为15136866890 bytes，SHA256
`bb0c6a1801cf0a753bb1f8aa1c923f9fcc7fff81fd654ae9d3a932ee280dfb74`。
格式头400 BF16 tensors，含backbone.*及head.weight [1,4096]，对应上游原始Trainer checkpoint分支；
未读取tensor数值或评测结果，另2个非必需文件未提取/解读。包内没有rm_meta/config/tokenizer。
已按学长确认的底座，单独下载公开config/tokenizer_config/tokenizer共7042052 bytes，固定revision
`49e3418fbbbca6ecbdf9608b4d22e5a407081db4`，位于incoming目录的base-metadata。
默认环境缓存中这些文件原本均缺，不等于遍历所有自定义缓存；未重复下载任何底座权重。

这解决了模型位置与文件接收，并非实际模型load/forward或e2e收益。上游raw loader会先from_pretrained底座权重；
下一步接入完整state从固定配置构造并strict加载，避免重复下载，再做有界GPU集成。该新入口本轮未实现/验证。
API路由、硬限与最终预算仍待完成；不恢复冻结确认资格或原严格四fit。回执在本页同名results目录的critic_*.json。

### 09:24 UTC后的运行修复，覆盖下方旧集成版本

学长新head `c428549973beb4a3289bf669675fac13f64e63b8` 修复MCTS._analyze未等待coroutine的错误；
文档critic示例改1GPU/5workers，但没有新的checkpoint路径，不证明8B在我方卡上已运行。
在该head上应用现有0005/0006/0007后tree为22ed3b437bdd027cba0759c001261538f50d046b；配置与选择器不变。
实际Linux定向检查另发现我方request_guard接入引入循环导入：analyze→GenericLLM→ForeTS→MCTS→analyze。
初次从分析模块导入时ImportError，先前ForeTS-first导入没暴露。新增0008使包级ForeTS延迟导入，保留公开接口。
当前应使用 **c4285499 + 0005→0006→0007→0008**（不叠0002/3/4），集成tree
`b146ac436fbd6616ed7573ee48df5eb5140dfe17`；源码在原隔离目录的 `upstream-c4285499/` 子目录，旧副本保留。
两个全新CPU进程分别从analyzer/solver入口导入，均通过实际_analyze→analyze_op配人工异步LLM的定向检查：
旧TypeError复现，新等待/结果登记正常，异常保留不伪装成功。无真实API/模型/数据，不是e2e验收。
执行脚本scripts/check_forets_analyze_c4285499.py，简要结果results/forets_e2e_pilot_20260908/analyze_regression.json。
外部模型/路由缺项未变，不重复既有矩阵；下面的6f7旧tree仅记录此前配置检查。

- 学长 head `54929de4ac92cb1a1a2fd75e31843a223c10c859`，加我方0005→0006→0007，实际集成 tree
  `6f7e650e5ecfd8dac7369a954ac16e01f258daa1`。仅224个Dojo源码/配置文件打包，无outcomes、训练数据或凭据。
- 独立远端目录：`/research/d7/spc/yzyang4/forets-e2e-dev-20260908-IMuJx6`；未改活动生产目录/学长分支。
  包SHA256 `4b97d7113c6c5188d29261fdd8f3d96e415b3fc4387dc65806fe61da01f7114d`，1136640 bytes。
- 用实际 `/research/d7/spc/yzyang4/venvs/aira/bin/python` 导入了真实 `dojo.solvers.fore_ts.fore_ts.ForeTS`，
  两臂 Hydra 配置实例化/validate 通过，solver配置差异仅 `selection_policy`。没有构造solver执行对象、
  加载模型、请求API、读取任务数据内容或启动GPU。不是完整端到端验收。
- 环境模块事实：aira-dojo0.1.0、Hydra1.3.2、LiteLLM1.65.7、Jupyter client8.9.1、MLE-bench1.0.0；
  aira主控环境的Torch是CPU版本，不能作为critic GPU环境。exp环境可见Torch2.11.0+cu128/Transformers4.57.1，
  但未加载8B模型；模型环境能否实际服务仍待一次有界GPU集成。
- 四个公开命名的开发候选任务目录都存在。选择leaf/ spaceships这一小规模起点依据已准备好和公开训练文件体积，
  不是按分数筛任务：leaf训练CSV1481500 bytes，spaceship724849 bytes；另两tabular任务分别493166255/283303880 bytes。
  只查public顶层文件stat、private目录存在性，未读数据内容；图像/额外目录总容量未统计。
- 现成19717783552-byte执行镜像存在；本轮未重复镜像哈希或隔离测试，仍需实际运行接入后才称可用。

## 首轮拟定矩阵（未提交）

|项|探索设置|
|---|---|
|任务|leaf-classification、spaceship-titanic；都是已知开发任务，不称新任务泛化|
|seed|6、7|
|两臂|uniform_random / critic_topk_random|
|候选与执行|每批4个候选，critic top-2中选1个；random全4个中选1个|
|执行|每程序统一300秒完整上限；最多4次执行，debug计入，max_debug_depth=1|
|重试|max_llm_call_retries=2，critic_max_attempts=1，launcher.max_retries=0|
|搜索|软限制1800秒；必须补外部硬停止后，才能按以下费用上限提交|
|资源设想|同节点2GPU，1卡critic/1卡worker，串行；两臂都计入整个已分配资源|
|底座API|学长配置默认deepseek/deepseek-v4-flash-0731 via OpenRouter，尚未确认可用；不得自动换模型|
|critic|现成Qwen3-8B_reward_seed1/checkpoint-100已收到，路径见上；不使用G0工程checkpoint，不恢复已撤回冻结确认|

矩阵共8个agent runs。若每run实际硬限30分钟、两卡，并额外共30分钟两卡初始化/debug，
条件总cap为8.0+1.0=9.0 GPU小时；这是计算值，不是已批准/已实现的硬预算。现有solver软限会在step后检查，
不能单靠该字段保证不超时。API美元上限待正确路由、价格和用量控制确定，不能把逻辑调用数当实际费用。
本轮故意不先分配GPU空等。取得模型/路由后先完成硬限与准确费用表，再在同一有界分配内做真实集成。

两臂沿用相同包列表/生成/分析规则。共同初始seed不保证独立API调用产生相同候选，更不保证搜索分叉后同池。
leaf seed6随机先、seed7 critic先；spaceship seed6 critic先、seed7随机先，缓解运行顺序影响，仍不当大样本确认。
同执行次数仅为辅助；报告最终提交的任务成绩、有效提交/失败、整体墙钟、分配GPU小时和实际API用量。
随机臂闲置的第二卡照计，这不是资源最优随机基线的生产成本证明。失败和未知成本不当0分/0成本。
300秒是本次新声明环境的统一完整执行上限，不是按早期结果续时的多保真方案，也不声称复现历史时限。
后续确认再扩任务/seed和强基线；这8run只能判断是否值得继续，不能选最好seed或最佳跨run提交报喜。

## 当前剩余接入项（模型下载位置已解决）

1. 权重已接收，不再索要链接或重传。底座Qwen/Qwen3-8B-Base、上下文16384由学长确认，
   用于现成旧critic的新探索，不等待RL/重新训练，不称最佳模型或干净scaling；不恢复具体已撤回冻结确认。
   本地加载入口的CPU检查已完成（0L119），接下来是有界GPU验证；结构符合不代表真8B运行成功。
2. 实际LiteLLM backend使用模型专属 `PRIMARY_KEY_...` 或 `PRIMARY_KEY`。远端.env有后者，
   没有该OpenRouter模型专属变量，也没有OPENROUTER_API_KEY；fallback不呈OpenRouter凭据形状，
   .env中未找到可说明路由的URL/ENDPOINT字段。形状不是凭据有效性验证，禁止把它试送错误服务。
   用户已回复“我等一下学长回复”；不再询问相同问题。未回显/传输密钥、未发账户或推理请求。

本轮小失败：打包检查最初漏允许顶层src目录；随后辅助导入写错ForeTSSolver类名，改为实际ForeTS。
两处均已修正；Hydra仍提示上游default_runner缺_self_，当前真实配置成功，不为此展开框架重构。
不要重跑G0/旧选择器测试/语料预算计算。外部项未回时，不轮询同一路径充当进展。
