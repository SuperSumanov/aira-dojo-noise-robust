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

`ModelClient` 复用 dojo 的 `OpenAIClient.query_raw`，同步请求放到线程中，
每个 run 的各 operator 按输入配置创建客户端，所有客户端
共享一个 semaphore 限制同时发出的请求。模型和地址来自 `llm.client`，
密钥从现有 `.env` 的 `PRIMARY_KEY_<MODEL>` 或 `PRIMARY_KEY` 读取，模型专用密钥优先。
HTTP 超时 1800 秒，关闭环境代理读取，
SDK 自带重试次数为 0。

| 调用 | 参数和返回 |
|---|---|
| `debug_hint` / `improve_hint` | temperature 0.2，max_tokens 8192，关闭 thinking，JSON hint |
| `generate` | 沿用目标 operator 记录的采样参数，返回 completion、usage、model |

长轨迹的 `part=True` 调用与最终 hint 调用使用相同的生成参数。
完整生成的默认值是 temperature 0.6、top_p 0.95、开启 thinking、reasoning_effort medium；
原配置中显式记录的字段覆盖这些值，输出上限也来自原配置。

provider 特有的 `chat_template_kwargs`、`top_k`、`min_p`、`repetition_penalty`
放入 SDK 的 `extra_body`。若服务将 reasoning 与 content 分开返回，客户端拼成
`thinking + </think> + answer`，保留原生思考内容。

每次调用最多三次尝试，间隔一秒、两秒。hint 校验 JSON 中有非空字符串 `hint`；
首次返回格式错误时，后续尝试附带校验错误并使用 JSON Schema 约束。
完整回答检查 `finish_reason=stop`、思考结束标记、代码前的计划、唯一 Python 代码块
及 Python 语法。HTTP 400/401/403/404 直接报错，其余最终错误原样抛出。

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

测试使用伪模型、模拟 HTTP 响应和模拟执行器，覆盖轨迹选择、重试、最小文件集合、
显式 prepare、debug 次数，以及大/小 journal 到 GRPO 和合并数据的读取流程。
真实训练耗时与模型输出质量通过实际 allocation 中的实验检查。
