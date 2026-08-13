# Scoreable Prediction Tap 标签盲机制 Pilot 裁决

日期：2026-08-13
状态：**冻结裁决为 `INCONCLUSIVE`；不扩到 v11 的 176-pair discovery**

## 1. 实际执行与完整性

- frozen commit：`a4c9d19044c713ffcb89add2043c85bb0fc76183`；
- Slurm job：`10648`，`3×RTX3090`，6 cards × 3 arms = 18 executions；
- parent accounting：`COMPLETED 0:0`，wall=`00:45:53`，scheduler allocation=
  `2.2941666666666665 GPU·h`；
- manifest SHA-256：`5b74f725822b0290393de976020c02bfb456ac3164cc094a848637b53ef55a06`；
- 18/18 manifest、status、result 与代码/runtime/container provenance 完整；
- pilot 选择出的 6 cards、3 parents、3 runs 与三份 frozen v11 decision test 的 2,086 rows、
  2,028 endpoints、848 parents、92 runs 均为零交集，overlap 审计为 `PASS_ZERO_OVERLAP`。

冻结主验证器与一个不 import 主 verifier/worker、直接从 raw result 重算 K0--K5 的独立实现逐项一致。
主 summary SHA-256 为
`d2803973d4b35d8cbfde4d0963d0f3b44204dd80c68cb0bcfb0669a797bffda4`，cross-check
SHA-256 为 `1646ddafa12a518ba9a500a87f33dbcf8813c7d3694bea8793b889d36d87b130`。

## 2. 冻结门与结果

| gate | 结果 | 是否通过 |
|---|---:|---:|
| K0：完整 provenance | 18/18 executions | PASS |
| K1：baseline evaluable | 2/6 cards | FAIL |
| K2：120 秒内 finite valid probe | 2/6 cards | FAIL |
| K3：经验语义等价率 | 2/2，exact hash | PASS |
| K4：可比较 latency pairs | 2 | FAIL |
| K5：median relative feedback gain | 0.04135151374612629 | FAIL |

按 outcome 前固定的优先级，K1 首先失败，因此正式 verdict 是 **`INCONCLUSIVE`**。即使忽略 K1，
K2、K4 与 K5 也分别失败；不得换成 `PILOT_PASS`，也不得只报语义等价或唯一一个 sibling rank 成功。

## 3. 逐任务只读诊断

- `random-acts-of-pizza`：两张 card 的三个 arm 都在约 600 秒被预算终止；没有 submission 或 probe，
  stderr 为空。静态可插桩并不代表运行时 120 秒内能到达 prediction call。
- `petfinder-pawpularity-score`：两张 card 的三个 arm 也都在约 600 秒被终止；一张 tapped card 到
  `308.143884 s` 才产生 probe（score `18.00226`），另一张没有 probe。因此它不满足 120 秒门，
  且没有 baseline endpoint 可比较。
- `us-patent-phrase-to-phrase-matching`：两张 card 的三个 arm 均完成；probe 分别在
  `27.054646 s` 与 `64.344369 s`，baseline endpoint 中位时间分别为 `29.2687535 s` 与
  `64.8015795 s`。相对提前分别为 `0.07564748187858429` 与 `0.007055545613668293`，中位数只有
  `0.04135151374612629`。tap endpoint 与 originals 均 exact-hash 相同。

唯一可排序 group 为 1/1 正确，只能作描述。尤其第一张 patent card 的 probe score=`0.30524`，
final score=`0.60246`；第二张为 `0.60178` vs `0.60409`。这证明 raw prediction 可能发生在校准、
inverse transform 或后处理之前，`probe 可评分`不等于`probe 已忠实代表 final`。

## 4. 机制裁决

当前 SPT 只是 identity-wrap 已存在的 `.predict/.predict_proba/.decision_function` call。该 call 通常发生在
完整训练结束之后、写 `submission.csv` 之前，所以它最多省掉 prediction 后的序列化与后处理时间，不能把昂贵训练
本身变成早期反馈。pilot 的 4.14% 中位提前和两个 600 秒 silent 任务与这一结构限制一致。

因此：

1. **关闭 SPT identity tap 作为当前核心正方法**，不启动原草案的 176-pair GPU 扩展；
2. 保留 SPT 代码作为 semantics/provenance 测量工具和后续强基线；
3. 当前正方法回到已经过 2-task 工程门的 **Probe-First/Progressive Artifact Contract**：它必须主动在训练早期
   产生 cheap、candidate-specific、外部可评分 artifact，而不是等待现有 final prediction call；
4. 该路线必须和 ArchPilot-style 1 epoch/10% rewrite、最强 pre-execution critic/FOREAGENT、full execution
   在相同总成本下比较，并把 probe-to-full fidelity、失败率、full quality 与 observability/ranking regret
   分开报告；
5. 若 contract 只能靠 task-specific patch，或 fixed-budget search utility 不优于 ArchPilot，则方法线关闭，
   只保留 Anytime Feedback Frontier 的 D&B benchmark 贡献。

## 5. 产物

精简可复核产物位于 `phase1/spt_pilot_v1/`；18 个 raw result 仍保存在远端冻结 ops 目录，未把大型 checkpoint
快照重复提交到 Git。`verify_spt_pilot_raw.py` 是独立 raw verifier；`diagnose_spt_pilot.py` 只做 outcome 后
失败机制分类，不改变任何冻结 gate。
