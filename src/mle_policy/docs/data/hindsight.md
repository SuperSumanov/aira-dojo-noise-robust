# Hindsight：从搜索经验生成额外训练回答

流程：**原轨迹 → 详细 hint → 原 prompt 临时加 hint → policy 完整重新解题**。
新 response 原样保存，训练 prompt 恢复为未加 hint 的输入。方案演变见
`hindsight_history.md`，客户端详细设计见 `hindsight_impl.md`。

新代码未经执行。metric 继承提供经验的最终跑通节点，用来区分来源质量。
hindsight 单独分组、计算 advantage，严格筛 `advantage > 0` 后再合并训练行。

## 1. 三步处理与代码对应关系

代码在 `src/mle_policy/src/data/hindsight/`。

| 步骤 | 代码入口 | 处理内容 |
| --- | --- | --- |
| 审查 CV | `__main__.rewrite`、`prompts.audit/review` | 审查跑通 episode 的评估是否虚高；拟拒绝项独立复核，确认后剪掉该起点和后代 |
| 吸收 debug 经验 | `tree.episodes`、`__main__.rewrite` | 选择 implement/improve 后经过 debug 跑通的 episode，重新回答它最初的 prompt |
| 吸收 improve 经验 | `tree.better`、`__main__.rewrite` | 后继 improve 的 CV 严格更好时，将其经验带回前一个 episode 的最初 prompt |

第三步的目标既可以是 implement，也可以是 improve。journal 中 implement 的操作名
是 `draft`。第二、三步都从审查后的原树选候选，第二步的新回答不会成为第三步输入。
比较使用 agent CV 和 `metric_maximize`，不用官方测试集分数，同分不生成。

一次重生成的调用链：

```text
prompts.hint / regenerate.extract_hint：原 prompt、轨迹中的 plan/日志/分析、来源终点代码 → 详细工程建议
  → regenerate.inject_hint：临时放到原 user prompt 前面
  → client.ModelClient.generate：policy 原生 thinking 完整生成
  → helper.parts：检查 think、plan、Python，解析代码 AST
  → regenerate.append_rewrite：保存完整 response、原 prompt、继承标签和来源
  → tree.rebuild_links：补齐输出树的 children 和 current_best_node
```

`regenerate.extract_hint` 对长轨迹逐节点提炼，再汇成最终 hint。字符阈值是这批数据的
工程设置，不是通用 token 保证；超窗会报错，已有请求缓存可继续使用。

`client.ModelClient` 复用 dojo 的 `llm_helpers/backends/open_ai.OpenAIClient`。
普通 `query` 只提供处理后的文本和 usage，所以这里使用 `query_raw` 保留完整响应，
检查 `finish_reason` 并读取独立 `reasoning_content`。hindsight 层负责并发、缓存、
格式检查和有限重试，网络请求由 dojo client 发出。同步 client 通过线程执行。

生成沿用原 run 的 temperature、top_p 和 reasoning 配置；模型由 `--model` 指定。
完整回答与两轮审查均不加 JSON grammar；审查在生成后解析 JSON，hint 提炼使用
JSON 输出约束。两轮审查均开启 thinking，且不主动设置输出 token 上限；完整回答
只继承原 operator 显式记录的上限。格式检查不执行新代码。

## 2. 输出树与 journal 每行的格式

每个 run 写出两份对应的 journal：

- `json/JOURNAL.jsonl`：每行是 `{timestamp, step, data}`，节点在 `data` 内；metric_info 字段展开为 `metric_info/...`。
- `checkpoint/journal.jsonl`：每行直接是节点对象，metric_info 是嵌套对象。没有外层 `data`。

一行就是一个树节点，不是单独一条对话。`parents` 和 `children` 存 **step 数字**，
不是 id。下面是 checkpoint 的示意，长文本、id 和轨迹引用作了缩写：

```json
{
  "step": 54,
  "id": "new-proposal-id",
  "parents": [0],
  "children": [],
  "operators_used": ["draft"],
  "operators_metrics": [{
    "prompt_messages": [{"role": "user", "content": "原始输入，不含 hint"}],
    "completion_text": "原样保存的 think、plan 和 Python 代码",
    "usage": {}
  }],
  "plan": "从完整回答提取的计划",
  "code": "从完整回答提取的 Python 代码",
  "metric": 0.3865,
  "metric_maximize": true,
  "is_buggy": null,
  "analysis": null,
  "term_out": null,
  "_term_out": null,
  "exit_code": null,
  "exec_time": null,
  "current_best_node": 54,
  "metric_info": {
    "median_threshold": 0.72756,
    "gold_threshold": 0.76305,
    "is_lower_better": 0.0
  },
  "hindsight": {
    "kind": "rewrite",
    "stage": "debug",
    "source_journal": "相对原始输入根目录的 run/json/JOURNAL.jsonl",
    "prompt_source": {"step": 1, "id": "original-proposal-id"},
    "source_parents": [{"step": 0, "id": "original-parent-id"}],
    "target_trajectory": [{"step": 1, "id": "original-proposal-id"}, {"step": 3, "id": "original-terminal-id"}],
    "donor_trajectory": [{"step": 1, "id": "original-proposal-id"}, {"step": 3, "id": "original-terminal-id"}],
    "response_origin": "regenerated",
    "execution_status": "not_run",
    "metric_origin": "inherited",
    "metric_source": {"step": 3, "id": "original-terminal-id"},
    "hint_includes_code": false,
    "generation_cache_key": "request-hash",
    "generation_model": "qwen3.8-27b",
    "generation": {"temperature": 0.6, "top_p": 0.95}
  }
}
```

字段分成三组理解：

| 字段 | 含义 |
| --- | --- |
| `step/id/parents/children` | 输出树的位置；新 proposal 的 step 大于原树最大 step |
| `operators_used/metrics` | 操作名与模型调用一一对应；当前 proposal 一次调用，anchor 零次 |
| `completion_text` | 整份新回答；think 与代码不做拼接替换 |
| `plan/code` | 从同一份回答提取的计划和代码 |
| `metric/metric_maximize` | 来源最终跑通节点的 CV 及方向，不是新代码的实测结果 |
| `is_buggy` | proposal 为 null，表示未执行；anchor 为 true，只是不可训练的占位节点 |
| `analysis/term_out/_term_out/exit_code/exec_time` | proposal 都为 null，旧执行记录清空 |
| `metric_info` | 保留 reward 归一化所需阈值、方向和竞赛名，清除官方 score、奖牌和提交检查 |
| `current_best_node` | 截至该 step、按可用 metric 选出的最佳节点 step，用于树索引 |
| `hindsight.kind` | `rewrite` 是新回答；`context` 是必要祖先锚点 |
| `stage` | `debug` 为第二步，`improve` 为第三步，与目标操作名 draft/improve 分开 |
| `prompt_source/source_parents` | 原 prompt 所在节点及其原父节点，引用原树 step/id |
| `target_trajectory/donor_trajectory` | 被重答的 episode 与提供经验的 episode，按顺序记录原节点引用 |
| `metric_source` | 提供继承 metric 的原跑通节点 |
| `generation_cache_key/model/generation` | 请求缓存、模型及实际采样配置；完整请求/响应在 `_hindsight/cache` |

debug 阶段 target 和 donor 是同一轨迹；improve 阶段 donor 是更好后继。
`hint_includes_code=false` 表示 policy 只看文字经验；提炼 hint 的模型仍看来源代码。
hint 不进入训练 prompt，也不放入节点对话；它保留在树目录内的生成报告/缓存供排查。
真实请求的 usage 同样留在缓存，节点调用的 usage 留空。

祖先 anchor 只有 step、新 id、原 parents、重建的 children，以及
`hindsight={kind: context, source_journal, source_node}`；code 为空，metric 为 null，
operators 两个列表为空。它连接原祖先层级和新 proposal，不复制原始训练调用。

**保留的树是来源索引，不是新代码执行历史。** 原 prompt 可能引用旧祖先的代码、
日志或 memory，这些内容不会随新回答重新生成，树上的上下文可能前后不一致。
每个合成 proposal 自己结束 episode，原 debug 后继不会接到它下面。

## 3. 与共享数据流程的边界

来源标记只保留在 hindsight 树中。`samples.jsonl`、`groups.jsonl`、GRPO 行都沿用
普通格式，不携带 hindsight key，也不因来源改变 advantage 公式。

共享读取器通过通用字段识别标签：已执行的 `is_buggy=false` 节点有结果；
`is_buggy=null` 且有有限数值 metric 的未执行 proposal 有训练标签。
后者仍然 `node_has_result=false`、官方 score 为空，仅 metric reward 可用。
这个判断不读取来源标记。大写读取器也保留已有 metric_info 阈值，避免因缺少官方
score 而丢掉 CV reward。

样本归属靠独立目录和操作顺序控制：原数据与合成数据分别构建组、分别计算
advantage，合成数据筛正以后才合并。筛选和合并不依赖逐行来源字段。需要追溯时，
回到对应树，用样本的 node id/step 查询；导出后可通过 sample_id 与 samples 对照。

切分沿用原数据已有的 `splits.jsonl`，`align_splits` 按 group_id 对齐合成组。
不增加 hindsight 专用的 split 模式。task 切分可以隔离竞赛；group 切分隔离 prompt
组；run 模式面对跨 run 组不能保证同一 run 完全隔离。只有一个任务又需要验证集
时，按已有实验需求选择划分粒度，不为一次运行增加 batch 模式。

## 4. 分阶段运行

共享操作继续使用 `scripts/data/` 下的原入口；hindsight 专用操作在
`scripts/data/hindsight/`。各脚本只做一个步骤，均从仓库根目录运行。

切分对齐、正 advantage 筛选和数据合并的 Python 实现在通用目录
`src/mle_policy/src/data/helper/`，对应 `align_splits.py`、`filter_positive.py`、
`merge.py`，不依赖 hindsight 核心。这里保留原 shell 入口和参数，已有运行命令
继续可用；其他实验可直接以 `python -m src.mle_policy.src.data.helper.<模块名>`
调用。`--original` 指已有数据，`--hindsight` 指待对齐或追加的数据，均不读取
逐行 hindsight 标记；合并仍要求追加行的 advantage 严格为正。

```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
export PYTHONPATH="$PWD/src:$PWD${PYTHONPATH:+:$PYTHONPATH}"
RAW=data/augmented_mle_critic/raw_journal/hindsight/1028
TREE=data/augmented_mle_critic/raw_journal/hindsight/1028_hindsight_v3
ORIGINAL=data/mle_policy/dataset/hindsight_example/original
SYNTHETIC=data/mle_policy/dataset/hindsight_example/synthetic
MERGED=data/mle_policy/dataset/hindsight_example/merged
```

### 4.1 原数据：共享主流程

```bash
bash src/mle_policy/scripts/data/build_all_batches_bigjournal.sh "$RAW" "$ORIGINAL"
bash src/mle_policy/scripts/data/aggregate_batches.sh "$ORIGINAL"
bash src/mle_policy/scripts/data/assign_splits.sh "$ORIGINAL" task 0.1
bash src/mle_policy/scripts/data/to_sft.sh "$ORIGINAL"
bash src/mle_policy/scripts/data/to_grpo.sh "$ORIGINAL"
```

已有原数据中间件和 splits 时直接复用。大写 journal 使用已有 bigjournal 入口；
小写 checkpoint 使用 `build_all_batches.sh`。一个任务按 task 切分时可能全在 train，
需要验证集时沿用实验选定的切分方案。原始 GRPO 默认使用官方 score reward；若实验
按 agent CV 训练，使用已有 `to_grpo_metric.sh`。

### 4.2 hindsight：生成和验证

```bash
bash src/mle_policy/scripts/data/hindsight/generate.sh \
  --input "$RAW" --output "$TREE" --hint-code omit \
  --model qwen3.8-27b --concurrency 12 --journal-workers 4
bash src/mle_policy/scripts/data/hindsight/verify.sh --input "$RAW" --output "$TREE"
```

`verify.sh` 调用测试目录的 `src/mle_policy/test/verify_hindsight.py`，对已经生成的
整批数据做离线验收；生成主流程不依赖这个验证工具。

默认服务是 `http://127.0.0.1:8000/v1`。有已有审查缓存时给生成命令加
`--audit-cache "$AUDIT_CACHE"`。同目录重跑会校验并复用完成请求；无需重生成全部回答。
`--hint-code include` 可让 policy 额外参考来源完整代码，仍原样保留新回答。

### 4.3 hindsight：共享分组与 advantage，再筛选

```bash
bash src/mle_policy/scripts/data/build_all_batches_bigjournal.sh "$TREE" "$SYNTHETIC"
bash src/mle_policy/scripts/data/aggregate_batches.sh "$SYNTHETIC"
bash src/mle_policy/scripts/data/hindsight/align_splits.sh \
  --original "$ORIGINAL/thinking" --hindsight "$SYNTHETIC/thinking"
bash src/mle_policy/scripts/data/to_grpo_metric.sh "$SYNTHETIC" thinking
bash src/mle_policy/scripts/data/hindsight/filter_positive.sh \
  --input "$SYNTHETIC/thinking/grpo.jsonl" --output "$SYNTHETIC/thinking/positive.jsonl"
```

先在完整合成候选组计算 advantage，再严格保留 `> 0`。单候选组和全同分组由共享
GRPO 流程跳过；筛选只读已计算的有限 advantage，不改变 reward 或重算 advantage。
示例使用 thinking 桶；其他桶按同样步骤分别处理。

### 4.4 合并训练行

```bash
bash src/mle_policy/scripts/data/hindsight/merge.sh \
  --original "$ORIGINAL/thinking/grpo.jsonl" \
  --hindsight "$SYNTHETIC/thinking/positive.jsonl" \
  --output "$MERGED/thinking/grpo.jsonl"
```

合并保留原行，检查合成输入的 advantage 严格为正、sample_id 不重复、同 group 的
split 一致。输入必须来自独立处理后的两个目录；通用行本身不能证明其来源。
输出 JSONL 携带原有 split，不加来源字段。后续长度过滤与训练格式转换走现有流程。

## 5. 检查用例

`experiment.py` 比较同一个 hint 下“文字经验”和“文字经验+来源代码”两种输入。
仓库内的最小用例在 `src/mle_policy/test/fixtures/hindsight/`：
`run/dojo_config.json` 保存配置，`run/json/JOURNAL.jsonl` 保存树。
它是人为构造的接口与格式检查数据，代码和 metric 不代表真实实验：step0 是根，
draft step1 → debug step2 修复缺少导入的问题，随后 improve step3 得到更好的 metric。

### 5.1 运行对照

从仓库根目录执行，先启动兼容 OpenAI 协议的模型服务，再运行：

```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
export PYTHONPATH="$PWD/src:$PWD${PYTHONPATH:+:$PYTHONPATH}"
python -m src.mle_policy.src.data.hindsight.experiment \
  --journal src/mle_policy/test/fixtures/hindsight/run/json/JOURNAL.jsonl \
  --case debug:1:1 --case improve:1:3 \
  --model qwen3.8-27b --base-url http://127.0.0.1:8000/v1 \
  --output data/mle_policy/dataset/hindsight_example/comparison
```

`--case stage:target:donor` 中后两个数字都是原 episode 的起点 step，不是终点。
debug 必须 target=donor；improve 指定要重答的起点和提供经验的起点。
换成真实数据时替换 `--journal` 和 `--case`，格式不变。

### 5.2 输出与评估

每个 case 先提炼一次 hint，再分别生成 hint-only 和 with-code 的完整回答。
例如 `debug:1:1` 生成 `debug-1-1-hint-only/` 和 `debug-1-1-with-code/`。
每个目录保存：

| 文件 | 内容 |
| --- | --- |
| `original_prompt.json` | 原始 policy 输入消息，方便与加 hint 后的输入对照，也应与树中恢复的训练 prompt 一致 |
| `hint_trace.json` | hint 提炼的调用列表，每项含 `stage`、完整 `messages`（含 system/user）与解析后的 `result` |
| `hint.md` | 两种输入共用的最终文字经验 |
| `rewrite_trace.json` | 重生成回答使用的完整 `messages`、`generation` 参数及模型返回的 `result`（完整回答、usage、缓存键等） |
| `generated.md` | 原样保存的完整回答，含 think、plan 和代码 |
| `nodes.json` | 新回答和必要祖先节点，用于检查字段及挂接位置 |
| `diagnostics.json` | 配置、轨迹引用、来源 metric、代码文本相似度和生成缓存键 |

输出根目录的 `summary.json` 汇总所有对照的 diagnostics；`cache/` 保存模型请求缓存。
trace 文件记录传给 client 的实际消息，命中缓存时也会输出。
`hint_trace.json` 中 user 消息的 `content` 是 JSON 字符串，可继续解析查看原始 prompt、
目标轨迹、来源轨迹和终点代码等输入。长轨迹会先分段提炼：列表保留所有
`debug_hint_part` / `improve_hint_part` 的输入输出，再保留最终汇总调用。
分段记录按完成顺序保存，可从输入中的 step 识别对应轨迹。
同一 case 的两种对照保存相同的 hint trace，便于单独打开任一目录审查。

建议依次检查：hint 是否准确覆盖踩坑过程；`rewrite_trace.json` 的输入是否正确插入
hint、with-code 是否额外包含来源代码；完整回答的 think/plan/code 是否一致；
`nodes.json` 内的训练 prompt 是否恢复为 `original_prompt.json`，不携带 hint。
diagnostics 的代码相似度仅描述改写程度；工具不执行新代码，继承 metric 也不代表
新回答已获得同样的实测成绩。trace 只用于检查输出，不写入训练样本或 hindsight 节点。

### 5.3 离线回归

离线测试直接读取上述用例，用 fake client 运行完整对照，不需要模型服务：

```bash
PYTHONPATH=.:src python -m pytest src/mle_policy/test/test_hindsight.py -k experiment -q
```

该测试检查 hint 共用、两种输入、完整输入输出保存、回答存储和来源节点。
完整 hindsight 测试还覆盖长轨迹分段 trace、缓存与数据导出：

```bash
PYTHONPATH=.:src python -m pytest src/mle_policy/test/test_hindsight.py -q
```

`test/verify_hindsight.py` 的 `verify_all` 检查候选覆盖、来源引用、树连接、原 prompt、缓存中的完整 response、
plan/code、metric 继承、执行字段清空、大小写读取器的 metric reward 一致和来源字段
未进入 samples。格式校验和这些检查都不代表生成代码已经在 benchmark 上执行成功。

## 6. 运行规模示例

2026-10-30 在 chaii 的 17 个 run 上完整执行了一次：

| 阶段 | 数量 |
| --- | ---: |
| 原始节点 | 826 |
| debug / improve 经验重生成 | 179 / 97 |
| 完整合成回答 | 276 |
| 独立 GRPO 导出 | 250，另 26 个单候选组跳过 |
| 正 advantage 保留 | 127 |
| 与原始训练行合并 | 1586 + 127 = 1713 |

这次复用审查缓存，生成约 3 小时 21 分钟，平均约 82 条/小时。主要耗时是长轨迹
hint 提炼和 policy 完整思考。该数值用于估算规模，不代表其他模型和轨迹长度的速度。
合成来源树保留 276 个新回答及必要祖先，原样本和合成数据始终分开处理。
