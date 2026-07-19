# DeepSeek 结构化输出兼容性与修复记录

## 结论

AIRA-Dojo upstream 的 LiteLLM backend 使用了混合新旧两代格式的
`functions`/`function_call` 接口，并且只解析 legacy `message.function_call`。
这与当前 DeepSeek OpenAI-compatible 接口不可靠地兼容；对于启用 thinking 的模型，
强制现代 `tool_choice` 又会被服务端直接拒绝：

```text
Thinking mode does not support this tool_choice
```

本仓库因此将 LiteLLM 结构化输出的默认 transport 改为：

```python
response_format={"type": "json_object"}
```

JSON mode 不直接携带 JSON Schema，所以 backend 会把 schema 明确附加到 system
message，并在本地执行 `json.loads` 和 Draft 7 schema validation。格式或 schema
错误默认额外重试两次。只有 endpoint 明确报告不支持 JSON mode 时，才回退到正确的
现代 `tools`/`tool_choice` 接口；结构化请求不再静默退化为普通文本。

## Upstream 问题调用链

MLE-bench 的 analyze operator 在
`src/dojo/core/solvers/operators/analyze.py` 中定义 schema，并将其交给 `GenericLLM`：

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

修复前，`LiteLLMClient.query()` 最终构造的是：

```python
filtered_kwargs["functions"] = [{
    "type": "function",
    "name": "submit_review",
    "description": "...",
    "parameters": schema,
}]
filtered_kwargs["function_call"] = "auto"
```

这里同时存在四个问题：

1. `functions` 是 legacy 参数，但列表项又混入现代格式的 `"type": "function"`；
2. `function_call="auto"` 不保证模型调用函数；
3. 返回端只读取 legacy `message.function_call`，不读取现代 `message.tool_calls`；
4. function calling 报错或返回格式不符时，会静默回退到无 schema 约束的普通文本。

现代 tools 的正确请求形状应为：

```python
tools=[{
    "type": "function",
    "function": {
        "name": "submit_review",
        "description": "...",
        "parameters": schema,
    },
}]
tool_choice={
    "type": "function",
    "function": {"name": "submit_review"},
}
```

但 `tmp/deepseek-json-report.json` 证明本次使用的 DeepSeek thinking 模型不接受上述
强制 `tool_choice`，所以它不适合作为默认方案。

## 修复前的 DeepSeek 实测

诊断脚本为 `src/mle_critic/test/test_deepseek_json_interfaces.py`，完整历史日志为
`tmp/deepseek-json-report.json`。环境是 Python 3.12、OpenAI SDK 1.72.0、LiteLLM
1.65.7，模型是 `deepseek-v4-flash`，每条路径 10 次。

成功不仅要求输出可解析，还要求字段类型正确、`is_bug=false`、`summary` 非空，且
metric 精确等于提示中的 `0.8123`。

| 路径 | 成功率 | 观察 |
|---|---:|---|
| OpenAI SDK + JSON mode | 10/10 | 同一 endpoint 上最稳定 |
| LiteLLM + JSON mode | 9/10 | 唯一失败是 `summary` 为空；JSON 本身可解析 |
| OpenAI SDK + forced tools | 0/10 | 全部被 thinking 模式拒绝 `tool_choice` |
| LiteLLM + forced tools | 0/10 | 同上 |
| LiteLLM + upstream hybrid legacy payload | 3/10 | 空响应或截断 arguments 较多 |
| 修复前的实际 Dojo wrapper | 6/10 | 三次空字符串；另有一次独立 W&B import 故障 |

因此，这组数据支持选择 JSON mode。它也说明 JSON mode 仍需 schema validation 和
应用层重试：LiteLLM JSON 的一次失败虽然是合法 JSON，但没有满足更严格的业务约束。

W&B 错误如下，它发生在 backend 请求之前，与 DeepSeek transport 无关：

```text
cannot import name 'Deprecated' from wandb.proto.wandb_telemetry_pb2
```

## 本次代码更改

主要修改位于 `src/dojo/core/solvers/llm_helpers/backends/lite_llm.py`：

- 结构化调用默认发送 `response_format={"type": "json_object"}`；
- 将 function description 和完整 JSON Schema 附加到 system message，且不修改调用方
  原始 messages；
- 对返回值执行 JSON object 类型检查和 Draft 7 schema validation；
- 空 content、非法 JSON、字段缺失、字段类型错误等都视为结构化调用失败；
- 默认额外重试两次，不再把失败伪装成成功的普通文本；
- endpoint 明确不支持 JSON mode 时，回退到现代 `tools` 和强制 `tool_choice`；
- tools 响应读取 `message.tool_calls[0].function.arguments`；
- usage stats 记录最终 transport 和实际结构化 API 请求次数，并汇总重试产生的 token；
- 修正 `FunctionSpec.as_openai_tool_dict` 的现代 tools 嵌套格式；
- 修复 `_query_client(..., model_kwargs={})` 的可变默认参数问题；
- 移除调用方可能传入的冲突 transport 参数，保证一次结构化请求只使用一种接口。

诊断脚本中的 upstream hybrid payload 被保留为历史对照项；`dojo_wrapper` 现在测试修复后的
真实路径。另新增离线回归测试
`src/mle_critic/test/test_litellm_structured_output.py`，覆盖：

- 默认 JSON mode 及 schema prompt；
- 非法 JSON 后重试；
- schema violation 不退化成文本；
- 显式现代 tools 的请求与响应解析；
- JSON mode 不受支持时回退到现代 tools。

## 配置方式

默认配置无需修改。只要调用时提供 `json_schema`、`function_name` 和
`function_description`，LiteLLM backend 就会使用 JSON mode。

应用层结构化重试次数可在 operator 的 `generation_kwargs` 中调整：

```yaml
generation_kwargs:
  structured_output_retries: 2
```

对于已经验证不处于 thinking 模式、并且 tools 表现更好的 endpoint，可以显式选择：

```yaml
generation_kwargs:
  structured_output_mode: tools
```

可选值只有 `json` 和 `tools`。DeepSeek thinking 模型不要设置为 `tools`，否则仍会收到
`Thinking mode does not support this tool_choice`。

## 验证

离线回归测试不会访问网络：

```bash
PYTHONPATH=src pytest -q \
  src/mle_critic/test/test_litellm_structured_output.py
```

真实 endpoint 的比较测试会产生 API 调用和费用：

```bash
python src/mle_critic/test/test_deepseek_json_interfaces.py \
  --modes openai_json,litellm_json,openai_tools,litellm_tools,litellm_dojo_payload,dojo_wrapper \
  --trials 10 \
  --output tmp/deepseek-json-report.json
```

对于大规模采集，建议至少记录 model、transport、重试次数、原始结构化响应和最终 schema
错误。不要把 schema validation 失败后的普通文本计为一次成功的 analyze 结果。
