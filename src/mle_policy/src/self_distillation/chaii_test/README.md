# CHAIi tokenizer 知识与回答完整性评测

固定 journal 中 step 1 的输入，重复采样，比较知识是否出现在思考里、是否进入最终代码，
以及回答是否完整、生成成本如何变化。

## 1. 代码分工

- `__main__.py`：读取 journal、调用服务、保存原始响应，边生成边统计。
- `inspect.py`：离线重算已有 `responses.jsonl`，生成多组对比 JSON 和 Markdown 表。
- `evaluation.py`：两个入口共用的思考/答案拆分、知识检查、完整性与长度统计。

`inspect.py` 同时分析思考和最终代码，也支持纯答案输出；它和生成入口使用同一套指标。
原先的 `use_fast`、`code_*` 和独立严格检查器已合并为 schema version 2。

## 2. 三个知识指标

| 表格列 | JSON 指标 | 定义 |
| --- | --- | --- |
| 思考：明确标识符 | `thinking_explicit_identifier` | 思考出现独立词 `use_fast` 或任意 `*TokenizerFast` 类名 |
| 思考：含文字描述 | `thinking_including_description` | 包含前一项，也接受 `fast tokenizer(s)`、`fast-tokenizer(s)`、`fast tokenization` |
| 最终代码：明确标识符 | `final_code_explicit_identifier` | 最终答案的 Python/无语言标签代码块中出现上述明确标识符 |

“含文字描述”是包含明确标识符的宽口径，不是只统计纯文字命中。
单纯出现 fast、训练很快或一般 offsets 描述不计入。思考里的代码示例仍属于思考。
最终答案的普通文字不算最终代码；多个代码块合并统计标识符。

这三列是文本命中：注释、字符串和 `use_fast=False` 也会命中明确标识符。
`explicit_fast_constructor` 另用 AST 检查最长代码块中的真实 `from_pretrained` 调用：
Fast 类，或 `AutoTokenizer(..., use_fast=True)`。它与“代码提到了知识”分开统计。
给 `XLMRobertaTokenizer` 传 `use_fast=True` 记为 `slow_class_use_fast`，不当作明确选择 Fast 类。
AST 诊断还保留 `auto_tokenizer_default`、`explicit_slow_with_offsets`。

## 3. 思考和答案怎样拆分

支持 `reasoning_content`、`reasoning` 独立字段，以及 `content` 中的 `<think>...</think>`。

- 有 `</think>`：前面算思考，后面算最终答案；支持服务预填 `<think>`、响应只返回闭合标签。
- 有 `<think>` 而没有闭合：全部算未完成思考，其中的代码不算最终代码。
- 有非空独立 reasoning 字段：该字段算思考，`content` 算最终答案。
- 没有标签、没有独立 reasoning：由 `--response-mode` 决定。

| 模式 | 无标签输出的处理 |
| --- | --- |
| `thinking` | 全部算未闭合思考，适用于服务预填 `<think>` 后又在闭合前结束的回答 |
| `answer` | 算最终答案，适用于关闭思考、只生成最终回答的服务 |
| `auto`（默认） | 根据原请求判断：`enable_thinking=False` 为 answer；True 或非空有效 `reasoning_effort` 为 thinking；均未指定时按普通答案处理 |

离线检查从同目录 `request.json` 恢复请求和已记录的 `response_mode`。
如果服务默认开思考、原请求却没有写任何相关参数，请显式用 `--response-mode thinking`。
这个选项只影响解析，不修改发给服务的生成设置。

`thinking_closed`：行内标签以闭合标签为准；独立 reasoning 字段以是否进入非空最终答案为准。
纯答案模式记为 `null`，闭合率的分母只包含实际识别到思考的回答。
`premature_stop` 指 `finish_reason=stop` 但思考未闭合；`truncated` 指 `finish_reason=length`。
两者分开统计。思考闭合也可能在写代码时截断。

`valid_final_code` 检查最长代码块非空、代码围栏闭合、Python 语法通过。
已进入答案但未闭合的代码块仍统计知识命中，同时标为未完成。
这项语法检查与实际执行成功、MLEBench 分数分别评估。

## 4. 长度与统计口径

知识率以成功 API 响应为分母，包含截断回答；错误单列，不当作知识未命中。
每个比例提供 `hits / total`、rate 和 95% Wilson 区间。
`stop_only_metrics` 另统计正常 stop 的子集，保留 `premature_stop` 便于识别提前结束。

`lengths` 为以下各项提供有效数量、均值、中位数、P90、最小值和最大值：

- `completion_tokens`：API 原始 usage 中的总生成 token；是否包含 thinking 取决于服务的 usage 口径。
- `reasoning_chars`：拆出的思考字符数。
- `answer_chars`：最终答案字符数。
- `primary_code_chars`：最长代码块字符数。

usage 缺失时 token 长度为 null，不补零、不重新分词估算。P90 使用最近秩法。
多组比较以 `--responses` 第一组为参照，JSON 提供命中率变化（百分点）、各项平均长度差和比值。
Markdown 展示三列知识、think 闭合、提前停止、截断、有效代码、平均/P90 tokens 和长度比。
JSON 同时记录 prompt 是否相同、生成参数哪些键不同；不同底模或生成预算的比较仅用于观察现象。

## 5. 生成新结果

从仓库根目录运行，服务需已启动：

```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
export PYTHONPATH="$PWD/src:$PWD${PYTHONPATH:+:$PYTHONPATH}"
JOURNAL=path/to/run/json/JOURNAL.jsonl

python -m mle_policy.src.self_distillation.chaii_test \
  --journal "$JOURNAL" --base-url http://gpu35:18351/v1 \
  --model-id qwen3.8-27b --n 100 --concurrency 6 \
  --response-mode thinking --output-dir outputs/chaii_test/base
```

也接受 `checkpoint/journal.jsonl`。程序取 `step == 1` 节点的 draft `prompt_messages`，
沿用同一 run 的 `dojo_config.json` 中 `generation_kwargs`，只移除客户端选项
`allowed_openai_params`，并设置服务模型名和单次请求 `n=1`。
对 adapter 运行相同命令，更换 `--model-id` 和输出目录即可。

输出目录须为新目录，包含 `request.json`、`responses.jsonl`、`summary.json`。
每条响应保留完整 API JSON 和统一分析结果 `analysis`；每完成一条就更新 summary。
中断时保留已完成记录和 `requested/completed/unfinished`。

## 6. 重算已有结果

```bash
PYTHONPATH="$PWD/src:$PWD" python -m mle_policy.src.self_distillation.chaii_test.inspect \
  --responses outputs/chaii_test/base/responses.jsonl outputs/chaii_test/day1/responses.jsonl \
  --response-mode thinking --output tmp/opsd/chaii-comparison.json
```

输出 `chaii-comparison.json` 和同名 `.md`。旧响应中的 `indicators`、`analysis` 都不直接复用，
统一从原始 `response` 重算。原始响应文件保持不变；历史 summary 保留旧口径，不与 v2 指标混用。

## 7. 测试

```bash
PYTHONPATH="$PWD/src:$PWD" pytest -q \
  src/mle_policy/test/test_chaii_test.py \
  src/mle_policy/test/test_chaii_inspect.py
```

覆盖 journal 读取、请求透传、两种 reasoning 字段、预填/未闭合 think、纯答案、
代码围栏截断、知识与 AST 区分、缺失 usage、长度变化、失败计数、中断保留，
以及生成 summary 与离线重算的一致性。
