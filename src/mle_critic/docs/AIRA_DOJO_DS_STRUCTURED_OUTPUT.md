# DeepSeek 结构化输出：Dojo 实际发送的 payload 及风险

这里的问题位于原仓库的通用 LiteLLM backend，不是学生为 DeepSeek/HCE 新增的代码。`git blame` 显示下述逻辑来自 upstream 初始版本。学生后来增加 metric marker/正则 fallback，主要是在绕开这个 backend 在 DeepSeek 上不稳定造成的后果。

## 调用链

MLE-bench 的 analyze operator 先定义 JSON Schema，要求返回：

```json
{
  "is_bug": false,
  "summary": "...",
  "metric": 0.8123
}
```

`src/dojo/core/solvers/operators/analyze.py` 将 schema 和函数信息传入 `GenericLLM`：

```python
return analyze_llm(
    query_data=analyze_data,
    json_schema=schema,
    function_name="submit_review",
    function_description=(
        "Submit a review evaluating the output of the training script."
    ),
    no_user_message=True,
)
```

`GenericLLM` 再原样转交给 `LiteLLMClient.query()`。`LiteLLMClient` 将 schema 包装成 `FunctionSpec`，然后构造如下参数：

```python
filtered_kwargs["functions"] = [{
    "type": "function",
    "name": "submit_review",
    "description": "Submit a review evaluating the output of the training script.",
    "parameters": schema,
}]
filtered_kwargs["function_call"] = "auto"

completion_fn(messages=messages, **filtered_kwargs)
```

因此 Dojo 并没有使用本次测试中表现稳定的：

```python
response_format={"type": "json_object"}
```

它走的是旧版 `functions`/`function_call` 接口。

## 风险 1：payload 混用了两代接口的形状

旧版 `functions` 中的单项通常是：

```python
{
    "name": "submit_review",
    "description": "...",
    "parameters": schema,
}
```

现代 `tools` 中的对应写法则是：

```python
{
    "type": "function",
    "function": {
        "name": "submit_review",
        "description": "...",
        "parameters": schema,
    },
}
```

Dojo 发送的是 `functions=[...]`，但单项里又加入了现代格式的 `"type": "function"`，同时没有现代格式要求的嵌套 `function`。这是一种 hybrid payload。某些服务端或 LiteLLM 版本会宽容处理，但不能依赖它在所有 OpenAI-compatible provider 上具有一致行为。

## 风险 2：`function_call="auto"` 没有强制结构化返回

`auto` 允许模型自行决定是否调用函数。模型可以把 JSON 放进普通 `message.content`，也可以返回空 content，不能保证一定得到 `submit_review.arguments`。如果 analyze 的下游必须获得字典，更合适的是强制指定函数，或者直接使用 JSON mode。

## 风险 3：Dojo 只读取 legacy `message.function_call`

返回后，Dojo 只检查：

```python
function_call = choice.message.function_call
```

它没有读取现代响应字段：

```python
choice.message.tool_calls[0].function.arguments
```

如果 LiteLLM/provider 用现代 `tool_calls` 返回，即使服务端实际给出了合格 arguments，Dojo 仍可能判断“没有 function call”，转而返回 `message.content`。这个 content 可能是 JSON 字符串，也可能为空；此时 `GenericLLM` 得到的是 `str`/`None`，而不是 analyze 下游预期的 `dict`。

## 风险 4：错误时主动退化为无约束文本

当 LiteLLM 抛出的 `BadRequestError` 文本包含 `function calling` 或 `functions` 时，Dojo 会删除：

```python
functions
function_call
```

然后重新请求普通文本。返回解析阶段如果没有 function call 或函数名不匹配，也会直接返回 `message.content`。因此 schema 在这些 fallback 路径上完全不再是硬约束。

## 本机 DeepSeek 实测

测试脚本：`src/mle_critic/test/test_deepseek_json_interfaces.py`。环境为 Python 3.12、OpenAI SDK 1.72.0、LiteLLM 1.65.7，模型为 `deepseek-v4-flash`，每条路径 10 次：

测试的成功判据除类型/schema 外，还要求 `summary` 非空且 metric 等于提示中的 `0.8123`，因此比当前 Dojo schema（只规定 `summary` 是 string，没有 `minLength`）稍严格。

| 路径 | 成功率 | 含义 |
|---|---:|---|
| OpenAI SDK + `response_format=json_object` | 10/10 | DeepSeek OpenAI-compatible JSON mode 本身稳定 |
| LiteLLM + `response_format=json_object` | 9/10 | LiteLLM JSON mode 基本稳定，仍有一次空/不可解析响应 |
| LiteLLM + Dojo hybrid legacy payload | 5/10 | 出现截断 arguments，以及既无 arguments 也无 content |
| 实际 `LiteLLMClient.query()` | 2/10 | 多数 fallback 成字符串/空 content；另有一次独立的 W&B import 故障 |

这组结果支持以下结论：**DeepSeek 并非普遍不能稳定输出 JSON，主要问题是 Dojo 的结构化输出 transport 与当前 DeepSeek/LiteLLM 组合兼容性差。** 但不能把所有失败都归因于同一个 payload：

- `litellm_json` 的 1 次失败说明 provider/LiteLLM 链路也不是绝对 100%。
- `dojo_wrapper` 第 1 次出现 `cannot import name 'Deprecated' from wandb.proto.wandb_telemetry_pb2`，这是 W&B/protobuf 安装不一致，和 JSON transport 无关。
- wrapper 后续调用能进入 API 请求，说明其余失败才可用于观察 Dojo 的返回解析行为。

## 对复现和采数据的建议

严格复现 upstream 时，不应悄悄修改 backend；应保留原 payload，并记录 analyze 解析失败率。这也是为什么 upstream reproduction 与学生 fallback 结果必须分开存放。

如果目标是稳定采数据而不是逐行复现，优先考虑让 analyze 使用：

```python
response_format={"type": "json_object"}
```

并在本地执行 `json.loads` + JSON Schema validation。另一种方案是完整迁移到现代 `tools` + 强制 `tool_choice`，同时兼容解析 `tool_calls`；但本轮四模式结果没有测试现代 tools 路径，实施前应先运行测试脚本中的 `openai_tools` 和 `litellm_tools` 模式验证。

无论使用哪种 transport，都不应把“fallback 到普通文本”视为结构化调用成功；至少应记录 transport 类型、原始响应和 schema 校验错误，必要时针对结构化失败单独重试。