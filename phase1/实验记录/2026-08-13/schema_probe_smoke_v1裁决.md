# Schema/probe-first contract smoke V1 裁决

日期：2026-08-13
状态：**FAIL（冻结裁决；不得回填、替换任务或重跑同一候选）**

## 1. 实验角色与预注册门槛

本实验只验证自由形态 MLE 候选能否遵守以下 anytime artifact contract，不验证搜索收益或最终质量：

1. 同一候选进程先原子写入候选特异的 `candidate_probe.csv`，再继续完整训练；
2. host watcher 独立记录首次稳定文件、哈希和单调时间；
3. pristine grader 只在候选退出后运行，候选看不到隐藏标签或 grader；
4. probe 写入后不可修改，full submission 只能作为后续独立 transition；
5. 共同 `sample_submission` 不得冒充候选信号。

冻结矩阵为两个预先选定任务、seed 861、每任务一次生成。MCTS 预算是 root + 一个 draft（`step_limit=2`、一个 code node），不允许 debug/improve。门槛为：

- `PASS`：两个任务都在 host 120 秒内产生合法、候选特异、可评分且不可变的 probe，并且至少一个任务在 600 秒内完成合法 full transition；
- `PARTIAL`：两个 probe 都通过，但没有合法 full transition；
- `FAIL`：任一 probe 的有效性、provenance、候选特异性、不可变性或 120 秒时限失败。

## 2. 完整性与恢复说明

- 生成 job `10623` 的两个 scientific `srun` 均为 `COMPLETED/0:0`；父 job 最终为 `FAILED/1:0`，原因是生成后的本地审计仍按旧的 root-only 拓扑计数，而不是候选生成失败。
- 修复审计器后只从原始 journal/search export 提取候选；没有重调 LLM、修改候选代码、替换任务或补跑生成。
- 生成 manifest SHA256：`c66630737f5a056b068502fa5d3fa234f707dc6ded53206b9a7304e61de0006d`。
- replay manifest SHA256：`46446dd330baea1bdd00de38a0f4ba6d6becc889ed11b7b6cffd2f6080ba0636`。
- replay array job `10625` 两个元素均 `COMPLETED/0:0`；原始 validator 与恢复前冻结的门槛一致。
- 恢复前重新运行单测、代码/hash/task 拓扑、容器镜像、只读 public data、资源与 secret 检查；没有读取论文冻结 test 作为训练信号。

## 3. 逐任务结果

| 任务 | 候选退出 | host 首次 probe | probe 分数 | host full | full 分数 | 裁决 |
|---|---:|---:|---:|---:|---:|---|
| `spooky-author-identification` | rc=1，5.124624 s | 无 | 无 | 无 | 无 | probe fail |
| `tabular-playground-series-may-2022` | rc=0，403.838195 s | 15.762469 s | 0.94006 | 403.356871 s | 0.96684 | probe/full pass |

表格任务的 probe 与 sample submission 行数、表头一致，但 100,000/100,000 个预测行不同且预测非常数；probe 在 30/60/120/240/360 秒 checkpoints 中哈希不变。程序自报 probe/full marker 分别为 10.2/397.8 秒；headline 采用 host 捕获时间，避免信任候选自报时钟。

文本任务在写出任何 submission 或 marker 前退出。冻结 stderr 的根因是当前容器中的 sklearn 不接受候选使用的 `LogisticRegression(..., multi_class="multinomial")`。这属于真实的通用 runtime/API 失败，必须计入失败分母，不能事后删参数并回放来把 V1 改成成功。

## 4. 正式裁决

`probe_pass_count=1/2`，`full_transition_count=1/2`，因此按预注册规则为 **FAIL**。

V1 只支持以下有限结论：schema/probe 合约在一个真实表格任务上能够由单次 LLM draft 实现，并通过 host provenance、候选特异性、不可变性和 pristine grading 的全部检查。它不支持“prompt-only schema 在任务间稳定可行”，更不支持 coverage、质量或搜索收益提升。

## 5. 后续唯一允许的修复门

按照 outcome 前冻结的停止规则，只允许一次相互独立的 V2：使用新任务、新 seed 和固定的 conditional-debug operator；draft 无效时最多 debug 一步，首次 externally valid 候选出现即停止。V2 不修补或重放 V1 候选，且原始/schema 两臂未来必须获得同样的条件 debug 预算。

- 若 V2 通过同一双任务 probe/full 门，才设计独立因果 A/B；
- 若 V2 再失败，关闭 prompt-only schema 路线，只考虑 runtime-owned probe API，不继续改 prompt。
