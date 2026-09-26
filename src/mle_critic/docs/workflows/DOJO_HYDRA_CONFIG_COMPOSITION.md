# Dojo 的 Hydra 配置是怎么拼出来的

本文用一个真实命令，把 `dojo-reproduce` 分支的 Hydra 配置流程拆开讲清楚：YAML 之间怎么互相引用、
`@` 和 `override` 是什么意思、`???` 谁来填、`vars` 怎么把一条命令展开成多个 run。

文中所有结论都是在当前 checkout 上实际跑出来的，命令和输出都贴在对应位置。涉及的代码：

- 入口：`src/dojo/main_runner_job_array.py`
- 配置目录：`src/dojo/configs/`
- 配置对应的 dataclass：`src/dojo/config_dataclasses/`
- 环境：`source /research/d2/gds/zzchen2/anaconda/bin/activate aira-dojo`

## 0. 先给结论

1. **没有"运行时按目录名去读超参数"这个过程。** Hydra 在进程启动、业务代码执行之前，把
   `src/dojo/configs/` 下的若干 YAML 按各自的 `defaults` 声明合并成**一个**大 dict；命令行上的
   `a.b=c` 是合并完成之后的最后一道覆盖。
2. 这个 dict 随后被 `hydra.utils.instantiate(_cfg)` 转换成 dataclass 对象（`RunnerConfig`）。
   字段类型、字段是否缺失、字段名是否拼错，都是在这一步由 dataclass 决定的，YAML 自己不管这些。
3. `main_runner_job_array` 接着拿 `vars` 做笛卡尔积，把一份 Runner 配置展开成多个 `RunConfig`
   （每个 run = 一个 task × 一组 seed），再交给 launcher。

## 1. 入口在哪

`src/dojo/main_runner_job_array.py` 末尾：

```python
@hydra.main(version_base="1.3.2", config_path="configs", config_name="default_runner")
def main(_cfg: DictConfig):
```

- `config_path="configs"` 是相对于 `dojo` 包目录的，也就是 `src/dojo/configs`。Hydra 只在这个目录
  （以及 `hydra.conf` 这类内置 provider）里找配置。
- `config_name="default_runner"` 对应 `src/dojo/configs/default_runner.yaml`，这是整棵配置树的根。
- 命令里的 `+_exp=mlebench/aira_forets_dsf_medium_mle` 对应
  `src/dojo/configs/_exp/mlebench/aira_forets_dsf_medium_mle.yaml`。路径里的斜杠就是目录层级，
  没有别的映射规则。

## 2. 心智模型：配置是"槽位"，`defaults` 是"给槽位选实现"

先别把这些当路径读。Hydra 的配置更像**一张填好的表**：

```
最终配置（RunnerConfig）
├── launcher                          ← 槽位：可插拔的启动器
├── benchmark                         ← 槽位
├── solver                            ← 槽位
│   ├── memory                        ← 子槽位
│   └── operators.debug.llm.client    ← 更深的子槽位
└── interpreter                       ← 槽位
```

- **group（槽位名）**：一个"接口位置"的名字，物理上对应 `configs/` 下的一个目录。`launcher` 槽位
  对应 `configs/launcher/`。
- **option（实现名）**：槽位目录里的某个 YAML 文件，去掉 `.yaml` 就是它的名字。`configs/launcher/`
  里有 `slurm.yaml`、`srun_pool.yaml`、`local_gpu_pool.yaml`，于是 `launcher` 槽位有三个候选实现。
- **`- launcher: slurm`** 读作"`launcher` 槽位选 `slurm` 这个实现"。左边的 `launcher` 是槽位名，
  右边的 `slurm` 是候选名 —— **两边都不是路径**，所以不写 `.yaml`、也不写目录，Hydra 自己会去
  `configs/launcher/slurm.yaml` 取内容。
- **package（落点）**：这份实现的内容挂到最终配置树的哪个位置，默认就是槽位名。
- **defaults（依赖清单）**：这份 YAML 对哪些槽位负责、各自默认选谁。

用 Python 类比：

```python
cfg.launcher = SlurmLauncher()      # 从 configs/launcher/ 这组实现里挑一个
cfg.solver.operators.debug.llm.client = LiteLLMQwen3_8_27B(...)
```

### 2.1 defaults 里会出现的几种写法

| 写法 | 含义 |
| --- | --- |
| `- launcher: slurm` | 槽位 `launcher` 选实现 `slurm`，内容挂到 `launcher` |
| `- /solver: mlebench/fore_ts` | 槽位 `solver` 选实现 `mlebench/fore_ts`（实现本身放在子目录里），内容挂到 `solver` |
| `- /solver/client@debug.llm.client: litellm_4o` | 槽位 `solver/client` 选 `litellm_4o`，但内容挂到 `debug.llm.client`（相对父落点） |
| `- /solver/operators@operators: [a, b, c]` | 一个槽位一次选多个实现，全部挂到 `operators` |
| `- fore_ts`（没有冒号） | 纯路径包含：把某个目录下的 `fore_ts.yaml` 整个包含进来，见第 4 节 |
| `- override /solver: mlebench/mcts` | 改一个**已经被别人选过**的槽位，见 2.2 |
| `- solver: ???` | 这个槽位必须有人选，现在还没选（MISSING） |
| `+_exp=...`（命令行） | 往 defaults 列表里**新增**一条；删是用 `~` |

包名层面 `@` 的作用：`- 槽位@落点: 实现`。所以
`- /solver/client@solver.operators.debug.llm.client: litellm_deepseek_flash` 读作"`solver/client`
槽位选 `litellm_deepseek_flash`，内容挂到 `solver.operators.debug.llm.client`，而不是默认的
`solver.client`"。命令行里那条 `solver/client@solver.operators.debug.llm.client=litellm_qwen3.8-27b`
就是同一个 `槽位@落点` key，必须一字不差才能覆盖掉原来那条。

（package 的另一个来源是文件第一行的 `# @package xxx`；defaults 条目里显式写的 `@...` 优先级更高。
`_exp/` 下的文件都用 `# @package _global_`，原因见 2.3。）

### 2.2 `override` 是干什么的：一个槽位只能被选一次

规则就一句：**同一个槽位在整棵 defaults 树里只能被赋值一次**。于是：

- 想改别人（父配置、被包含的配置）已经选过的槽位 → 必须写 `override`。少了 `override` 直接报错（实测）：

  ```
  Multiple values for solver. To override a value use 'override solver: mcts'
  ```

  （如果省略了开头的 `/`，写成 `- solver: mlebench/mcts`，Hydra 会把它当成一个新槽位 `_exp/solver`，
  报的是 `Could not find '_exp/solver/mcts'` —— 连"重复赋值"都算不上。项目里槽位引用都带 `/` 就是
  为了避开这类歧义。）

- 写 `override` 指向一个没人选过的槽位 → 也报错（实测）：

  ```
  Could not override 'nosuch'. No match in the defaults list.
  ```

- `override` 条目必须放在 defaults 列表的最后，否则报
  `Overrides must be at the end of the defaults list`。

为什么要定这么啰嗦的规则：

- 让"基础配置"和"实验配置"分工。`default_runner.yaml` + `solver/mlebench/*.yaml` 把所有槽位的默认
  选择写全；每个实验配置只写差异。`_exp/mlebench/aira_forets_dsf_medium_mle.yaml` 三十来行就表达了
  "benchmark 换 dev、interpreter 换 jupyter、solver 换 fore_ts、四个 operator 的 client 换 X、
  再补一个 `reasoning_effort`"。没有 override 就得把槽位和默认值一起重抄一遍，基础配置一改所有实验
  都要跟着改。
- 如果两个地方都能给同一槽位赋值而不报错，出了问题时没人说得清最终用的是谁的值。Hydra 的做法是
  直接报错，逼你把意图写明白：**改**用 `override`，**加**用 `+`。

命令行上的 `launcher=srun_pool` 是"改"，`+_exp=...` 是"加"，和文件里是同一套规则。

### 2.3 为什么 `_exp/*.yaml` 第一行都要写 `# @package _global_`

因为 package 既决定内容挂在哪，也决定 override key 长什么样。以 `_exp/xxx.yaml` 为例：不写这行时，
这个文件属于组 `_exp`、落点是 `_exp`，于是它里面的 `solver:` 被理解成"槽位 `_exp/solver`、挂到
`_exp.solver`"，跟根节点上的 `solver` 完全是两回事（实测报错 `Could not find '_exp/solver/mcts'`；
就算改用绝对路径 `/solver`，也会变成 `Could not override 'solver@_exp.solver'`）。写上
`# @package _global_` 之后，文件内容直接摊在根节点，`- override /solver: ...` 才能对上根配置里的
`solver`。

### 2.4 合并顺序

`defaults` 类似 import，优先级从低到高：

1. 列表里越靠前的越先合并，靠后的覆盖靠前的；
2. 文件自己的正文（body）最后合并，所以自己优先于它引用的所有 defaults（Hydra 会自动补 `_self_`；
   根配置因此会打一条 `Defaults list is missing '_self_'` 的 UserWarning，属于正常噪音）；
3. 命令行覆盖优先级最高，在整棵树合并完之后统一施加。

实测小例子（`/tmp` 下同一个 Hydra 版本）：`root.yaml` 的 defaults 写成 `[a, b]`，`a.yaml` 里
`v: from_a`，`b.yaml` 里 `v: from_b`，结果是 `from_b`；而 `a.yaml` 的 defaults 写成 `[b]` 并且自己
写 `v: from_a`，结果是 `from_a`。

## 3. 根配置 `default_runner.yaml` 是个骨架

```yaml
defaults:
  - metadata: base_metadata
  - logger: base_logger
  - launcher: slurm
  - benchmark: ???
  - solver: ???
  - interpreter: ???

_target_: dojo.config_dataclasses.runner.RunnerConfig
```

- 它只声明"我要有 metadata / logger / launcher / benchmark / solver / interpreter 这六块"。
  metadata、logger、launcher 给了默认选项，另外三块是 `???`。
- `???` 是 OmegaConf 的 MISSING，意思是"必须有人填，现在没有值"。它**不是**"有默认行为"。
- 所以裸跑 `python -m dojo.main_runner_job_array`（不做任何覆盖）会在 Hydra 阶段直接失败：

```
You must specify 'interpreter', e.g, interpreter=<OPTION>
Available options:
	chroot_python
	jupyter
	python
```

- `_target_` 是给 `hydra.utils.instantiate` 用的：告诉 Hydra "把合并出来的这一坨 dict 当成
  `RunnerConfig` 这个 dataclass 来构造"。

## 4. 纯路径写法：`- fore_ts` 里的相对路径到底相对谁

defaults 里还有一种**没有冒号**的写法。本项目唯一的例子是 `solver/mlebench/fore_ts.yaml` 的第一行：

```yaml
defaults:
  - fore_ts                                        # 纯路径：包含某目录下的 fore_ts.yaml
  - /solver/operators@operators: [...]             # 有冒号：槽位写法；斜杠开头=从 configs/ 根算
```

`- fore_ts` 的含义是"把某个目录下的 `fore_ts.yaml` 整个包含进来"。这个"某个目录"**不是文件自己
所在的目录**，而是**选中这个文件的那条 defaults 条目的槽位目录**。同一份文件、同一行
`- helper`，被不同写法选中时结果不一样（实测）：

| 根配置里的写法 | 文件内部的 `- helper` 解析成 | 合并落点 |
| --- | --- | --- |
| `- thing: sub/impl`（槽位写法） | `thing/helper` | `thing` |
| `- thing/sub/impl`（纯路径写法） | `thing/sub/helper` | `thing.sub` |

实测输出：

```
# config_name=root_g  (defaults: [- thing: sub/impl])
thing:
  v_help: at_slot_dir      # 来自 conf/thing/helper.yaml
  v: impl

# config_name=root_p  (defaults: [- thing/sub/impl])
thing:
  sub:
    v_help: at_file_dir    # 来自 conf/thing/sub/helper.yaml
    v: impl
```

回到本项目：`solver/mlebench/fore_ts.yaml` 是被 `- /solver: mlebench/fore_ts` 这个**槽位写法**选中的，
所以它里面的 `- fore_ts` 的基址是槽位目录 `configs/solver/`，解析成 `configs/solver/fore_ts.yaml`。
这份文件因此读作："mlebench 专用的 fore_ts 变体 = 同组的通用 fore_ts 骨架 + 下面这些覆盖值"。

反过来的坑也实测过：如果根配置改成 `- solver/mlebench/fore_ts`（纯路径写法），基址就变成文件自己
所在的 `configs/solver/mlebench/`，同一个 `- fore_ts` 会指向它自己，直接 RecursionError。

两条实用规则：

- 想引用同组里更通用的那份配置 → 用 `- 名字`（纯路径，基址是同组目录），本项目里就是 `- fore_ts`。
- 想换槽位的实现 → 用 `- override /槽位: 实现`；拿不准就先用下面的命令看它到底解析成什么路径。

以 `/` 开头则从 `configs/` 根开始算，例如 `- /solver/operators@operators`。

```bash
python -m dojo.main_runner_job_array <你平时的那串参数> --info defaults
```

它会打印整棵合并树（哪个文件被谁选中、落在哪个 package），是排查配置最直接的工具。

## 5. 把这条命令逐条拆开

```bash
python -m dojo.main_runner_job_array \
  +_exp=mlebench/aira_forets_dsf_medium_mle \
  'benchmark.tasks=[google-quest-challenge]' \
  'solver/client@solver.operators.analyze.llm.client=litellm_qwen3.8-27b' \
  'solver/client@solver.operators.debug.llm.client=litellm_qwen3.8-27b' \
  'solver/client@solver.operators.draft.llm.client=litellm_qwen3.8-27b' \
  'solver/client@solver.operators.improve.llm.client=litellm_qwen3.8-27b' \
  metadata.git_issue_id=google-quest-challenge-4seeds \
  solver.execution_timeout=7200 \
  solver.time_limit_secs=86400 \
  solver.num_children=6 \
  solver.critic_host=127.0.0.1 \
  solver.critic_port=8765 \
  solver.critic_max_attempts=5 \
  solver.critic_top_k=3 \
  solver.num_children_to_choose=2 \
  launcher=srun_pool \
  launcher.debug=false \
  launcher.max_parallel=3 \
  launcher.cpus_per_step=6 \
  launcher.gpus_per_step=1 \
  logger.use_wandb=false
```

| 命令行片段 | Hydra 怎么理解 | 效果 |
| --- | --- | --- |
| `+_exp=mlebench/aira_forets_dsf_medium_mle` | 向 defaults 列表**追加**一条：group `_exp` 选 `mlebench/aira_forets_dsf_medium_mle` | 把 `_exp` 那份实验配置叠在整棵树最后，它的值最优先 |
| `benchmark.tasks=[...]` | 普通字段覆盖（`benchmark.tasks` 不是组名，没这个目录） | 把 benchmark 的任务列表换成这一个任务 |
| `solver/client@solver.operators.debug.llm.client=litellm_qwen3.8-27b` | group `solver/client` 的选项，落点 `@solver.operators.debug.llm.client` | 覆盖 `_exp` 里那条 `override ...: litellm_deepseek_flash` |
| `metadata.git_issue_id=...` | 普通字段覆盖 | 只是给这批 run 打一个标签，用于日志目录和 id；叫 `-4seeds` 不代表真的跑 4 个 seed |
| `solver.execution_timeout=7200`、`solver.num_children=6` 等 | 普通字段覆盖 | 单个 YAML 里已经存在的 key 才能这样覆盖 |
| `launcher=srun_pool` | group `launcher` 换成选项 `srun_pool` | 覆盖骨架里 `launcher: slurm` 的默认值 |
| `launcher.debug=false` | 普通字段覆盖 | 关掉 dry run，真正提交作业 |
| `logger.use_wandb=false` | 普通字段覆盖 | 不往 wandb 打点 |

### 为什么 `_exp` 前面必须有个 `+`

`_exp` 这个 group 只存在于目录 `src/dojo/configs/_exp/` 里，`default_runner.yaml` 的 defaults 列表
里并没有它。Hydra 的规则是：覆盖一个**已存在**的条目用 `key=value`，新增一个条目必须用
`+key=value`。所以不加 `+` 会得到：

```
Could not override '_exp'. No match in the defaults list.
To append to your default list use +_exp=mlebench/aira_forets_dsf_medium_mle
```

### `_exp` 文件本身在做什么

`src/dojo/configs/_exp/mlebench/aira_forets_dsf_medium_mle.yaml`：

```yaml
# @package _global_
defaults:
  - override /benchmark: mlebench/dev
  - override /interpreter: jupyter
  - override /solver: mlebench/fore_ts
  - override /solver/client@solver.operators.analyze.llm.client: litellm_deepseek_flash
  - override /solver/client@solver.operators.debug.llm.client: litellm_deepseek_flash
  - override /solver/client@solver.operators.draft.llm.client: litellm_deepseek_flash
  - override /solver/client@solver.operators.improve.llm.client: litellm_deepseek_flash

solver:
  operators:
    draft:
      llm:
        generation_kwargs:
          allowed_openai_params: ["reasoning_effort"]
          reasoning_effort: medium
    # improve / debug / analyze 同理

metadata:
  git_issue_id: to_be_determined

vars:
  metadata.seed: [1,2,3,4,5,6,7,8]
```

- 第一行 `# @package _global_`：内容直接摊到根节点，所以它能直接写 `solver:`、`metadata:`、`vars:`，
  也才能 override 到根配置里的槽位（原因见 2.3）。
- 四条 `override /solver/client@...`：operator YAML 自己声明的 client 是 `litellm_4o`，这里把它们
  统一改成 `litellm_deepseek_flash`（第 5 节的命令行又把它改成 qwen）。注意 `- override ...` 只对
  已经在 defaults 树里的条目有效；如果某个 group 从来没被引用过，就得用 `+` 追加，否则报
  `Could not override`。
- `solver.operators.*.llm.generation_kwargs` 这几段是**文件正文**，按第 2.4 节第 2 条，正文在所有
  defaults 之后合并，所以它们能盖掉 client YAML 自带的 `generation_kwargs`（合并是逐 key 的，
  这里新增了一个 key，不会把 client 的 `temperature` 顶掉）。
- `vars` 是给 `main_runner_job_array` 做扫参用的，Hydra 本身不认识它，见第 6.4 节。

## 6. 完整走一遍（实测）

### 6.1 第一步：合并成默认树

```bash
... --info defaults
```

节选（客户端那四条已经被命令行改成了 qwen）：

```
| Config path                                      | Package                             | _self_ |
---------------------------------------------------------------------------------------------
| metadata/base_metadata                           | metadata                            | False  |
| logger/base_logger                               | logger                              | False  |
| launcher/srun_pool                               | launcher                            | False  |
| benchmark/mlebench/dev                           | benchmark                           | False  |
| solver/memory/simple_memory                      | solver.memory                       | False  |
| solver/memory/debug_memory                       | solver.debug_memory                 | False  |
| solver/fore_ts                                   | solver                              | True   |
| solver/client/litellm_qwen3.8-27b                | solver.operators.debug.llm.client   | False  |
| solver/operators/mlebench/aira_operators/debug   | solver.operators                    | True   |
| solver/client/litellm_qwen3.8-27b                | solver.operators.draft.llm.client   | False  |
| solver/operators/mlebench/aira_operators/draft   | solver.operators                    | True   |
| solver/client/litellm_qwen3.8-27b                | solver.operators.improve.llm.client | False  |
| solver/operators/mlebench/aira_operators/improve | solver.operators                    | True   |
| solver/client/litellm_qwen3.8-27b                | solver.operators.analyze.llm.client | False  |
| solver/operators/mlebench/aide_operators/analyze | solver.operators                    | True   |
| solver/mlebench/fore_ts                          | solver                              | True   |
| interpreter/jupyter                              | interpreter                         | False  |
| default_runner                                   |                                     | True   |
| _exp/mlebench/aira_forets_dsf_medium_mle         |                                     | False  |
```

几处值得注意的地方：

- `solver/mlebench/fore_ts` 之下的 `solver/fore_ts` 就是第 4 节讲的相对路径解析结果；
  `solver/fore_ts` 又带进来 `solver/memory/simple_memory` 和 `solver/memory/debug_memory`。
- `solver/operators/...` 那四行来自 `solver/mlebench/fore_ts.yaml` 里的这一个默认项：

  ```yaml
  defaults:
    - fore_ts
    - /solver/operators@operators:
      - mlebench/aira_operators/debug
      - mlebench/aira_operators/draft
      - mlebench/aira_operators/improve
      - mlebench/aide_operators/analyze
  ```

  这是 Hydra 的"一个组选多个选项"写法：四条都合并到 `solver.operators`，各自文件的顶层 key
  （`debug` / `draft` / `improve` / `analyze`）互不冲突，所以拼成了一个字典。合并顺序是列表里
  越靠后越优先，如果两份文件写了同一个 key，后面的赢。
- `_exp/...` 排在最下面，说明它是最后合并的，所以它的值优先级高于前面的骨架。

### 6.2 第二步：合并结果里到底有哪些值

```bash
... --cfg job
```

关键字段（实际输出，这里为了绕开第 11 节那个未提交改动，额外加了 `+solver.critic_type=llm`）：

```text
step_limit: 10000          # 来自 solver/mlebench/fore_ts.yaml，命令行没动它
num_children: 6            # YAML 里是 5，被命令行覆盖成 6
max_debug_depth: 20
max_llm_call_retries: 3    # 来自 solver/fore_ts.yaml（骨架里唯一没留 ??? 的搜索参数）
max_debug_time: 1000000000.0
data_preview: true
use_test_score: false
use_complexity: false      # 骨架里是 ???，这里被 mlebench/fore_ts 填成 false
execution_timeout: 7200    # 命令行覆盖
time_limit_secs: 86400
uct_c: 0.25
critic_host: 127.0.0.1
critic_port: 8765
critic_max_attempts: 5
critic_top_k: 3
num_children_to_choose: 2
```

四个 operator 的 LLM 客户端（命令行覆盖生效）：全部是 `qwen3.8-27b`、
`http://127.0.0.1:8000/v1`、`provider: selfhosted`；`generation_kwargs` 是

```text
draft / improve / debug: {temperature: 0.6, top_p: 0.95, allowed_openai_params: [reasoning_effort], reasoning_effort: medium}
analyze:                {temperature: 0.5,              allowed_openai_params: [reasoning_effort], reasoning_effort: medium}
```

即：`temperature` 来自 operator YAML，`reasoning_effort` 来自 `_exp` 的正文。

### 6.3 第三步：YAML → dataclass

`main()` 里第一句就是：

```python
og_cfg: RunnerConfig = hydra.utils.instantiate(_cfg)
```

到这里，`solver` 节点会被构造成 `ForeTSSolverConfig`（由
`solver/mlebench/fore_ts.yaml` 里的 `_target_` 决定），多余字段、类型不对、`???` 没填，都在这一步
报错。报错长这样（示例是 dataclass 里有 `critic_type` 但没有任何 YAML 提供它）：

```
omegaconf.errors.MissingMandatoryValue: Structured config of type `ForeTSSolverConfig`
has missing mandatory value: critic_type
    full_key: solver.critic_type
```

### 6.4 第四步：`vars` 展开成多个 run

`main()` 剩下的逻辑（`src/dojo/main_runner_job_array.py`）：

```python
cmd_vars = dict(og_cfg.vars)
keys = list(cmd_vars.keys())
for values in itertools.product(*(cmd_vars[key] for key in keys)):
    single_vars_comb = dict(zip(keys, values))
    runner_cfg = copy.deepcopy(og_cfg)
    for k, v in single_vars_comb.items():
        override_config(runner_cfg, k, v)   # 直接改 dataclass 字段
    runner_configs.append(runner_cfg)
```

- `vars` 的 key 是 dotted path，value 是一个列表；Hydra 不参与这一步，纯粹是 Python 层的笛卡尔积。
- `_exp` 里写的是 `vars: {metadata.seed: [1..8]}`，所以这一条命令实际会展开成 **8** 个 run。
  `metadata.git_issue_id` 叫 `-4seeds` 只是标签；要真的跑 4 个 seed，得自己覆盖
  `'vars.metadata.seed=[1,2,3,4]'`。
- 验证方式（dry run，不提交任何作业）：

  ```bash
  ... launcher.debug=true
  ```

  实测输出（每个 run 一段，共 8 段）：

  ```
  metadata.seed                 1
  task.name                     google-quest-challenge
  ============================================================
  metadata.seed                 2
  task.name                     google-quest-challenge
  ============================================================
  ...
  ```

- 注意 `launcher.debug=true` 的作用范围比想象中大：`main_runner_job_array._main()` 在 debug 时
  只打印、不启动；但 `SrunPoolConfig.debug` 同时也是 launcher 自己的配置字段（`srun_pool.yaml`
  里默认就是 `true`）。用 `launcher=srun_pool` 时两者是同一个字段。
- `_main()` 里还有一层展开：`runner_cfg.benchmark.to_cfg_list()` 会把 `benchmark.tasks` 里的每个
  任务变成一份 `RunConfig`。所以总 run 数 = seed 数 × 任务数。这里任务只有 1 个。

### 6.5 第五步：launcher 分派

`launch_jobs()` 按 launcher dataclass 的类型走三条不同的路：

- `LocalGpuPoolConfig` → `LocalGpuPoolLauncher`
- `SrunPoolConfig` → `SrunPoolLauncher`
- `SlurmConfig` → submitit `SlurmExecutor` 批量提交

提交之前，`launch_jobs()` 会先决定用哪个代码快照：pool 类 launcher 会先尝试复用已有的快照
（`resume_snapshot_path`），没有就新拍一份到 `$LOGGING_DIR/aira-dojo/snapshots/<时间戳>`；
Slurm batch 路径则每次都新拍。job 在快照目录里执行，所以启动之后再改 YAML 或代码，不会影响
已经提交的这一批 run。

## 7. `use_complexity: ???` 这种要不要手动传？

不用。`???` 只是"必须有人填"的占位，谁都可以填：

`src/dojo/configs/solver/fore_ts.yaml` 是**留给别人继承的接口**，把搜索相关的字段全留成了 `???`：

```yaml
operators: ???
step_limit: ???
num_children: ???
max_debug_depth: ???
max_debug_time: ???
data_preview: ???
use_test_score: ???
use_complexity: ???
```

`src/dojo/configs/solver/mlebench/fore_ts.yaml` 给它填了具体值（`use_complexity: false`、
`num_children: 5`、`step_limit: 10000` 等）。而 `_exp` 里有 `override /solver: mlebench/fore_ts`，
所以走 `_exp` 时这些值都会被填上，不需要命令行传。

如果绕过它直接选 `solver=fore_ts`，合并结果里就是一堆 `???`：

```bash
python -m dojo.main_runner_job_array solver=fore_ts benchmark=mlebench/dev \
    interpreter=jupyter launcher=srun_pool --cfg job
```

```
{'step_limit': '???', 'num_children': '???', 'max_debug_depth': '???', 'max_debug_time': '???',
 'data_preview': '???', 'use_test_score': '???', 'use_complexity': '???', 'operators': '???'}
```

可以看到 `--cfg job` 会把没填的 `???` 原样打出来，是确认"某个字段最终是谁填的"最省事的办法。
（`export_search_results`、`execution_timeout`、`time_limit_secs`、`max_llm_call_retries` 这类在骨架
里就写了值的字段则不受影响。）

## 8. 常见报错对照

| 报错 | 原因 | 处理 |
| --- | --- | --- |
| `Could not override 'X'. No match in the defaults list. To append ... use +X=` | 想改的条目不在 defaults 树里（例如 `_exp`、某个从没被引用的 group） | 改成 `+X=...` |
| `Could not override 'solver.foo'. Key 'foo' is not in struct` | 想覆盖的 key 在任何 YAML 里都不存在（常见于刚在 dataclass 里加的字段） | 用 `+solver.foo=...`，或者直接写到某个 YAML 里 |
| `Multiple values for solver. To override a value use 'override solver: mcts'` | 同一个槽位被赋值两次，其中一条没写 `override` | 把"改"的那条改成 `- override /solver: ...` |
| `Overrides must be at the end of the defaults list` | `override` 条目放在了被它覆盖的条目前面 | 把 `override` 挪到 defaults 列表末尾 |
| `You must specify 'interpreter'` | 骨架里的 `???` group 没有人选 | 加 `interpreter=jupyter` 之类的覆盖，或者用带 `override /interpreter` 的 `_exp` |
| `MissingMandatoryValue: ... has missing mandatory value: X` | dataclass 里该字段是 MISSING，但合并后的 YAML 没有提供 | 在 YAML 里补上，或命令行 `+...` 传进去 |
| `Could not find '_exp/solver/mcts'` | `_exp/*.yaml` 少了 `# @package _global_`，相对槽位变成了 `_exp/solver` | 第一行补 `# @package _global_` |
| 命令行 `launcher=srun_pool` 报 `Could not override 'launcher'. No match in the defaults list.` | 这个组是用纯路径（`- launcher/slurm.yaml`）包含进来的，没有槽位身份，覆盖不到 | 改用槽位写法 `- launcher: slurm`（对同一个文件，槽位写法才能被覆盖，实测） |
| `RecursionError` / 循环引用 | defaults 里的相对/绝对路径写歪了（见第 4 节） | 用 `--info defaults` 看实际解析出来的路径 |

## 9. 运行产物落在哪

- 每个 run 自己的最终配置：`$LOGGING_DIR/aira-dojo/user_${USER}_issue_${git_issue_id}/${id}/dojo_config.json`。
  路径模板写在 `src/dojo/config_dataclasses/logger.py` 的 `LoggerConfig.output_dir`。
- `${id}` 由 resolver `generate_id` 生成，格式是
  `user_{user}_issue_{issue}_seed_{seed}_id_{hash}`。hash 覆盖除了标注 `exclude_from_hash` 之外的
  所有字段，所以改一个 YAML 数值会落到新目录，不会覆盖旧结果。
- 代码快照：`$LOGGING_DIR/aira-dojo/snapshots/<时间戳>`（第 6.5 节）。
- 自定义 resolver 注册在 `src/dojo/config_dataclasses/omegaconf/resolvers.py`：
  `${get_mlebench_data_dir:}`、`${get_superimage_dir:}`、`${get_git_commit_id:}`、`${generate_id:}`、
  `${get_current_time:}`。带冒号的这种写法是自定义 resolver，不是环境变量；对应的值来自 `.env` /
  进程环境（例如 `MLE_BENCH_DATA_DIR`、`SUPERIMAGE_DIR`、`LOGGING_DIR`）。

## 10. 排查用的命令

```bash
# 看合并树：谁被谁选中、落在哪个 package
python -m dojo.main_runner_job_array <参数> --info defaults

# 看合并后的 dict（未解析的 ${...} 和 ??? 会原样显示）
python -m dojo.main_runner_job_array <参数> --cfg job

# 解析所有插值（需要 LOGGING_DIR / MLE_BENCH_DATA_DIR 等环境变量已设置）
python -m dojo.main_runner_job_array <参数> --cfg job --resolve

# 干跑：只打印每个 run 的扫参组合，不提交作业
python -m dojo.main_runner_job_array <参数> launcher.debug=true

# 完整 Python 栈
HYDRA_FULL_ERROR=1 python -m dojo.main_runner_job_array <参数>
```