# Hindsight 实现说明

处理流程、运行命令和树格式见 `hindsight.md`，设计演变见 `hindsight_history.md`。

## 1. Model client

实现文件：`src/mle_policy/src/data/hindsight/client.py`。
客户端负责模型通信、请求参数、返回格式校验、重试与缓存；episode 选择、提示词
内容和是否剪枝由 `__main__.py`、`regenerate.py`、`prompts.py` 负责。

按处理目标组织代码：`__main__.py` 放单树审查重写与批量读写入口，`regenerate.py`
放一次回答的 hint 提炼、完整生成和节点构造。`experiment.py` 复用同一套回答生成
函数做对照。`hindsight/helper.py` 保存回答解析 `parts`、缓存版本及 `atomic_json`，
hint 注入 `inject_hint` 与生成逻辑放在 `regenerate.py`。
树操作、模型通信和提示词各自保留独立模块。通用数据工具放在 `data/helper/`：
`align_splits.py` 对齐分组切分，`filter_positive.py` 筛选正 advantage，`merge.py`
合并数据。这些工具直接写结果文件，JSON 报告使用普通 `json.dump`，不依赖 hindsight
核心模块。
生成产物的离线验收在 `test/verify_hindsight.py`，由测试及 `verify.sh`
调用，核心生成代码不依赖测试目录。

### 1.1 按用途提供入口

| 方法 | 调用位置 | thinking | 输出上限 | 返回结构 |
| --- | --- | --- | ---: | --- |
| `audit(messages)` | `__main__.rewrite` 的初轮审查 | 开启，medium | 不指定 | `reason`、`untrustworthy` |
| `audit_review(messages)` | `__main__.rewrite` 对初轮拟拒绝项复核 | 开启，medium | 不指定 | `reason`、`untrustworthy` |
| `debug_hint(messages, part=False)` | `regenerate.extract_hint` 提炼调试经验 | 关闭 | 8192 | `hint` |
| `improve_hint(messages, part=False)` | `regenerate.extract_hint` 提炼更好方案的经验 | 关闭 | 8192 | `hint` |
| `generate(messages, generation)` | `regenerate.regenerate` 生成完整 policy 回答 | 由 generation 指定 | 无默认值，继承原 operator 显式设置 | 完整回答、usage、缓存键、model |

前四个入口温度为 0.2。hint 的 `part=True` 表示长轨迹的分段提炼，使用独立缓存
阶段 `debug_hint_part` / `improve_hint_part`；最终汇总使用不带 `_part` 的阶段。
debug 与 improve 的任务内容由各自提示词输入区分，目前共享相同的 hint 请求参数。

公开入口各自确定请求设置，再交给内部 `_json_result` 处理通用机制。
这个内部方法接收明确的校验函数、缓存目录、版本和可选 schema，不根据 stage
猜测业务类型。`_hint` 复用两种 hint 共有的请求设置。
`generate` 单独校验完整回答，不经过 JSON 结果通道。

`max_tokens` 直接传给服务端；客户端不另设 thinking budget，也不根据
`reasoning_effort` 计算 token 数。对于本流程预期的 Qwen/vLLM 服务，生成预算
由思考和最终回答共同使用，输入 prompt 另外占上下文窗口。
审查和复核不主动设置输出上限；完整生成只保留原 operator 已记录的显式上限。
省略字段后仍由服务端的默认生成设置及剩余上下文空间决定可用输出预算。
hint 提炼仍保留原有 8192 上限及关闭 thinking 的设置，本次调整针对审查和完整生成。

### 1.2 复用 dojo 的通信实现

底层使用 `dojo.core.solvers.llm_helpers.backends.open_ai.OpenAIClient.query_raw`。
通过 `asyncio.to_thread` 调用同步 SDK，信号量限制同时执行的请求数量；HTTP 超时
为 1800 秒，关闭环境代理读取（`trust_env=False`）。SDK 自带重试设为 0，重试
统一由这里管理。调用方用 `await close()` 关闭底层 client。

`request` 把 `chat_template_kwargs`、`top_k`、`min_p`、`repetition_penalty`
移入 SDK 的 `extra_body`，其余参数直接传递。返回原始响应字典供缓存和检查使用。

### 1.3 校验与重试

`validate_audit` 检查返回对象包含非空字符串 `reason` 和真正的布尔值
`untrustworthy`；`validate_hint` 检查非空字符串 `hint`。这两个校验器不检查
事实正确性，也不判断审查理由与布尔决定是否一致。

hint 首次请求使用 `json_object`。若返回不完整、JSON 解析失败或字段
校验失败，保存错误记录，再附加一条格式修正指令，并启用严格 JSON Schema。
`HINT_PROPERTIES` 描述这种重试所需的字段类型和必填项。
它们不是每次调用从一开始就启用的 schema。

初轮审查和复核从首次到重试都不加 JSON grammar；返回正文含 `</think>` 时，去掉
此前思考再解析 JSON。若服务端分开返回 `reasoning_content`，仅解析正文中的 JSON。

每次最多请求三次，重试前等待 1 秒、2 秒；HTTP 400/401/403/404 直接报错。
`finish_reason` 必须是 `stop`，`length` 也算失败。目前重试不增加输出上限。
有服务端响应的 JSON 调用失败会保存请求与响应；网络异常没有响应时仍会重试。

`generate` 不加 JSON grammar；校验完整 thinking、plan、Python 代码格式，合并
服务端分开返回的 `reasoning_content` 与正文。失败重试不改 prompt 或采样设置。
代码格式合格不代表代码执行正确，该客户端不运行生成代码。

### 1.4 缓存与版本

每次逻辑请求用 `identity = {version, stage, request}` 标识；排序序列化后计算
SHA-256，保存在 `<cache>/<stage>/<digest>.json`。身份包含模型、完整消息和生成
参数，但不包含服务地址；因此同名模型服务换了权重时，应更换缓存目录或模型名。

审查两入口使用 `audit_cache`（未指定则使用普通 cache）及独立常量
`AUDIT_CACHE_VERSION=4`；hint 和完整生成使用 `helper.VERSION=8`。开启初轮审查
thinking、取消审查上限及完整生成默认上限后，更新两个版本，使旧审查缓存和旧
整树完成报告失效。同目录重跑会按新设置处理，已有数据不会在修改代码时自动重写。

JSON 缓存保存 `identity`、成功尝试的 `attempt_request`、解析后的 `result` 与
原始 `response`。缓存键按最初请求计算，修正格式后的请求记录在 `attempt_request`。
完整生成缓存保存 `identity`、规范化后的 `result` 和原始 `response`。
命中缓存后重新做相应校验，不再调用模型。

失败记录在普通缓存目录的 `errors/`，不随 `audit_cache` 改变。
hindsight 的缓存与报告使用 `hindsight.helper.atomic_json`：先在目标目录写临时文件，
写完并关闭后再替换目标。通用 `data/helper/` 工具使用普通文件写入。
即使只有一个写入者，进程中断或序列化失败也不会把原来的完整缓存截成半份 JSON；
首次写入尚未完成时，目标文件保持不存在，重跑仍会正常发起请求。
异常退出可能留下临时文件，但缓存读取只按确定的哈希路径取文件，不会命中它。
这不是文件锁，也没有执行 fsync 来保证断电持久性。
并发信号量控制实际调用，
没有对相同缓存键做跨任务或跨进程加锁；多个进程同时发起相同请求仍可能重复调用。

### 1.5 测试和检查输出

`test/test_hindsight.py` 用 HTTP mock 覆盖全部入口及 hint 分段模式的参数、格式
失败后的重试、schema 差异、缓存阶段与命中，以及跨输出目录复用审查缓存。
主流程和 experiment 的离线测试检查调用链及来源节点，完整生成另测截断重试。

experiment 的 `hint_trace.json` 和 `rewrite_trace.json` 便于查看逻辑输入输出；
其中的输入不一定等于格式修正后的重试请求。需要核对实际成功发送的 JSON 请求时，
查看对应缓存的 `attempt_request`，失败过程查看 `errors/`。
