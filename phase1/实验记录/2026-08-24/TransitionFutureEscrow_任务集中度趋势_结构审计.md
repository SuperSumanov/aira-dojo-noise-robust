# Transition Future Escrow：任务集中度趋势结构审计

日期：2026-08-24
状态：`STRUCTURE_ONLY_DOMINANT_TASK_CONCENTRATION_IMPROVED_GATE_STILL_FAIL`

## 1. 问题与边界

0FH 已确认 transition future escrow 从旧快照 `79701f...` 前滚到 `f109ac...` 后，eligible tasks 从 11 增至
16，但预注册的 dominant eligible-pair task share≤0.25 仍失败。本审计只回答两个结构问题：

1. 当前失败离阈值有多远；
2. 0822 新增支持使任务集中度改善还是恶化。

这是看到两个 snapshot 后补做的**结果后描述性诊断**，不是预注册效果检验。输入只含已托管的 pair identity、task、
run 与 `strict_effect_eligible`；不读取 pair 胜负、grade、label、accuracy、prediction margin、CI 或 search utility，
也不改变 cohort、阈值或自然生产策略。

## 2. 固定输入与实现

旧输入：

- artifact：`7458f09-append/20260822T212930Z_79701f90db16/artifact`；
- pairs SHA-256=`184cdadfdd2966274a44f72bc1b78a4dc259c6353a5d7e5ce9f97daf71544710`；
- summary SHA-256=`55c295c511ef79e786eb8d33834c1d2fdda1254fff9a3d0174e417fac07c77b4`。

新输入：

- artifact：`7458f09-append/20260824T111032Z_f109ac928ed0/artifact`；
- pairs SHA-256=`498a8aebf79027e96294e6c22fdce87e4007cdaeacfbb969198f55627b9db3fe`；
- summary SHA-256=`da62681ed53835de40a9a3dda583e589e05aef7c5bd1d602cc556b78c851d5cf`。

主实现为 `phase1/audit_transition_task_balance.py`，其 SHA-256=
`8b88b08e6ac957671ab45556e911bde94214908d177df53ed1e3a25b02eb9e9e`，与远端正式运行的 source bytes 相同。
它要求 pair/summary 精确 SHA、固定完整 schema、summary inventory 绑定，并只计
`strict_effect_eligible == true`。独立实现用 `jq-1.7` 投影 task，再以 `LC_ALL=C sort | uniq -c` 生成规范 TSV；
旧、新两份 TSV 均与主实现逐字节一致。

审计前写入 13 项 preflight，明确：单 CPU、GPU/API/model fit/base-LLM update=`0/0/0/0`；任何输入、schema、
计数、实现、trace 或 credential 门失败即关闭；条件缺口只能解释为算术，不能解释为生产预测。

## 3. 精确结果

| 结构量 | 旧 `79701f...` | 新 `f109ac...` | 变化 |
|---|---:|---:|---:|
| eligible pairs | 222 | 363 | +141 |
| eligible runs | 28 | 45 | +17 |
| eligible tasks | 11 | 16 | +5 |
| dominant task | tensorflow speech | tensorflow speech | 不变 |
| dominant count | 107 | 107 | **+0** |
| dominant share | 0.481981981981982 | 0.29476584022038566 | -0.18721614176159632 |
| dominant≤0.25 | FAIL | FAIL | 改善但未过门 |
| 若 dominant count 固定，所需非主导新增对 | 206 | 65 | -141 |

share 下降的精确分数为 `5029/26862`。最关键的结构事实是：新增 141 个 eligible pairs 全部来自旧主导任务之外，
因此分母增长并非该任务的更多重复。新快照 16 个任务的规范计数 SHA-256=
`5ce9def66779aa23472d10c31d4096ab3f8270b6c4486a44469f99105e56cbfe`；旧快照对应 SHA-256=
`3eb6bec6eef0d05537e9dbb95014b0c708612a5db52e0ae9d966071a252fd030`。

条件缺口来自最小整数解：`107 / (363 + x) <= 0.25`，所以 `x>=65`。如果后续主导任务也增加，实际所需新增量会
相应变大；因此 65 既不是 ETA，也不是停止规则。当前更远的 1,500 eligible-pair 与 150-run 门保持原样。

## 4. 完整性与失败记录

第一次单点 wrapper 的科学计数已完成，但旧凭据扫描正则没有前导边界，把 `protocol` 字段普通字符串中的
`sk-...` 子串识别成疑似 key：

- 只命中 `python.stdout` 与其同内容 `python_a/summary.json`；
- redacted classifier 只输出 `json_path=$.protocol`、类别、长度、匹配 SHA 与 `preceding_class=ALNUM`，没有打印
  匹配文本；
- 宽规则命中文件=2，边界感知高置信命中文件=0；
- wrapper 在 credential gate 处停止，没有写 `COMPLETE`；
- failed root 已写显式 failure receipt、manifest 后递归只读，manifest 文件 SHA-256=
  `8111c535286907cae7a3562290a9284adf6aa77cca1a12b3c51f961c896f480c`。

修复只给凭据模式增加 token 前导边界，没有改输入、计数器、threshold 或 estimand。全新 v2 从头运行：

- root：`/research/d7/spc/yzyang4/transition-task-balance-audit/17f0b27-f109-v2`；
- producer×独立 `jq` 计数逐字节一致；
- forbidden open / high-confidence credential files=`0/0`；
- outcome/effect metrics=`false/[]`；
- 递归 writable files=0；
- 独立 `sha256sum -c` 与字段重算通过；
- `SHA256SUMS` 文件 SHA-256=`28fb4ab286fb24cd6f9bad743345a41ade7f50044f90a989fa7169b6d462ba78`。

旧→新趋势也从两个固定输入重新独立运行并封存：

- root：`/research/d7/spc/yzyang4/transition-task-balance-trend/17f0b27-797-f109-v1`；
- 两个 snapshot 的 producer×`jq` 均逐字节一致；
- forbidden/credential=`0/0`，outcome/effect=`false/[]`，GPU/API=`0/0`；
- 递归 writable files=0；
- 独立 manifest 与字段重算通过；
- `SHA256SUMS` 文件 SHA-256=`e75c855094a89f4ff801389f41750341110725c223a5cb1a4ca312c16bb8e57d`。

提交验证也保留完整失败链。第一次 pre-push wrapper 没有限制 BLAS 线程，在登录节点出现约 30 核过度并行；聚焦测试已
完成，但全量测试只到 22%，因此人工终止并明确标为 `INVALID_TEST_HARNESS_BLAS_THREADS_UNBOUNDED`。该次没有运行
科学分析、没有读取 outcome，也没有写 `COMPLETE`；失败 root 封存后的 `SHA256SUMS` 文件 SHA-256=
`42469fb4b997f50cf519985213c53553d5460f91f4edad0007b8536ca1409909`。全新 v2 使用 `env -i` 与
`OMP/OPENBLAS/MKL/NUMEXPR=1` 从头运行，聚焦=`9 passed`、全量=`963 passed, 47 warnings`，两份正式结构产物的
独立复核与 commit 文件名/内容凭据扫描也全部通过；其 `SHA256SUMS` 文件 SHA-256=
`8b3c28c08bf4b1a3737aa56655324bce36b27dad0de9eebc3f488d97518dbed7`。推送后从 GitHub fresh no-smudge
拉回 commit `92c2ad28ce3d244e520d55074de3908bfa351860`，聚焦 9/9 再次通过、源码 SHA 与正式 producer 字节一致，
post-push `SHA256SUMS` 文件 SHA-256=`af608525e4278ea7a9099bf111bfb881e21d1f0f0bb31af8fcf7ab7b7910b0fd`。

## 5. 科学裁决

可以新增的正面主张只有：**在固定自然时间外 population 中，0822 新增结构支持扩大了任务广度，并把旧主导任务
占比从 48.20% 降到 29.48%；新增 141 个合格对中旧主导任务为 0 个。** 这说明 dominant gate 正在朝正确方向移动，
而不是被单一任务增长永久锁死。

不能新增的主张包括：门已通过、再来 65 对必过、critic 有效、transition features 优于 child-only、已有 search gain，
或应定向改变 producer 的任务分布。正式状态仍为 `TRANSITION_ESCROW_INSUFFICIENT_FUTURE_SUPPORT`；合法下一步仍是
outcome-blind 自然摄取与 append-only prediction escrow，所有冻结支持门同时通过后才允许按既有协议一次性揭盲。
