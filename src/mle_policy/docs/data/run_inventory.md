# 查一个任务到底用哪些 provider 跑的（run_inventory）

## 这个脚本解决什么问题

`data/augmented_mle_critic/raw_journal/` 里的 run 是用很多不同的模型、不同的 API 供应商跑出来的。
同一个任务在不同日期、由不同人跑的时候，用的模型经常不一样（比如 tgs-salt 有 7 种模型）。
所以当某个任务上 policy 有效果、某个任务上没效果时，第一个该问的问题就是：
**这个任务的数据到底是谁跑出来的？不同 provider 的 run 各有多少？**

`run_inventory` 就是回答这个问题的固定工具。它扫一遍 run 目录，把每个 run 用的
endpoint + 模型读出来，按任务汇总。以后想核对"某任务的 run 是不是混了差模型"、
"某个模型一共贡献了多少 run"，都用它，不要临时手写脚本。

代码位置：`src/mle_policy/src/data/run_inventory.py`。
下面所有命令都在仓库根目录、用 `-m` 跑（`PYTHONPATH` 指到包根），不要直接
`python src/mle_policy/src/data/run_inventory.py`——那样相对 import 会断。

## 先搞清楚：`dojo_config.json` 里的 `provider` 字段不是你要找的 provider

每个 run 目录里都有一份 `dojo_config.json`，里面每个算子（draft / debug / improve / analyze）
都带一个 `llm.client`：

```json
"client": {
  "api": "litellm",
  "model_id": "deepseek-v4-flash",
  "base_url": "https://api.deepseek.com",
  "provider": "openai"
}
```

这里的 `provider` 是 **litellm 客户端的协议类型**，意思是"这个接口说 OpenAI 那套 chat-completions 格式"。
把 `raw_journal` 下 1650 个 `dojo_config.json` 全扫一遍，`provider` 只有 `openai` 一个值，
拿它区分供应商没有意义。

真正有区别的是 `base_url` + `model_id` 这一对：

- `base_url` = 调用的是哪家 API（DeepSeek 官方 / OpenRouter / chatanywhere 等）；
- `model_id` = 那家 API 上的哪个模型（`deepseek-v4-flash`、`moonshotai/kimi-k2.5`、`gpt-5.6-luna` 等）。

所以脚本默认就报 `(base_url, model_id)`。如果只想按供应商或模型聚合，
用 `--group-by endpoint` 或 `--group-by model`（见下）。

## 怎么用

```bash
# 下面统一用这个前缀（在仓库根目录执行）
INV="env PYTHONPATH=src/mle_policy python -m src.data.run_inventory --root data/augmented_mle_critic/raw_journal"

# 列出所有任务和各有多少 run
$INV --list-tasks

# 查指定任务（可以给多个 --task）
$INV --task tgs-salt-identification-challenge \
     --task chaii-hindi-and-tamil-question-answering \
     --task random-acts-of-pizza

# 连每个 run 目录一起列出来（核对日期/seed 时用）
$INV --task random-acts-of-pizza --runs

# 机器可读输出（喂给别的脚本）
$INV --task random-acts-of-pizza --json

# 只按供应商聚合
$INV --task random-acts-of-pizza --group-by endpoint
```

参数说明：

| 参数 | 作用 |
| --- | --- |
| `--root` | 扫描根目录，显式传 `--root data/augmented_mle_critic/raw_journal` |
| `--task` | 只看这些任务，可重复；不给就是全部任务 |
| `--list-tasks` | 只打印任务名和 run 数就退出 |
| `--group-by` | `endpoint_model`（默认）/`endpoint`/`model`/`provider` |
| `--runs` | 每个分组下面把 run 目录也列出来；行首 `!` 表示这个 run 没写出 journal |
| `--require-journal` | 丢掉没有 `checkpoint/journal.jsonl` 的 run（被 kill 的），只统计有效 run |
| `--json` | 输出 JSON |

两个约定：

- **默认跳过 `comparison/` 目录**（它的目录层级不一样，是另一套对比实验）。
  想扫它就加 `--skip <别的名字>` 覆盖，但一般不需要。
- 有效数据的判据是 run 目录下有没有 `checkpoint/journal.jsonl`。没有的就是还没写出 checkpoint
  就被 kill 的 run，默认仍然计数但在 `journal` 列标出来、在 `--runs` 里标 `!`。
  分析时如果关心"实际产出了多少数据"，加 `--require-journal`。

## 三个任务的实查结果（2026-10-04，root = `data/augmented_mle_critic/raw_journal`）

计数单位是 run（不是 seed 里的 step）。`journal` 列是其中真正写出 journal 的 run 数。

### tgs-salt-identification-challenge：30 个 run，7 种模型

| endpoint | model_id | run 数 | 有 journal |
| --- | --- | ---: | ---: |
| `https://api.deepseek.com` | `deepseek-v4-flash` | 8 | 8 |
| `https://openrouter.ai/api/v1` | `moonshotai/kimi-k2.5` | 8 | 8 |
| `https://api.chatanywhere.org` | `gpt-5.4-nano` | 4 | 4 |
| `https://api.chatanywhere.org` | `gpt-5.6-luna` | 4 | 4 |
| `https://openrouter.ai/api/v1` | `deepseek/deepseek-v4-flash-0731` | 4 | 4 |
| `https://openrouter.ai/api/v1` | `stealth/ox-alpha` | 4 | 4 |
| `https://openrouter.ai/api/v1` | `minimax/minimax-m3` | 2 | 2 |

按日期：0814 deepseek-v4-flash；0816 chatanywhere 的 gpt-5.4-nano + gpt-5.6-luna；
0818 minimax-m3；0820/0821 kimi-k2.5；0824 stealth/ox-alpha；0828 deepseek-v4-flash-0731。

**注意 0816 那 4 个 run 是"混模型"的**：同一个 run 里 `analyze` 用 gpt-5.4-nano，
`draft`/`debug`/`improve` 用 gpt-5.6-luna。脚本会专门打 `[mixed operators]` 警告，
因为这种 run 的环境指纹和别的 run 不一样，不能当成一个干净的单模型 run。

### chaii-hindi-and-tamil-question-answering：24 个 run，3 种模型

| endpoint | model_id | run 数 | 有 journal |
| --- | --- | ---: | ---: |
| `https://api.deepseek.com` | `deepseek-v4-flash` | 12 | 12 |
| `https://openrouter.ai/api/v1` | `qwen/qwen3.8-flash` | 8 | 4 |
| `https://api.deepseek.com` | `deepseek-v4-pro` | 4 | 1 |

按日期：0728 deepseek-v4-flash；0729 deepseek-v4-pro；0801 deepseek-v4-flash（8 个 run）；
0830 qwen3.8-flash（8 个 run 里只有 4 个写出 journal）。这个任务里 deepseek-v4-pro 那组
基本没跑出来数据（4 个 run 只有 1 个有 journal），分析时要小心。

### random-acts-of-pizza：24 个 run，5 种模型

| endpoint | model_id | run 数 | 有 journal |
| --- | --- | ---: | ---: |
| `https://openrouter.ai/api/v1` | `z-ai/glm-5` | 8 | 8 |
| `https://api.deepseek.com` | `deepseek-v4-flash` | 4 | 4 |
| `https://openrouter.ai/api/v1` | `minimax/minimax-m3` | 4 | 4 |
| `https://openrouter.ai/api/v1` | `tencent/hy3-preview` | 4 | 4 |
| `https://openrouter.ai/api/v1` | `xiaomi/mimo-v2.5` | 4 | 4 |

按日期：0809 deepseek-v4-flash；0810 minimax-m3；0811 glm-5（8 个 run）；
0812 hy3-preview；0813 mimo-v2.5。这个任务每个 provider 基本都是 4 个 seed 一组，
比较像是有意的多模型对比。

## 已知限制

- 统计口径是 **run**，不是"多少次 LLM 调用"。想看每个 provider 各贡献多少条样本，
  那是 `overview.md` 里 stage 1 分桶之后 `samples.jsonl` / `manifest.json` 的活，不是这个脚本。
- `--skip` 只按目录名匹配，`comparison` 里如果也出现同名目录会被一起跳过。
- 一个 run 内部如果不同算子用了不同模型，这个 run 会在每个模型分组各记一次（并打警告）。
  也就是说"分组 run 数"之和可能大于该任务的总 run 数，正是 0816 那种情况。
