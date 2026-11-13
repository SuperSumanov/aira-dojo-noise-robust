# Hindsight 代码阅读说明

主流程是“选择轨迹 → 提炼经验 → 完整作答 → 写入 journal”。
所有磁盘产物由命令入口写出；树操作和生成函数处理内存对象。

## 1. 各文件的输入输出

路径均相对 `src/mle_policy/src/data/hindsight/`。

| 文件 | 输入 | 输出 |
|---|---|---|
| `__main__.py` | `--input` 下每个 run 的 `json/JOURNAL.jsonl`、`dojo_config.json`，可选 `env_variables.json` | `--output` 的同相对 run 路径：复制的配置与环境文件、`json/JOURNAL.jsonl`、`checkpoint/journal.jsonl` |
| `tree.py` | journal 的节点字典列表 | 内存中的 episode、重建的节点列表 |
| `regenerate.py` | 原节点、目标 episode、来源 episode、模型客户端和采样参数 | 内存中的 hint、新回答和新节点；实验模式可填充 trace |
| `client.py` | 消息列表及采样参数 | hint 字典或完整回答字典 |
| `helper.py` | 回答文本或指定的 JSON 文件路径和值 | 解析后的思考/计划/代码，或写入该路径的 JSON 文件 |
| `experiment.py` | `--journal <run>/json/JOURNAL.jsonl`，同 run 的配置 | `--output/<case>-<variant>/metadata.json`、`trace.json`、`nodes.json` |
| `exp/prepare.py` | `--generation` 下各案例的 `metadata.json`、`nodes.json`，其中引用的原 journal | `--output/manifest.json` 和 `runs/<name>/solution.py`、`metadata.json` |
| `exp/evaluate.py` | `--output/manifest.json`、清单中的代码与 metadata、来源配置 | `runs/<name>/result.json`、`worker-0.log`，dojo 执行目录和评分目录，根目录 `results.json` |
| `exp/summarize.py` | `manifest.json` 与各 run 的 `result.json` | 同目录的 `results.json` |
| 两个 `__init__.py` | 包导入 | 包说明，无文件读写 |

这些输入、输出约定也写在每个代码文件顶部。评测目录的完整树见 `hindsight_eval.md`。

## 2. 从主入口往下读

1. `run` 扫描大 journal，限制同时处理的 journal 数，读取该 run 的配置。
2. `rewrite` 用 `tree.episodes` 找到已跑通的提案和 debug 链，按 mode 选择重写对象。
3. `regenerate` 先调用 `extract_hint`，把 hint 临时加进原始用户输入，再调用完整生成。
4. `append_rewrite` 解析新回答、加入必要祖先、继承来源标签并记录节点引用；
   `rebuild_links` 更新 children 和 current_best_node。
5. `run` 复制 run metadata，分别写大 journal 与小 journal。

生成所用的增强输入只在请求期间存在。节点里的 `prompt_messages` 从原提案复制，
`completion_text` 则保存完整的新回答，节点调用的 usage 留空。
原来源的官方分数、执行输出和耗时留在原 journal；新节点继承 CV 与奖励所需的竞赛阈值。

`tree.synthetic_id` 为新节点分配可区分的 id；来源引用使用原 step/id。
`regenerate.append_rewrite` 对父节点只复制索引关系，以便原分组逻辑继续工作。

## 3. 模型调用

`ModelClient` 直接调用 dojo 的 `LiteLLMClient.query`，与搜索实验共用通信、
密钥选择、请求重试、JSON 格式和解析机制。每个 run 的各 operator 按输入配置创建
客户端，全部客户端共享一个 semaphore，限制同时执行的请求。
模型、地址默认来自 `llm.client`，主入口的 `--base-url` / `--model-id` 可分别覆盖全部
run 和 operator；provider 和 Azure 设置仍来自来源配置。评测入口的同名参数用于 debug，
并传递给各 worker。现有 `.env` 中的
`PRIMARY_KEY_<MODEL>` / `PRIMARY_KEY` 也交给 dojo backend 读取。

| 调用 | 参数和返回 |
|---|---|
| `debug_hint` / `improve_hint` | temperature 0.2，max_tokens 8192，JSON Schema 描述非空 hint，thinking 使用服务默认行为 |
| `generate` | 沿用目标 operator 采样参数，返回完整 completion、usage、model |

hint 使用 backend 已有的结构化输出通道：默认 JSON mode，按 schema 校验并重试；
服务不支持 JSON mode 时使用 backend 已有的 tools 通道。JSON 内容前的
`<think>...</think>` 由共享 backend 去掉，再交给 dojo 的 JSON parser。
hindsight 额外检查 hint 包含实际文字，长轨迹的分段调用也使用相同接口。

完整生成的默认值是 temperature 0.6、top_p 0.95、开启 thinking、reasoning_effort medium；
原配置中显式记录的字段覆盖这些值，输出上限也来自原配置。
完整回答调用共享 backend 的 `include_reasoning=True`：服务单独返回
`reasoning_content` 时拼回 `thinking + </think> + answer`，已有内联 thinking 时原样保留。
这个选项只影响调用方需要的返回文本，搜索实验原来的普通文本返回保持不变。

请求超时和网络重试沿用 LiteLLM backend 的统一设置。hindsight 自身只校验
完整回答的结束状态、思考标记、代码前的计划、唯一 Python 代码块和语法；
校验失败直接抛出，避免再叠一层重试流程。

## 4. 评测与测试

案例生成、prepare、evaluate 是三个独立命令。prepare 集中描述所有评测输入、
每个方案的路径及历史指标；evaluate 按清单启动每个 GPU worker。
失败程序的 dojo debug 历史存在内存里，结束后统一写入该 run 的 `result.json`。
每次执行该命令都会重新运行清单中的全部方案。

从仓库根目录运行轻量测试：

```bash
source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo
export PYTHONPATH="$PWD/src:$PWD${PYTHONPATH:+:$PYTHONPATH}"
pytest -q src/mle_policy/test/test_hindsight.py src/mle_policy/test/test_hindsight_eval.py
```

测试使用伪模型、模拟 LiteLLM 响应和模拟执行器，覆盖轨迹选择、重试、最小文件集合、
显式 prepare、debug 次数，以及大/小 journal 到 GRPO 和合并数据的读取流程。
真实训练耗时与模型输出质量通过实际 allocation 中的实验检查。
