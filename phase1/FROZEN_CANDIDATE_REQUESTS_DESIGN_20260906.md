# 同批候选信息隔离：可选请求层原型，不是在线搜索结果

2026-09-06。服务于已批准月度路线的“先锁模型，再测真实选择收益”准备，
不替代当前full G-reuse→L四fit主线，不改现有AIRA默认solver、算子、scorer或冻结协议。
此处没有运行API、GPU、MLE任务或读取真实/保护数据。

## 要解决的实际问题

历史MCTS会逐个生成、执行、分析、加入journal。后续同父节点可能看到前一个候选的执行反馈。
这样的历史siblings不自动等于“尚未执行时同时可选择”的候选池，不能仅凭离线重排声称节省执行成本。
另外，现有`improve_op`会原地shuffle `cfg.available_packages`；只复制parent ID还不足以锁定实际prompt。

新`frozen_candidate_requests.py`提供显式、可选的准备层：

1. 同一批次从同一份过去状态复制cfg/journal/parent对象图；每个槽位再次独立复制。
2. 给原`improve_op`注入一个不访问网络的捕获器，在任何生成调用前渲染全部system messages。
   包顺序等准备随机性使用独立登记的slot seeds，准备后恢复调用者Python RNG。
3. 把实际messages、解码参数和外部状态/算子/生成器绑定写入不可变请求；先验证全部请求，再锁批次。
4. 每槽位先持久化intent再调用显式传入的client.query。即使返回后真实journal被修改，后续请求也不能重渲染。
   请求/返回只在安全回执中显示哈希。失败或不明远端完成不自动重试。

这层不执行候选、不选择程序、不改变agent底座，也不提供新的ranking方法。
现有默认MCTS未接入；未来统一batch-random、廉价selector、critic三者时才会使用共同生成规则。
原逐节点即时反馈MCTS若另作比较，必须标为整体系统基线，而非“只改selector”的因果对照。

## 已覆盖与尚未覆盖

本地synthetic测试覆盖：live journal/parent/config/参数变动不能污染已冻结请求；
所有render先于首个query；客户端修改messages不能改变之后的槽位；RNG恢复；
失败不重试；后面槽位的坏请求在首个调用前拒绝；拒绝带凭据/路由、未审核参数、批内n>1及NaN。
另用`ef19d100ac6cb1a747c332eb1b8596051f47a695`中**未修改的improve_op函数AST**核对逐槽位query数据，
原函数blob SHA `b0b9bc561f26682ce84701287bd3c92a57b58ed37d2664a31eae4b56c5aab5e0`。
此测试用synthetic对象和格式化stub，不能冒充完整Dojo依赖、真实Jinja模板或完整agent验收。

另提供真实Dojo环境的`test_frozen_native_template_bridge.py`：真实Node/Journal、OmegaConf、
improve_op、JinjaPrompt及GenericLLM.__call__，只把client替换为无网络记录器并绕过其构造函数。
它比较三个既有complexity分支的实际messages/解码kwargs。首轮实际Linux检查30通过/3失败：
三项原生桥接均在可选provider SDK litellm缺失处停止，未执行到请求比较。此失败原样保留。
后续在测试拥有的client边界提前替换factory import，仍执行原生算子、Jinja和GenericLLM.__call__，
不安装SDK、不调用真实factory；该测试从不声称provider SDK/routing已经验收。修订后仍待远端执行。
该检查也明确保留接口差别：此层返回原始usage，未提供GenericLLM的cumulative_num_llm_calls包装。
原模板写死1RTX3090/6CPU；测试匹配这些字面值不代表未来agent实际资源已匹配。

解码参数范围是本原型主动选择的窄契约，不是声称所有供应商支持同一范围；不支持的参数或新范围必须先审核。

上线前还必须实际完成：

- 合格数据/状态授权及真实resource与渲染prompt的一致性；外部传入SHA不是自证资格。
- 原生模板、client routing/model/decoding固定与真实wire核验；准备seed不保证供应商解码可复现。
- 每槽位解析失败/内部API重试政策、费用和截止时间。当前包装器不替代client内部重试上限或进程级timeout。
- 批次生成、critic推理、全长执行、分析/状态准备的总预算；没有1/6执行或多保真。
- 批次结果与选择锁的持久化、未知外部调用的人工核对、进程退出/重启行为；当前没有自动resume入口。
- 多步AIRA真实接入、多seed公平对照和合格的独立评价。不能复用另一策略后续轨迹充当反事实。

当前选择：先把这个最容易造成虚假收益的请求顺序问题隔离，保留可接入接口；
不为等待语料或磁盘配额而扩张新的方法网格，不报告任何准确率、regret或搜索收益。
