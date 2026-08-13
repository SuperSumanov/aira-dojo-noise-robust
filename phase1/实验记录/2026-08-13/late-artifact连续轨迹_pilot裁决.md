# late-artifact 连续轨迹 pilot 裁决（2026-08-13）

## 1. 裁决

**SCHEMA-FIRST-CANDIDATE**。

在冻结选择的 6 cards / 6 tasks / 6 physical runs 上，同一进程从 30 秒连续观察到
30/60/120/240/360/480/600 秒，共得到 42 条 checkpoint records：

- stable copied artifacts：0；
- racy copies：0；
- finite pristine grades：0；
- 120 秒后首次变为 finite pristine grade 的 cards：0；
- grader-recovery-only cards：0；
- 到 600 秒仍没有 finite grade 的 cards：6。

预注册门规定：至少两个不同任务发生 late conversion 才保留 `TaskHazard`；0 个转向
`schema-first operator`；1 个或只发生 grader recovery 则为 `INCONCLUSIVE`。完整性门全部通过，
因此本次裁决按冻结规则为 **SCHEMA-FIRST-CANDIDATE**，关闭把“统一等待 120→600 秒”作为近期主要
方法投资的路线。

## 2. 作业与冻结完整性

- Slurm job：`10592`；节点 `gpu27`；状态 `COMPLETED 0:0`；elapsed `00:22:57`；
- 运行代码 commit：`108d3ed`；GPU：1×RTX3090；API 调用：0；
- manifest SHA256：`f535116e51dc7a03a65aa6df4b4621812367eea201f16aeb8d83d21bc398bbe1`；
- trajectory JSONL SHA256：`4b2134279d9da87c8b6f648ba7ea459a601460735ead1538467540be0ae9cd8e`；
- validation JSON SHA256：`d3f7d09c75dd279e0d4b236465f909149fb7d81c0207cd053a1b30c13e123089`；
- validation CSV SHA256：`fb67a83ee1b12c585fcb09c13e91c597a8acc3015f157c60c29dc22214cdcf9b`。

冻结 validator 给出 `SCHEMA-FIRST-CANDIDATE`。随后在新目录中重新复制原始记录并重新验证，生成的
validation JSON/CSV 与原文件逐字节一致，输出
`LATE_ARTIFACT_FRESH_REVALIDATION_PASS`。第一次 fresh replay 尝试使用 `cp -a`，因 `/tmp` 不允许保留
部分权限而在 validator 启动前失败；原始记录未被修改。改为普通递归复制且不保留权限后通过。

另有一份不 import 主 validator 的 raw verifier 从原始 JSONL 独立检查 checkpoint 网格、card 数、
artifact/grade 字段和最终进程状态，输出：

```text
LATE_ARTIFACT_RAW_INDEPENDENT_VERIFY_PASS cards=6 records=42 stable=0 finite=0 full_cap_alive=2 early_exit=4 final_rc={"-9": 2, "1": 4} decision=SCHEMA-FIRST-CANDIDATE
```

## 3. 必须保留的限制

本 pilot 不等价于“六个程序都有效运行了 600 秒”。只有 Google QUEST 与 tabular May 2022 两个候选
持续运行到 600 秒并由预算上限终止（`rc=-9`）；另外四个候选自然异常退出（`rc=1`）：Russian
normalization 约 5.005 秒、Chaii 约 7.759 秒、Essay 约 36.006 秒、MLSP birds 约 91.798 秒。因此：

- 允许说：在这份按冻结规则选择且保留真实早退行为的 pilot 中，统一延长等待没有产生任何可评分分数；
- 不允许说：昂贵 silent 候选总体的 120→600 秒 late-conversion rate 为 0；
- 不允许剔除这四个异常早退后重新解释原预注册 gate；它们是候选执行过程的真实结果；
- 只能把“两个存活到 600 秒仍无分数”作为极小样本的机制观察，不能独立估计总体概率。

三个早退与既有 fresh-120 replay 接近：Russian 约 5.0 vs 4.6 秒、Essay 约 36.0 vs 32.6 秒、Chaii
约 7.8 vs 8.4 秒，退出码均为 1 且输出字节数相同。MLSP 在旧 replay 中于 120 秒被终止，本次则在
约 91.8 秒自然以 `rc=1` 退出。该对照只用于排除明显的 watcher 新故障，不是效果分析。

## 4. 对下一步方法的约束

下一步不再把统一晚等或仅依赖 task-level hazard 作为主突破，而测试明确的 artifact contract：

1. `incumbent`：parent 或任务合法的共同 fallback，只保证任何时刻都有 schema-valid 输出；
2. `candidate_probe`：候选特异、低成本且带 provenance 的早期 probe；
3. `full_candidate`：候选完整训练后的产物。

共同 `sample_submission` 只能验证 schema/grader 通路，不能排序 siblings；selector 只允许使用
`candidate_probe` 或 `full_candidate` 的候选特异分数。没有候选特异证据时必须 abstain，不能把共同
fallback 分数伪装成候选质量。先做 contract smoke（schema/grader validity、首次候选特异 artifact 时间、
完整路径连续性），通过后才冻结固定预算 2×2：原 operator vs schema-first operator，stdout-only vs
pristine score channel。
