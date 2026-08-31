# Archive disposition longitudinal replication v1：完整性失败

状态：`ARCHIVE_DISPOSITION_REPLICATION_INTEGRITY_FAIL`。

v1 在 exact commit `5fb6a34250a60607165970989e7dd0d49b505e55` 通过 focused/full=
`12/1844 passed`（48 warnings），随后 producer 在写结果前因 `unknown rejection reason` fail-closed；没有 result，
独立 verifier 未启动，也没有计算 accepted/rejected competition 交集或 mixed-disposition fraction。

根因不是纵向复现结论为负，而是 v1 把所有 post-baseline rejected archive 都当成结构拒绝，并错误要求所有
post-baseline payload hash 唯一。当前 ledger 含 8 个早在 2026-08-26/27 单独预注册、逐字节验证并显式隔离的
`ARCHIVE_BYTES_DUPLICATE_COMMITTED_TRANSACTION` aliases；其 payload hash 按定义与 8 个 accepted transactions
重合。v1 既漏列该已知 reason，又设置与其语义冲突的唯一性门，故 v1 永久保留为完整性失败，不能通过补丁改写成成功。

在不计算 competition overlap 的前提下，taxonomy-only 诊断得到：accepted=`126`；目标结构拒绝=`13`，对应三个
历史 reason，hash 全唯一且与 accepted 重合=`0`；alias quarantine=`8`，hash 全唯一且与 accepted 重合=`8`，
registry hash 种类=`1`。这些计数只用于冻结一个新的 taxonomy-aware v2，不是科学 readout。

v2 必须把 aliases 当成完整性正对照而非 mixed-disposition estimand 的样本；原 v1 的三项判据（结构拒绝竞赛数、
总体 extension settled archive 数、结构 mixed fraction）不得放宽。机器记录见 `integrity_failure.json`；远端失败根
`/research/d7/spc/yzyang4/prospective-archive-disposition/formal-5fb6a34-v3` 保持原状。
