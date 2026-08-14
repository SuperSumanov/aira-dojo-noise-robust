# Balanced continuation：真实 adapter 接口审计与冻结契约

日期：2026-08-14。当前裁决：**`REAL_ADAPTER_CONTRACT_VERIFIED_IMPLEMENTATION_PENDING`**。

本轮只审计现有 aira-dojo 执行/评分路径，并把真实 balanced-continuation adapter 必须满足的边界写成
fail-closed schema 与单测。它没有执行真实候选、调用 LLM、读取 frozen cohort 或打开 label vault，GPU/API
均为 0；因此不构成方法正结果，也不授权 E1/E2。

## 1. 为什么不能直接复用现有路径

### 1.1 MCTS/通用 operator 路径改变了干预

- `src/dojo/solvers/mcts/mcts.py:476` 的 `_expand_leaf_and_backprop` 会按 `num_children` 生成多个 child；
- 同一函数对 buggy child 自动进入 `debug_cycle`，后者最多执行 `max_debug_depth` 次；
- `parse_eval_result` 在 `src/dojo/solvers/mcts/mcts.py:583` 每次执行后还调用 analyze LLM；
- `src/dojo/core/solvers/operators/core.py:12` 的 `execute_op_plan_code` 会在抽取失败时重试。

这些行为都会破坏本实验“每个 transition 恰好一次 improve/debug operator call、一次候选执行、零重试、零
analyze call”的 equal-K 干预。因此真实 adapter 必须直接调用一次固定 operator，而不能套用当前 MCTS
expand/debug/parse 流程。

### 1.2 当前 MLEBenchTask 评分边界不满足 full-locked

- `src/dojo/tasks/mlebench/task.py:210` 的默认 `step_task` 在进程内调用完整 private-answer evaluator；
- 旧 HCE 默认配置为 `hce_search_frac=0.5`、`hce_val_frac=0.25`，即 50/25/25，而不是当前冻结的
  80/10/10 `D_train/D_search/D_val`；
- `src/dojo/tasks/mlebench/task.py:134-153` 在同一 orchestrator 进程计算 D_search 与 D_val，并把
  `dval_score` 放入 `AUX_EVAL_INFO` 和日志。即使搜索选择逻辑声称不使用它，D_val 仍对 orchestrator 可见；
- `src/dojo/tasks/mlebench/task.py:255` 的 final evaluation 同样调用完整 private evaluator。

因此不能通过“关掉 `use_test_score`”或改一个 config 来满足当前契约。D_search 与 D_val 必须由进程边界隔离的
外部 pristine evaluator 产生；D_test 在整个实验中不读取。

### 1.3 进程重置不等于 workspace 新鲜

`src/dojo/core/interpreters/python.py:299` 的 `reset_session=True` 会重建解释器子进程，但不会清空工作目录。
候选可遗留 cache、模型、临时文件或 submission，因此每个 rollout 必须使用全新的、不可复用的物理 workspace，
不能在同一路径删除若干文件后声称 fresh。

### 1.4 旧 fidelity worker 只能借鉴隔离概念

`phase1/fidelity_worker.py` 可以借鉴 public data 的只读容器挂载、host-side timeout/kill 和 immutable submission
snapshot；但它调用完整 `mlebench grade-sample`、包含一次启动重试，并复用/删除工作目录，不能直接作为本实验
adapter。

## 2. 已冻结的机器契约

新增 `phase1/balanced_continuation_real_contract.py`，严格限定：

1. worker contract 必须绑定精确 source commit、container、operator config、prompt、public dataset、opaque
   split manifest、D_search evaluator 和独立 D_val sealer 的 SHA-256；
2. 数据根必须是 canonical、非根目录的 POSIX 绝对路径；候选只能看到 public read-only mount，private path
   mount 必须为 false；
3. split 固定为 80/10/10 `D_train/D_search/D_val`；worker 只接收 D_search；D_val 只写 mode 0600 的
   sealed receipt；D_test rows read 必须为 0；
4. warm start 恰好一次，随后恰好 H 个 transition；上一步 buggy 才 debug，否则 improve；每步 operator call=1、
   operator retry=0、execution retry=0、analyze call=0；
5. execution、D_search、sealed D_val 三类 receipt 都绑定 rollout/workspace/task/ordinal/artifact identity；所有
   score 必须 finite，utility 必须等于冻结 orientation 作用后的 score；
6. visible step 的 exact-key schema 不含任何 D_val 字段，只含 sealed receipt 的 SHA-256 commitment；额外
   `dval_score` 字段会直接失败；
7. code、terminal、operator request/response 与所有 receipt 均由 SHA-256 绑定；credential-shaped bytes、
   NaN/Inf、布尔值冒充整数计数、路径穿越、身份错配和状态矛盾均 fail closed；
8. invalid-format operator response 被计为一次调用但不得虚构 code，也不得自动重试。

## 3. 当前验证证据

本地运行：

```text
python -m pytest -q \
  phase1/tests/test_balanced_continuation_real_contract.py \
  phase1/tests/test_balanced_continuation_manifest.py \
  phase1/tests/test_balanced_continuation_worker.py
34 passed in 3.12s
```

新增真实接口契约测试 12 项，覆盖 happy path、buggy→debug、旧 50/25/25 HCE 拒绝、D_val 字段注入、
private mount、D_test read、0600、NaN、跨 workspace identity、credential shape、one-call/no-retry、
invalid-format、POSIX 路径以及 receipt/operator request 篡改。

## 4. 仍未完成、不得越界解释

以下仍是 `PENDING`：

- 真实 public-only container executor；
- 80/10/10 split manifest 的实际生成与逐任务审计；
- 进程隔离的 D_search scorer 和 D_val sealer；
- 不读取 producer 实现的真实 adapter collection verifier；
- 0-GPU mock adapter 的端到端 receipt/workspace/replay 验证；
- E1 的 8 rollout jobs / 16 real candidate executions / 预计 3.24 GPU·时。

所以当前只证明“所需边界已被明确且能在 schema 层 fail closed”，没有证明真实 adapter 已实现，更没有证明
balanced continuation 的 label reliability、predictability 或 D_val utility 增益。下一步先完成 0-GPU mock
adapter；E1 仍保留显式批准门。

## 5. 后续执行更新：Linux mock 正式关门

精确 commit `eb2e693b2e1cca931148c504c68239b203b82731` 已在远端干净 worktree 正式通过：focused
tests 36 项、完整 `phase1/tests` 157 项、13/13 preflight；1 个 fresh rollout 产生 2 个 candidate、2 个
D_search scorer、2 个 D_val sealer 与 1 个 one-shot operator 子进程。独立 verifier 报告
`VERIFIED_ZERO_GPU_REAL_ADAPTER_MOCK`，retries=0、visible D_val fields=0、D_test rows read=0，Linux 实际
sealed mode=0600，GPU/API/Slurm=0/0/0。归档 SHA-256 为
`a58c86a10540b40daecebc118fe8179db9c6dde6b2e516c20ef67ceab56836a5`。

正式通过前四次失败均保留：错误 remote 名、无关历史 LFS object smudge、Linux module root 未加入 import path、
以及零命中 `grep` 在 `pipefail` 下被误判。前三次未创建 run root；第四次 worker/verifier 已通过但未完成最终
secret scan/tar，因此不冒充正式关门。修复均是 launcher/环境边界，没有更改 receipt 语义或 synthetic outcome。

用户随后明确批准既有 E1 矩阵，但批准不豁免 13 项 preflight。生产 public-only executor、真实 80/10/10
split、隔离 scorer/sealer 和真实 assignment 仍须全部实现、打印并独立验收后才能提交 8-job E1。
