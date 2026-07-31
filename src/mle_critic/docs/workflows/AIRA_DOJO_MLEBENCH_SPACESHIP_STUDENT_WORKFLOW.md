# 第二部分：学生研究分支（不在当前 checkout）

## 10. 学生流程增加和改变了什么

以下内容用于解释 `phase1-value-critic` 等历史研究分支与原协议的差异。所列 DeepSeek/HCE 配置和实现**不在当前 `dojo-reproduce` checkout 中**，也不应为了正式复现而迁回本分支。

### 10.1 新增 DeepSeek client

新增：

```text
src/dojo/configs/solver/client/litellm_deepseek_pro.yaml
src/dojo/configs/solver/client/litellm_deepseek_flash.yaml
```

模型配置：

```text
deepseek-v4-pro
deepseek-v4-flash
https://api.deepseek.com
```

使用：

```dotenv
PRIMARY_KEY_DEEPSEEK_V4_PRO=...
PRIMARY_KEY_DEEPSEEK_V4_FLASH=...
```

或者通用 `PRIMARY_KEY`。

### 10.2 新增 DeepSeek experiment

Spaceship 相关新增配置：

```text
src/dojo/configs/_exp/mlebench/deepseek_smoke.yaml
src/dojo/configs/_exp/mlebench/deepseek_greedy_spaceship.yaml
src/dojo/configs/_exp/mlebench/deepseek_mcts.yaml
src/dojo/configs/_exp/mlebench/deepseek_greedy_hce_spaceship.yaml
```

这些文件不属于原 AIRA-Dojo 默认流程。

### 10.3 Smoke 改用 Python interpreter

`deepseek_smoke.yaml` 明确选择：

```yaml
interpreter: python
solver: mlebench/greedy
task: mlebench/spaceship-titanic
clients: deepseek-v4-pro
step_limit: 5
```

Python interpreter 本身原仓库已有，但原始 `run_example` 和正式 MLE-bench experiments 使用的是 Jupyter。学生 smoke 当时改用宿主 Python，是为了绕过 Singularity runtime backend 落地前的 Apptainer/user namespace 限制；当前默认 Jupyter 配置已经可以直接使用 Singularity。

因此它与原流程的主要环境差异是：

| 项目 | 原仓库默认 | 学生 smoke |
|---|---|---|
| 执行环境 | superimage 内 Jupyter kernel | 宿主 Python multiprocessing 子进程 |
| 数据提供 | container bind | `workspace_agent/data` 符号链接 |
| 可用依赖 | superimage 固定依赖 | 当前 Conda/宿主环境依赖 |
| LLM | GPT-4o/o3 | DeepSeek Pro/Flash |
| 隔离性 | 较强 | 较弱 |

### 10.4 Python interpreter guard 修复

学生在 `src/dojo/core/interpreters/python.py` 增加：

```python
global_scope["__name__"] = "__main__"
```

这样候选代码中的：

```python
if __name__ == "__main__":
    main()
```

会在 Python interpreter 中正常执行。原代码没有显式设置该值。

该改动不影响 Jupyter 原流程，因为 Jupyter 走另一套 interpreter 实现。

### 10.5 修改 AIRA operator prompts

学生在 draft/debug/improve prompts 中加入：

- 强制处理 object/string/categorical dtype。
- 首个方案优先简单、鲁棒、避免过早 Optuna。
- 强制最后打印：

```text
FINAL_VALIDATION_SCORE: <number>
```

这些要求会直接改变 LLM 生成代码的分布，所以即使使用相同模型和 seed，也不能视为原仓库 prompt 的复现。

### 10.6 修改 Greedy/MCTS metric 解析

学生增加正则 fallback：当 analyze LLM 没能给出结构化 metric 时，从 stdout 提取：

```text
FINAL_VALIDATION_SCORE: 0.8123
```

学生还改变了 buggy 判定：

```text
原仓库：analyze is_bug 也参与判定
学生版：忽略 analyze is_bug，只看退出码、metric 和 submission validity
```

这会改变搜索树中哪些节点被 debug、哪些节点被保留，因此属于实质性算法行为变化。

### 10.7 新增 HCE 协议

学生新增：

```text
src/dojo/tasks/mlebench/hce_eval.py
```

并修改：

```text
src/dojo/tasks/mlebench/task.py
src/dojo/config_dataclasses/task/mlebench.py
src/dojo/configs/task/mlebench/_default.yaml
```

HCE 把私有答案固定切为：

```text
D_search / D_val / D_test
```

支持：

```text
task.arm=full
task.arm=naive
task.arm=consistency
```

搜索 fitness 可以来自外部 `D_search`，而不是候选自报 validation。它是学生研究噪声鲁棒评估的实验协议，不属于原 MLE-bench/AIRA 默认评测。

## 11. 学生普通 DeepSeek smoke 怎么走

命令：

```bash
python -m dojo.main_run \
  +_exp=mlebench/deepseek_smoke \
  logger.use_wandb=False \
  metadata.seed=1
```

链路：

```text
同一份 prepared/public 和 prepared/private
        |
        v
deepseek_smoke.yaml
        |
        +-- Python interpreter
        +-- Greedy
        +-- DeepSeek Pro operators
        `-- step_limit=5
        |
        v
workspace_agent/data -> prepared/public
        |
        v
DeepSeek 生成带 FINAL_VALIDATION_SCORE marker 的代码
        |
        v
宿主 Python 子进程执行
        |
        v
标准 MLEBenchTask submission 校验与 private score
        |
        v
学生版 Greedy metric fallback/buggy 判定
```

`deepseek_smoke` 的 `step_limit=5`，root 占 step 0，实际候选数量有限；同时默认 `num_drafts=5`，所以 smoke 通常还没进入完整 improve 阶段。

要观察 draft 后的 improve/debug：

```bash
python -m dojo.main_run \
  +_exp=mlebench/deepseek_smoke \
  logger.use_wandb=False \
  metadata.seed=1 \
  solver.step_limit=12
```

这条命令适合复现学生自己的采数协议，不适合替代第一部分的原仓库流程。

## 12. 学生 HCE 流程怎么走

命令示例：

```bash
python -m dojo.main_run \
  +_exp=mlebench/deepseek_greedy_hce_spaceship \
  logger.use_wandb=False \
  metadata.seed=1 \
  task.arm=full
```

HCE 与普通学生 smoke 的差异：

```text
普通 smoke：
  搜索 metric = 候选自报 validation
  private score = 只记录到 metric.info.score

HCE：
  搜索 metric = D_search 外部评分或其低成本 proxy
  D_val score = 保存为辅助/最终选择信息
  D_test = 不在搜索中评分
```

不同 arm：

| arm | 搜索信号 |
|---|---|
| `full` | 完整 D_search 真实评分 |
| `naive` | D_search 子采样 proxy |
| `consistency` | 多次 proxy 均值加方差惩罚 |

这套协议改变了 private labels 的使用方式，不能与原仓库默认分数直接比较。

## 13. 学生流程的输入输出和产物

数据准备结果与第一部分相同，但 Python interpreter 工作区表现不同：

```text
<run_dir>/workspace_agent/
`-- data -> $MLE_BENCH_DATA_DIR/spaceship-titanic/prepared/public
```

候选代码在宿主 Python 子进程中执行，输出仍必须是：

```text
./submission.csv
```

学生 prompt 额外要求：

```text
FINAL_VALIDATION_SCORE: <number>
```

普通学生流程序列化后的节点仍包含：

```text
metric              候选 validation 或 fallback marker
metric_info.score   MLE-bench private accuracy
is_buggy
code
term_out
parents / children
```

HCE 节点还会包含：

```text
metric_info.arm
metric_info.dsearch_fitness
metric_info.dsearch_info
metric_info.dval_score
metric_info.n_search
metric_info.n_val
```

## 14. 两套流程的直接对比

| 维度 | 原仓库流程 | 学生流程 |
|---|---|---|
| 代表配置 | `run_example`, `aira_greedy_o3` | `deepseek_smoke`, `deepseek_mcts`, `deepseek_greedy_hce_*` |
| 主要 LLM | GPT-4o/o3 | DeepSeek Pro/Flash |
| 默认执行环境 | Jupyter + superimage | Python interpreter |
| 数据接口 | 容器只读 bind `./data` | 宿主 workspace symlink `./data` |
| 原始 prompt | AIRA/AIDE 默认 prompt | 加 dtype、简单 baseline、marker 要求 |
| Metric 解析 | analyze LLM 结构化输出 | analyze + marker 正则 fallback |
| Buggy 判定 | 包含 analyze `is_bug` | 忽略 analyze `is_bug` |
| 默认搜索信号 | self-reported validation | 普通版相同；HCE 改为 D_search 外部信号 |
| 私有分数 | 记录到 aux info | 普通版相同；HCE 进一步切分私有答案 |
| 是否适合原结果复现 | 是 | 否，属于研究 fork |