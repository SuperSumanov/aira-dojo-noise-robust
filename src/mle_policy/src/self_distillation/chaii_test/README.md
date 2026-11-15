# CHAIi step 1 tokenizer 测试

固定 journal 的 step 1 输入，重复生成，比较底模与 LoRA 显式使用 fast tokenizer 的频率。
读取、采样、统计和命令行集中在 `__main__.py`。

## 1. 读取原始输入和超参数

`--journal` 指向一个 run 的 `json/JOURNAL.jsonl` 或 `checkpoint/journal.jsonl`。
程序直接取 `step == 1` 节点中的 draft `prompt_messages`，读取同一 run 的
`dojo_config.json` → `solver.operators.draft.llm.generation_kwargs` 作为生成参数。

temperature、top_p、seed、thinking、reasoning_effort 等均沿用该配置。
配置未指定的参数保持未指定，每次请求使用相同参数。
其中 `allowed_openai_params` 是 LiteLLM 的客户端选项，发往 HTTP API 时移除。

## 2. 调用已启动的服务

模型名统一使用 `qwen3.8-27b` 和 `qwen3.8-27b-mle-lora`。
确保vllm serve在后台运行后，从仓库根目录运行：

```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
export PYTHONPATH="$PWD/src:$PWD${PYTHONPATH:+:$PYTHONPATH}"
JOURNAL=path/to/run/json/JOURNAL.jsonl

python -m mle_policy.src.self_distillation.chaii_test \
  --journal "$JOURNAL" --base-url http://gpu35:18351/v1 \
  --model-id qwen3.8-27b --n 100 --concurrency 6 \
  --output-dir outputs/chaii_test/base &

python -m mle_policy.src.self_distillation.chaii_test \
  --journal "$JOURNAL" --base-url http://gpu35:18351/v1 \
  --model-id qwen3.8-27b-mle-lora --n 100 --concurrency 6 \
  --output-dir outputs/chaii_test/day1 &
wait
```

命令行只配置 journal、服务地址、模型名、样本量、并发和输出目录。
每次 HTTP 请求生成一个回答，两组同时执行时合计 12 并发。

## 3. 查看结果和运行测试

每个采样目录包含：

- `request.json`：实际 API 请求、prompt SHA256 和 journal 来源。
- `responses.jsonl`：每完成一个请求追加一行，保留完整响应和正则判定。
- `summary.json`：每完成一个请求更新统计，随时可读取部分结果。

已有输出目录会报错。`requested` 为目标数量，`completed` 为已返回数量，
`unfinished` 为尚未返回数量。HTTP 错误单列为 `failed`，命中率分母为成功响应数。
`metrics` 包括截断回答；`stop_only_metrics` 只统计正常结束的回答。

| 指标 | 规则 |
| --- | --- |
| `use_fast` | 完整输出（含 reasoning）出现独立词 `use_fast` |
| `code_use_fast` | 最终回答的 Python 代码块中出现 `use_fast` |
| `code_use_fast_true` | 代码中出现 `use_fast=True` 或字典形式 `"use_fast": True` |
| `code_fast_tokenizer_class` | 代码中出现 `BertTokenizerFast` 等显式 fast 类 |
| `has_code` | 提取到非空 Python 代码块 |
| `mentions_engineering_notes` | 完整输出出现 `engineering notes` |

统计附带 95% Wilson 区间。正则也匹配代码注释和字符串中的文字。

```bash
PYTHONPATH="$PWD/src:$PWD" pytest -q src/mle_policy/test/test_chaii_test.py
```

测试覆盖两种 journal 格式、精确选择 step 1、读取原始配置、参数透传、
reasoning 与代码分离、Wilson 区间、失败和截断计数，以及中断时保留部分结果。

一次Qwen3.8与Qwen3.8+lora对比已完成，用时 2:27:56，两张 3090、总并发 12，
稳定吞吐约 265–278 token/s。两组使用相同 prompt 和生成参数，seed 均为 0–99；
每组均取得 100 个不同回答。

| 模型 | 成功 | 截断 | 有代码 | 全文/代码含 `use_fast` | 显式 fast 类 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 底模 | 100/100 | 0 | 100/100 | 0/100 | 0/100 |
| LoRA | 100/100 | 1 | 99/100 | 0/100 | 0/100 |

LoRA 正常结束的 99 个回答也均未命中 `use_fast`。
两组各 0/100 的 95% Wilson 区间为 [0, 3.70%]。
