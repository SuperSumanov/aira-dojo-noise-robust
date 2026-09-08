# Upstream patches

这里保存针对其他现有分支、但不直接改写对方分支的可审计补丁。补丁必须注明精确 base commit、测试结果与
迁移边界；只有维护者审阅后才 cherry-pick。

## 当前ForeTS探索入口（2026-09-09，0L121）

### 可选后续：0012整轮共享请求额度（接0011）

065b0fba + 0010 + 0011 + 0012的完整tree为`49fd8698e6a5a3377224a2d92c65f354cb1eefa0`，已独立apply复建。
新模块`dojo.core.solvers.llm_helpers.backends.run_budget`用节点本地SQLite（不要NFS）先落dispatch intent，
在所有客户端/同节点进程间共享max_attempts和max_output_tokens。失败/超时/取消不返还，旧库不覆盖。
通过`FORETS_RUN_BUDGET_PATH`把同一绝对路径传给一run的所有worker调用；有该变量时unbounded调用禁止。
四算子应同时设置`bounded_run_budget_required=true`，没有预算库则拒绝发请求。
预算模块CLI只能初始化一次，参数`--path`、`--max-attempts`、`--max-output-tokens`均必填。
每run使用独立库和相同policy，不是8run共用库；节点本地文件丢失或切换allocation停止，不自动重建额度。
尚未自动接入Slurm worker初始化/归档；这里只验证手动提供库的实际调用路径，不把补丁称为完整运行器。

`phase1/forets_pilot_plan.py`生成统一四算子提议配置，不做模型调用或任务提交。
6项新CPU检查通过：8份真实Hydra配置4组完整哈希仅selector不同，实际GenericLLM四算子共享额度，
缺失/绕过/超限拒绝，失败/取消/重启无退款，损坏库拒绝，4进程24次竞争仅7次获额度。
回执`phase1/results/forets_bounds_20260909/run_budget_checks.json`。真实网络/API/GPU/任务均0。
API费用保持null；这里没有输入token界或供应商计费规则，不能声称美元cap。真实max_attempts尚未冻结批准。
日志可能被上游多handler重复输出，统计使用DB intent或attempt_id去重，不能数日志行。

实际检查命令（aira CPU环境，隔离目录；已完成，不因等待重跑）：

```bash
/research/d7/spc/yzyang4/venvs/aira/bin/python /research/d7/spc/yzyang4/forets-runbudget-20260909-cyPIf2/check_forets_run_budget_20260909.py --dojo-root /research/d7/spc/yzyang4/forets-runbudget-20260909-cyPIf2 --plan-root /research/d7/spc/yzyang4/forets-runbudget-20260909-cyPIf2 --source-tree 49fd8698e6a5a3377224a2d92c65f354cb1eefa0 --output /research/d7/spc/yzyang4/forets-runbudget-20260909-cyPIf2/checks.json
```

### 可选后续：0011有界传输（0L120）

0011是接在0010后的增量，组合tree `73fe9803cab2d325373dcc656842dfa35cf7d682`，只改LiteLLM backend。
在四个算子各自的`llm.generation_kwargs`中显式设置`bounded_transport: true`、
`bounded_request_timeout_seconds: 60`及正整数`max_tokens`后才启用；默认行为不变。
模式只允许一次adapter调用，不做SDK重试、JSON→tools fallback或格式重试。intent/return日志只含安全用量字段，
错误日志不带响应正文，失败仍保留记录。未知token/cost为null，不能当0或已证明免费。

9项人工completion检查通过；实际SDK连接本机HTTP模拟服务，200/429/500/schema-invalid各恰好1请求。
版本LiteLLM1.65.7/OpenAI1.72.0/httpx0.28.1；4次本机请求，0外部API。详见
`phase1/results/forets_bounds_20260909/{transport_checks,loopback_checks}.json`及同名脚本。
全run调用上限、美元上限、真正endpoint/代理重试及provider端超时取消仍需另验证，不能直接拿此声称同预算。

配套`phase1/forets_bounded_process.py`通过6项真实Linux无害进程检查；不提交Slurm，只有本地进程组控制。
它会回收同组后代，残留被回收时不把父进程0当完整成功；不覆盖旧运行。grace需计TERM等待和最终wait两段。
setsid逃逸/监督进程SIGKILL/不可中断IO需要集群側cgroup/step/allocation硬限，尚未替代这些设置。
结果`phase1/results/forets_bounds_20260909/process_checks.json`，无GPU/真实任务/受保护数据。
这些是预算入口的组成部分，不是整个GPU运行入口或模型效果已经验收。

### 0010累计基座

**只对独立、干净的`dojo-reproduce@065b0fbaa89e0eb663f2834ec768081f5d56394d`应用0010。**
不要改写活动生产checkout，不要再叠ForeTS的0005、0006、0007、0008、0009。

```bash
git apply --check /path/to/0010-ForeTS-cumulative-for-065b0fba-20260909.patch
git apply /path/to/0010-ForeTS-cumulative-for-065b0fba-20260909.patch
```

补丁是普通Git diff，不是mailbox patch。该exact base的完整应用树已复建核对为
`83ffe50f517dde409baba3a73e69ef5872dab1ac`，18个源码文件变化。
保留最新上游MCTS配置继承、uct_c=0.25、独立未选日志、JSON解析；同时保留我方共同候选批次、
零critic随机基线、预执行恢复边界、任务返回记录和离线raw critic加载。不是新方法/收益宣称。

修复了接入中的未选候选重试重复导出，以及JSON尾逗号修复误改字符串内容/原文日志。
真实源码、人工响应的8项定向CPU检查通过；两臂seed6/7的配置差异仅selection_policy。
`phase1/scripts/check_forets_upstream_065b_20260909.py`可复现修前/修后检查，结果见
`phase1/results/forets_e2e_pilot_20260908/upstream_065b_{before,after}.json`。
人工task/critic替身不等于真实端到端执行，不重复已完成旧测试作为进展。

`0009-ForeTS-offline-raw-critic-loader-20260908.patch`只保留为加载器的独立变更记录，已经包含在0010中。
显式参数`load_checkpoint(..., offline_base_dir=...)`及server的`--offline-base-dir`接受本地config/tokenizer目录，
要求组合的backbone.* / head.* safetensors、最多一个可见GPU；拒绝独立pickle head/不匹配state。
不传参数仍走旧入口。当前原始checkpoint没有rm_meta，服务沿用16384长度、0.25头部比例、task条件化默认值；
这不是从原训练记录重新证实的全部超参数。固定底座资料/权重位置见E2E_EXPLORATION_PILOT_20260908.md。

10项CPU加载检查已完成（真实小Qwen3 seed6/7与RewardScorer一致、异常拒绝、旧入口）；真实8B只有400键/形状与
分词器兼容性检查，未加载8B数值/执行8B前向。脚本`phase1/scripts/check_forets_offline_critic_20260908.py`及同目录回执。
GPU推理、HTTP实际服务、生成器API和真实任务尚待有界集成；本补丁不自行启动作业、授权费用或开放保护集。
用户在等学长回复API平台/地址/模型；不要把PRIMARY_KEY发送到猜测的服务。

## Prospective config-v2 producer hook（2026-08-27）

`0001-Add-prospective-config-v2-producer-hook-18-tests.patch` 精确基于学长
`dojo-reproduce@61459c0a1248900079dafed7c505afa87e476b40`，SHA-256=
`56a3e4b61918e1b06830712d418ed27ef5135017eab2b9e833b92c626054c9a5`。它把已经审计的
prompt-sensitive config-v2 指纹嵌入真实 `dojo.main_run` 启动路径，但默认关闭；仅在
`DOJO_CONFIG_V2_SIDECAR=1` 且显式提供 `DOJO_GENERATOR_RELEASE` 时，于 solver/task 构造前写
`producer.config_v2.jsonl`。输出不含 resolved solver、环境 dump、凭据、outcome 或 label；只含十个公开字段与
SHA-256。相同 run 的 resume 只允许复用逐字节一致的 sidecar，配置变化或竞争写入均拒绝且不覆盖。

fresh Linux no-smudge worktree 的 focused/full 为 `19 passed` / `84 passed, 1 skipped`；128 个合法变体与
`phase1/senior_experiment_config_v2.py` 逐 row、逐字节相同，4 类非法变体两边都拒绝；filename/blob
credential hits=`0/0`。正式根=
`/research/d7/spc/yzyang4/config-v2-producer-hook/verify_fa2151b_v4`，`SHA256SUMS` 自身 SHA-256=
`fbb9536c760c9a14ba9e7da044d1f32fe7f748ff54298f27fb1951bbe743c2b0`。

另在不读 env/outcome 的历史 schema-only smoke 中，按 mtime 预先冻结的 20 个真实 `dojo_config.json` 全部得到
candidate/reference 完全相同的 row/bytes；覆盖 7 tasks、2 clients、2 solver fingerprints、9 strata，forbidden
path opens=0、sidecar writes=0。formal root=
`/research/d7/spc/yzyang4/config-v2-producer-hook/real_config_smoke_65896b6_v1`，manifest SHA-256=
`80c8ab4b9ef5c23693aad00c7db75e81d81fd18f7339f65d6dff67e86003c47e`。这是兼容性验证，不是历史 provenance。

状态严格为 `PATCH_VERIFIED_NOT_DEPLOYED`：补丁没有改写学长分支，尚未观察到真实 producer sidecar，不能把
历史 archive 回填为 exact stratum，也不授权训练、GPU 矩阵或效果主张。8 月 19 日旧 exact-stratum patch 是
Cards/pair 生成后的 v1 同层过滤；本补丁解决的是更早的 outcome-before producer config/prompt 可识别性，两者不重复。

2026-08-30 再对学长最新 `dojo-reproduce@5baccb170ce287f9c8eed7b23ccf693a0268515a` 做 sparse/no-data
兼容复验：该 branch 仍未包含 `DOJO_CONFIG_V2_SIDECAR` 或 `DOJO_GENERATOR_RELEASE`；原补丁 SHA 不变且
`git apply --check`/apply 均无冲突，Linux focused=`19 passed`，compile 通过，4 个变更路径的 credential
filename/blob=`0/0`。复验没有展开 LFS data，也没有改写或推送学长分支。状态仍是
`PATCH_VERIFIED_NOT_DEPLOYED`；只有学长 review/apply 并在未来 producer 显式启用后，新 run 才能进入 exact-stratum
confirmation。

## Critic clean-confirmation overlay（2026-08-23）

以下四份补丁按顺序应用于学长 `dojo-reproduce@ac008af8b907d319b694f26b0ba9cf4053b3bf69`：

1. `0001-Harden-critic-confirmation-protocol.patch`，SHA-256
   `2fd5ca7b38e4277b68c2eb90b42c0f0ce85b8ab0ef687802e68ceeb8f0fc1fe2`；
2. `0002-Allow-fixed-step-critic-budget-calibration.patch`，SHA-256
   `89d7af494e436c4d5a7ed5c4a06e43c4d012cb26c3efd3c1e9f52bf00b3bd641`；
3. `0003-Record-critic-wall-clock-receipts.patch`，SHA-256
   `a4146bdc6ef3123e3b88a3b909352dd40db3cff992503919d4207c1756313f67`；
4. `0004-Emit-endpoint-score-receipts.patch`，SHA-256
   `237bbffe1130af74527d1a3febcfdcc3330b49a13b785c31039a79a1ac091242`。

集群 fresh no-smudge worktree 中四份补丁均通过 `git apply --check`，Python compile、launcher shell syntax、
`git diff --check` 以及 8 个聚焦测试文件；打印结果为 `36 passed in 46.79s`。第 4 份只把 evaluator 已经计算的
better/worse scalar scores 连同 margin 写入 one-shot receipt，并检查三者一致，不改变模型、输入或预测。该通过只证明工程 overlay 与精确
base commit 兼容，不证明模型效果，也不解除 source-batch provenance、全新 experiment-closed dev/frozen、Cards
LFS 和单旋钮门禁。当前不得直接运行 mixed launcher。
