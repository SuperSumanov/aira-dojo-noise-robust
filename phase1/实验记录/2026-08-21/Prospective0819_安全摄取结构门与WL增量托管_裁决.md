# Prospective 0819：安全摄取、结构门与 WL 增量托管裁决

日期：2026-08-21。状态：结构与预测托管完成；outcome vault 未开，效果结论未产生。

## 1. 八包闭合与 Plant 结构性拒收

冻结 manifest 的 8 个归档最终为 7 committed、1 rejected、0 pending。Plant 包首次 intake 以
`journal must identify exactly one competition` fail-closed 后，没有从文件名猜 task、没有部分 salvage，也没有
读取 senior archive 中的 env 或 live-event journal。绑定精确 archive SHA 的 credential-first 双审计显示：4 个
checkpoint journals 全部 `task_identity_cardinality=0`，共 4 个 invalid journals；审计未输出 task identity 值、
代码、stdout、grade 或 metric。由此生成的单条 rejection registry SHA256=
`0dc58a4f2b2770f615b4ebf6d077c25ec7866d0f0ad72a2cc2f312d8d4f1d503`，八包再做全源 SHA 检查后闭合。

## 2. 最终结构资产

最终 snapshot=`83ab1d681ed863d2374a6648df4801e6dbd6fb80d89f4f20cec8d46de1d5c047`。不依赖 accumulator
内部统计的结构 verifier 连续两次逐字节一致，得到：

- 49 transactions、249 eligible physical runs、6,471 endpoints、1,665 canonical sibling pairs、26 tasks；
- 248 finite-decision runs，run pair coverage=`0.9959839357429718`；1,623 decision parent groups，
  每个 decision run 的 pair 数中位数为 5.0；
- dominant pair task=278/1,665=`0.16696696696696697`，effective pair tasks=
  `12.25688288375918`；
- 6,458/6,471 exact-code unique，fraction=`0.9979910369340133`；9 个 duplicate groups、13 个
  beyond-first endpoints，cross-run 与 cross-task duplicate groups 均为 0；
- 0819 增量为 26 runs / 828 endpoints / 192 pairs / 7 tasks，26/26 runs 有 finite decision。

1,500 pairs、150 finite-decision runs、15 tasks 与 dominant≤0.25 四项结构支持门已经通过；但 first-960 尚差
711 runs，accrual closure=false，`vault_open_allowed=false`。因此不能提前读取预测效果。

## 3. WL 四臂 append-only 托管

固定 scorer commit=`031edb34400781ca026bc9833ac7f850312ffb1c`、四臂、bundle、protocol 与 activation
receipt 均未变化。producer 在 `11:22.61` 内完成 6,471 endpoints / 1,665 pairs；不 import producer 的 verifier
在 `10:51.10` 内独立重建。四臂逐 endpoint 最大绝对分数差均为 0.0，两个进程退出码均为 0。图解析为
6,274 AST、192 token-sequence fallback、5 raw-line fallback；159 endpoints 触发固定 8,192-node cap，四臂
pair ties 均为 0。

append verifier 两次输出逐字节相同，并证明旧 snapshot 的 5,643 endpoints / 223 runs / 1,473 pairs 每行
逐字段不变；新增量精确为 828 endpoints / 26 runs / 192 pairs。两份 syscall trace 共 18,094 行，所有 outcome、
label、scorer 与历史 frozen 路径的命中为 0；9 个目标文件共扫描 7,484,849 bytes，credential-shape matches=0。
GPU=0、API=0、base-LLM update=0，`effect_metrics_computed=[]`。

## 4. 必须显式保留的时间勘误

预注册文档最初称 0819 为“activation 后首批候选 physical runs”。这在“完成投递/摄取”意义上成立，但在固定
effect stratum 使用的 **生成开始时间** 意义上不成立。activation 是
`2026-08-20T05:20:27.656860Z`；独立 producer/verifier 均将累计 249 runs / 1,665 pairs 分类为
`outcome_unread_support_only`，strict post-activation runs/endpoints/pairs/tasks 全部为 0。

裁决是不改规则：不以上传时间替代生成时间，不移动 activation，不把等时刻算入，也不把支持集用于 accuracy、
CI 或 search utility。这次完成的是可审计的结构增长与冻结预测资产，不是 WL 方法正结果。真正效果样本必须来自
activation 后开始生成的全新 runs，并继续等 first-960 + accrual closure 后才开 vault。

## 5. 同期防 scoop 裁决

TraceML/MLE-Traj-v1 已关闭“首个 MLE trajectory/per-node score/tree dataset”等宽 novelty。当前可守贡献必须
限定为真实 search-time same-parent sibling decision、physical-run clean、failure/source missing、gap/regrade、
endpoint reuse、query/init/execution cost，以及 outcome-blind temporal escrow。外部 TraceML replication 只有在
正常获得 gated raw code、按 physical run 去重且通过预固定支持/零重叠门后才允许一次性运行冻结 scorer。
