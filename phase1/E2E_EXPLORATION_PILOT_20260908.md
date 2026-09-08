# ForeTS 真实端到端探索：首轮配置与实际缺项

2026-09-08，按用户转达学长反馈执行。此页是待完成的探索运行表，不是已开跑或收益报告。

## 要回答的问题

固定生成器、完整执行规则和实际资源，critic 选择能否比共同 batch 规则下的随机选择取得更好的 MLE 结果？
复用学长 ForeTS，不把“加入 critic/top-k”归为我方首次方法。训练/语料来源不完美可以在探索中明示，
不要求补造旧环境；但保护集不开放，探索看过的数据不再作为未触碰确认。

## 已落实

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
|critic|等学长提供现成可访问位置；不加载已撤回旧checkpoint，不使用G0工程checkpoint冒充有效critic|

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

## 现在真正等外部的两项

1. 学长文档的相对示例 `outputs/augmented_mle_critic/Qwen3-8B_reward_seed1/checkpoint-100` 在我方repo下不存在。
   需要共享绝对路径或可访问下载地址，以及底座/上下文设置。已发简短问题，不要求补历史审计。
2. 实际LiteLLM backend使用模型专属 `PRIMARY_KEY_...` 或 `PRIMARY_KEY`。远端.env有后者，
   没有该OpenRouter模型专属变量，也没有OPENROUTER_API_KEY；fallback不呈OpenRouter凭据形状，
   .env中未找到可说明路由的URL/ENDPOINT字段。形状不是凭据有效性验证，禁止把它试送错误服务。
   已询问正确服务地址，或请学长直接在远端0600.env安装对应凭据；未回显/传输密钥、未发账户或推理请求。

本轮小失败：打包检查最初漏允许顶层src目录；随后辅助导入写错ForeTSSolver类名，改为实际ForeTS。
两处均已修正；Hydra仍提示上游default_runner缺_self_，当前真实配置成功，不为此展开框架重构。
不要重跑G0/旧选择器测试/语料预算计算。外部项未回时，不轮询同一路径充当进展。
