# TraceML 外部结构资格审计 v1：裁决

日期：2026-08-21。正式 source commit：
`517c95c87edceb9d5841696982a34638db9d2fe2`。固定 TraceML revision：
`61faec615b179f186dbe9c82ee59d17e14817e96`。最终裁决：
`IDENTITY_OR_JOIN_AMBIGUOUS`，外部冻结 scorer **不允许运行**。

## 1. 预注册与完整性

本轮严格执行同日预注册：先由官方 dataset card/importer 与 schema 固定
`<physical_run>__branch<N>`、`orig_version_number` 和 action→state join，再读结构支持量；不把 189 条
root-to-leaf paths 当 189 个 runs，也不把跨层路径邻接当 direct edge。输入 SHA 与官方固定 revision 一致。

生产器和不 import 生产器的验证器各运行两次，JSON 分别逐字节相同。独立验证器改用 `rsplit` 解析 key、DFS
查环并独立重建全部聚合；所有复核项通过。聚焦测试 `12 passed`，覆盖正常 direct tree、skipped-depth、重复
action、跨 branch 元数据冲突、凭据形状拒绝和实现独立性。四个正式进程均 rc=0，单次约 1.31--1.40 秒，
最大 RSS 约 181--182 MiB。结果文件 credential-shape matches=0；GPU=0、API=0、base-LLM update=0。

## 2. 固定公开表能证明的结构

- MLEvolve state/action rows：1,026 / 837；
- branch keys：189/189 匹配，恰恢复 13 个 physical-run prefixes、7 个 tasks；
- 每 run branches：min=3、median=6、max=80；
- state/action identity 重复：0/0；endpoint join failure=0；元数据冲突=0；图无环、child 多 parent=0；
- 643 个去重 original nodes，`raw_code_path` 非空覆盖 0/643；
- 837 条 joined path-edge rows 去重后是 583 条 adjacency edges，其中 254 条是 branch-path 重复。

唯一决定性失败是 depth：`+1`=537、`+2`=178、`+3`=99、`+4`=22、`+5`=1，共 **300** 条跨层
adjacency。预注册要求所有 edge 精确 `+1`，故公开线性 branch 表无法唯一恢复 direct parent-child 图；
`canonical_direct_sibling_pairs=null`，不得读取 score 再反向挑映射。

## 3. 为什么 167 不能作为 external cohort

若违规把所有 path adjacency 当 direct edge，会得到 67 个 provisional parents、174 children、167 pairs。
该数字只作失败诊断，不是合法 sibling 数：

- 只覆盖 3 个有 pair 的 tasks，低于固定门 4；
- `google-quest-challenge` 占 117/167=`0.7005988023952096`，高于固定上限 0.50；
- scorer 所需 raw code join 为 0/643；
- 因 S0 已失败，finite non-tie score 支持与我方代码 overlap 均按协议不读、不算。

所以即使无视 300 条跨层边，它仍会独立触发 task-support、balance 和 code-coverage 三个停止门。此次没有
accuracy、CI、scaling 或方法效果结论。

## 4. 对论文主张的影响

这是一个窄但可守的正向资产：在固定公开 TraceML paired tables 上，不能按预注册且可复核的方式实例化我方
**physical-run-clean direct same-parent sibling decision** 协议；我方当前 249 runs / 1,665 canonical pairs /
26 tasks 的结构资源因此不是被其公开表直接替代。

边界必须写清：这不证明 gated `MLE-Traj-v1` 原始树里没有可恢复 sibling，也不允许恢复“首个 MLE
trajectory/per-node/tree dataset”等已关闭宽主张。若以后正常获得 gated raw tree/code，只能以本次固定门继续
S0/S1，不得降低阈值或用 paths 冒充 runs。

完整聚合证据位于
`phase1/results/traceml_external_structure_eligibility_20260821_517c95c/`；原始 parquet 不进 Git，归档
`full_artifacts.tar.gz` SHA-256=
`4cc0ecc7caabe6bc6377fc7f2b7fff9953a38e0e844eae7b3c62b48b382d98b0`。
