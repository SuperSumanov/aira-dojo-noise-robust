# Balanced continuation E1：真实执行裁决

日期：2026-08-14。最终裁决：**`INVALID_FOR_METHOD_CLAIM_ENGINEERING_FAILURE_REPAIRED_NOT_RERUN`**。

本轮不是“balanced continuation 无效”的负结果。它完成了真实执行和完整性闭环，但 outcome adapter 与
operator adapter 同时失效，导致 8 个 rollout 中没有一个 warm→continuation 可配对结果。稳定论文主线仍是
run-clean、decision-local 数据集/benchmark 与 first-960 前瞻确认；本轮只决定 gated 支线下一道工程门。

## 1. 冻结运行实际发生了什么

- source commit：`e59a759d99dd490b6f8a0011c66dd7c772307b28`；
- run root：`/research/d7/spc/yzyang4/balanced-e1-real-e59a759d-a1`；
- 2 tasks × 1 anchor/task × 2 siblings × 2 replicates × H=1：8 rollout jobs；
- 16 candidate attempts、14 candidate processes、8 operator API calls；retry=0、analyze=0、D_test rows=0；
- candidate wall=`2047.6709687478572` 秒，折合 `0.5687974913188492` GPU·时；
- 8 个 Slurm 元素均 `COMPLETED 0:0`；537 条顶层 manifest 逐一重算，mismatch=0；
- complete-coverage 关闭后才打开 16 个 sealed receipts。collection verifier 不 import producer，独立重建
  8 rollout、4 sibling、2 task 行，collection summary SHA-256 为
  `576c897a17220b02f9ff1ed5ded38685bcd1da6b009e90ba0eeca73648af3adf`。

这些事实证明执行、收集、seal 与账本闭环发生过；它们不保证被收集的效应值具有科学含义。

## 2. 为什么原 collection 不能解释

### 2.1 outcome adapter 的确定性接口错误

每个 public submission 模板包含完整 public ID universe，而 private `D_search` 与 `D_val` 各占其中一半：

- `spaceship-titanic`：public 1562 行，D_search 781，D_val 781；
- `tabular-playground-series-may-2022`：public 159998 行，D_search 79999，D_val 79999；
- 两个任务均满足 private 两子集不交且其并集逐 ID 等于 public。

v1 scorer 却要求 candidate submission 的 ID 集恰好等于单个 private 子集，因而会拒绝遵循 public
`sample_submission.csv` 的正确输出。干净 commit
`f352b013c67fb1b98b17391ba32711faaa780367` 在不重跑 candidate、不调用 API、不启动 GPU 的条件下，
用修复后的“先做 full-public-ID 校验、再按 private ID 取子集评分”重放：旧有效数为 `0/16`；修复后
D_search/D_val 均为 `6/16`。这 6 个全部来自 warm step，continuation 仍为 `0/8`，可配对 gain 为 0 个。

所以原表中的全零 utility、全 tie、`0/8` positive gain 是 measurement artifact，既不能写成正结果，
也不能写成方法失败。

### 2.2 operator adapter 的完整脚本失败

8 个 continuation 调用的 completion tokens 全部等于冻结上限 8192。逐 execution 与 terminal 归因为：

- `invalid_format`：2；
- Python `SyntaxError`：2；
- Python `NameError`：4。

6 个被启动的 continuation 代码都在约 0.49 秒内失败，表明执行到的是片段、伪代码或缺少上下文的 snippet，
不是一个完整的替代训练脚本。旧 extractor 取最后一个闭合 fenced block；长响应被截断时可能只留下较早的
短 snippet。旧 run 没有保存 raw response，仅保存 SHA，因此不能恢复完整响应、换 extractor 后补算。

零执行诊断 artifact SHA-256 为
`4f99b146ad9bcc1e42c4cf466806c23944de4c6e2572c466e8b7cfa9ce9b26a5`；它明确标记
`method_claim_allowed=false` 与 `repair_rerun_required_for_e1_method_result=true`。

## 3. 修复与两个不同边界的工程探针

修复版做了四件事：

1. scorer 先要求 full public sample ID universe 精确匹配，再对 sealed private ID 子集评分；
2. prompt 要求恰好一个、无 prose、可独立运行的完整 Python replacement script；
3. 执行前 fail closed：单 fenced block、AST 编译、无 Ellipsis、长度下界、至少 20 行，并要求
   `read_csv/submission.csv/to_csv/FINAL_VALIDATION_SCORE`；
4. raw response 以 mode 0600 保存，summary 绑定 intent、prompt、response 与 extracted code SHA。

第一道单独预注册只做两次 **Qwen 备选 operator** 调用，不执行输出代码：

| task | finish | completion tokens | extracted lines | gate |
|---|---:|---:|---:|---:|
| spaceship-titanic | stop | 1579 | 172 | pass |
| tabular-playground-series-may-2022 | stop | 1014 | 104 | pass |

probe 总计 API=2、GPU jobs=0、candidate executions=0、retry=0，状态
`PASS_OPERATOR_ONLY_GATE`；summary SHA-256 为
`a30aa463a75ead9fa48fcd53a37921749425ac4a8ee696b18c2d0be33413ed1d`。这证明修复后的 adapter
配合 Qwen 至少能在两个冻结样本上获得未截断、结构合规的完整脚本；没有执行脚本，所以不说明分数、gain
或 search utility。更重要的是，冻结 E1 的 production operator 是 DeepSeek，不能用此表证明原 operator 已修复。

第二道门因此精确匹配原 production profile：`deepseek-v4-flash`、temperature=0.6、top_p=0.95、
max output=8192、system role、client timeout=180；同样恰好 2 calls、0 GPU、0 candidate execution、0 retry：

| task | channel | finish | completion tokens | extracted lines | gate |
|---|---|---:|---:|---:|---:|
| spaceship-titanic | content | stop | 7636 | 178 | pass |
| tabular-playground-series-may-2022 | reasoning_content | length | 8192 | 0 | fail |

总状态为 `FAIL_PRODUCTION_MODEL_OPERATOR_GATE`；summary SHA-256 为
`1409719b01fc788797d299b341bf55244313090be496bc4c751a95614e12623f`。tabular 的失败重现了原 E1 的
reasoning 截断机制：输出顶满上限且不满足恰好一个完整代码块。协议禁止重试、增 token、关 reasoning 或换模型
“修成通过”。因此原 DeepSeek production path 仍关闭；Qwen 是未来新 contract 的候选，不是原 run 的修补。

## 4. 严格结论与下一门

- 原 E1：工程执行完成，**方法估计不可识别**；从论文结果表撤回全部零分/tie/gain。
- Qwen 备选探针：最低完整脚本门 2/2 通过，但不是 production-matched。
- DeepSeek production-matched 探针：1/2 通过，整体 FAIL；原 operator path 不能真实 rerun。
- E2/E3：继续关闭。
- 新 operator E1：若改用 Qwen，属于新的 operator policy 与新的 8 jobs/16 candidate executions/8 API 调用预算；
  原批准与已消耗预算不能复用。旧 anchors 的 D_val 已在诊断中揭开，只能再作工程回归；任何 scientific
  effect-size 必须使用 outcome-blind 选定的 fresh anchors/tasks，并在新 run root、精确 commit 与新的 13 项
  预检下运行。

## 5. 归档与复现缺口

紧凑归档位于 `phase1/results/balanced_continuation_e1_real_20260814_e59a759d/`。只纳入 compact
collection、job rc、preflight/Slurm/safety receipts、零执行诊断与探针 summary；mode-0600 raw responses、
private labels、candidate workspaces 和凭据均未进入 Git。Qwen 与 DeepSeek 的 raw responses 也只留在远端
mode-0600 目录；Git 中仅保存 compact summaries 与 hash binding。

构建干净诊断 worktree 时发现既有 `fixed_decision_scorer` tar 的 LFS object 在 GitHub 缺失。该 tar 为
681687 bytes；内含 24 个 regular files，tar path unsafe hits=0、filename secret hits=0、content credential
hits=0。只补传既有 object 后，集群端按当前 commit fetch 并重算 SHA-256 为
`80a21f8d05d52fd602edd61c0e2538c3b18910ca92cefb24ca6040ad4937d379`。这不改变 corpus 发布协议：
未来 corpus 只上传不可变 batch，一次一个对象，由 release descriptor 与 `rebuild_corpus.sh` 重建 merged 版本。
