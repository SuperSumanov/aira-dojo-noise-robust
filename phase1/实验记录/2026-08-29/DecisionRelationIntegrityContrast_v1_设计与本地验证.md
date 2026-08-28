# Decision Relation Integrity Contrast v1：设计与本地验证

## 定位

这是当前 `Decision Corpus + Predictor Benchmark + Audit Protocol` 主线内的历史聚合压力测试，不是新的 predictor
effect 实验，也不是预注册确认。三个输入结果在本规范固定前都已经知道；本轮价值在于把分散的已发布证书组成一个可机器
复验的诊断链，并测试审计栈是否在两个历史资源家族上退化成 constant-accept 或 constant-reject。

允许的主张被固定为：已发布的聚合审计栈接受 canonical v11 的 hard-integrity certificate，拒绝 relation-mixed 0819
certificate；预先固定的 direct-sibling quarantine 随后得到一个 train/test referenced-run overlap 为零、并通过其独立
repair 协议全部 hard/support gates 的 core。

不得称为一般审计方法首创、因果资源质量差异、calibrated sensitivity/specificity、predictor scaling/effect、search utility、
prospective confirmation 或 row-level release。

## 精确输入

规范 `phase1/historical_relation_integrity_contrast_v1.json` 绑定三个不可变发布包及其完整 manifest、producer summary、
independent verifier：

1. canonical v11 lineage audit v2；
2. senior 0819 relation taxonomy；
3. senior 0819 deterministic direct-sibling quarantine。

producer 和 verifier 都必须完整复核 package membership，不只抽查 summary。repair 必须逐哈希回指 taxonomy certificate，且
两者 input hashes 与 source commit 必须相同。

## 可比性限制

- 三个证书的 frozen gate schemas 相关但不相同；13/15、15/15 与 16/16 不是共同标尺上的通过率，不能直接作统计比较。
- canonical 的 `lineage-direct` 包含 parent Card 缺失但 endpoint lineage 可证的 orphan-parent tier；parent-present strict core
  retention 另行报告。
- 这是两个历史资源家族的 deterministic case study，不是资源总体的 sensitivity/specificity 估计。
- support gate 只按各自原证书解释；canonical `frozen:b2.maximum_single_run_pair_share` 的失败必须保留。

## 本地实现与攻击测试

- producer：`phase1/build_historical_relation_integrity_contrast.py`；
- 独立 verifier：`phase1/verify_historical_relation_integrity_contrast.py`，不导入 producer；
- 测试：`phase1/tests/test_historical_relation_integrity_contrast.py`。

本地 smoke 已完成：新测试 9/9，通过 package hash/membership 漂移、semantic count drift、repair non-exhaustiveness、candidate
隐藏 support failure、known-result 边界等攻击；四组相邻审计测试共 34/34。producer/verifier A/B 各自逐字节一致。
本机全量测试在 collection 阶段因环境没有 `scipy` / `sklearn` 而停止；这不是测试失败，也不得写成全量通过。正式集群
环境必须重新执行全部 `phase1/tests`，通过前不发布 readout。

正式 readout 仍须在 exact source commit 的 fresh detached cluster worktree 上完成 13 项 preflight、全量 `phase1/tests`、
三包 manifest、A/B、独立 verifier、forbidden-open/network trace 与 credential scan；任何一项失败均不发布结果。
