# FOREAGENT UST outcome sensitivity：v2 身份失败与 v3 任务命名空间修正

时间：2026-08-30

## 裁决

v2 是第二个**无结果工程失败根**。它证明线程修正有效并通过全部测试，但 producer 错把官方 task-relative
solution path 当成全局 endpoint ID。v3 把 endpoint identity 明确定义为 `(task, solution_path)`，并同时修改
producer、独立 verifier、测试与 formal hash binding；科学 estimand 与支持集不变。

## v2 正式证据

- exact commit：`293576b1cab6f46a7ffab0ad0df768325701d390`
- formal root：`/research/d7/spc/yzyang4/foreagent-ust-outcome-sensitivity/formal-293576b-v2`
- focused：`11 passed in 0.51s`
- full：`1771 passed, 48 warnings in 107.36s`
- producer A：`ValueError: endpoint crosses tasks`
- `FAILED_RC=1`
- `COMPLETE`：不存在
- `result_a/b.json`、`verification_a/b.json`：全部不存在

producer 在错误前读取了协议允许的历史公开 scores/predictions，并可能在内存中构造了部分早序 task graph；但没有完整
common graph、没有写出 result、没有形成或读取任何新的 UST outcome aggregate。所有 partial in-memory work 均明确作废。

证据 SHA-256：

```text
d207fc0cdc13b51ab9b633a3b1ec2b34248f1a1c3e1e6d7cf70dfdc35f5f569f  FAILED_TASK_SCOPED_ENDPOINT_IDENTITY.txt
4be62ecc52aba271019df5c005124ada58723cf583c0548b3299289679824f32  task_scoped_endpoint_structural_audit.json
632faea756e575985b89728307d38c063e0e182c13b97f4dcf590ecf0c50633f  producer_a.stderr
c9001cbd1f2385a6f2487a9053e2f0e1275e3be444568cb86f3d19ad765d64dd  full_tests.txt
```

## 只读路径结构审计

诊断脚本只允许读取 `source_index` 和 `solution_paths`，并绑定原 manifest/master SHA；scores、predictions、confidence
均未读，task/path identity 均未输出。结果为：

| 字段 | 数值 |
|---|---:|
| tasks | 26 |
| cross-model common grid pairs（finite filter 前） | 18,430 |
| task-scoped endpoint memberships | 895 |
| raw unique path strings | 885 |
| 跨 task 复用的 raw strings | 9 |
| 上述 strings 覆盖的 task-path memberships | 19 |

等式 `895 - 885 = 10` 正好来自跨任务复用造成的 namespace collapse；论文报告的 895 solutions 也与 task-scoped
计数一致。因此 `path` 本身不是跨任务全局主键。

## v3 修正边界

允许：

- 同一个 raw path 字符串在不同 task namespace 中分别表示不同 endpoint；
- 每个 task 独立构图，再把结构总量与 metric numerators/denominators按冻结公式汇总。

继续禁止：

- 同一 source/task 内重复 unordered pair；
- release 或 model 间 task drift、truth/score drift；
- 把两个 task 的 vertices 放进同一个 graph；
- 输出 raw task/path identities；
- 任何 result-dependent threshold、model selection 或重写 prior `INSUFFICIENT-SUPPORT`。

## 独立实现与控制

- producer：task loop 内独立 UnionFind；
- verifier：task loop 内独立 adjacency/DFS；
- 新控制：两个 task 故意复用完全相同的 raw pair，两个实现都必须报告 `4 vertices / 2 components / rank 2`，
  且两条 edge weight 均约等于 1；
- focused：`12 passed in 0.30s`；
- identity addendum SHA-256：`e2d8f6a5de13698c0940c0e19ae4d4650eeeff7f09c338a7c0dc8c68df6f3684`。

## 下一步

公开 v3 exact source 后，以 fresh detached worktree 和 fresh output root 第三次执行全部 13 项 pre-flight、focused/full、
producer A/B、independent verifier A/B、trace/security/manifest/mode/read-only 门。v1/v2 根永不复用。
