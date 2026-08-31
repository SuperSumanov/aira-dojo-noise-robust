# Archive disposition longitudinal replication：结果前冻结

## 目标

把 2026-08-25 的 archive-level mixed-disposition 结论做一次严格的时间外复制。历史锚点覆盖 218 个 source archives、
90 个 post-baseline settled decisions，且 6/6 个出现结构拒收的 competition 也至少有一次 accepted archive。
当前只锁定 outcome-blind observer metadata：275 个 archives 被摄取状态元数据分为 128 baseline、126 accepted、
21 rejected、0 pending；在冻结本协议前不读取当前 rejected competition 集合、mixed-disposition 分数或原因分布。

## GCCV 与 13 项预检

1. Goal：检验“结构有效性是 archive-level 而不是 task whitelist/blacklist 属性”能否在新增 57 个归档后复制。
2. Context：唯一方向为 Decision Corpus + Predictor Benchmark + Audit Protocol；LATEST 固定为
   `30945550b6b12a146dadd6eda733c3b676b467aef86636ae31ac59813133104f`。
3. Population：observer metadata 的不可变私有快照 SHA-256 固定为
   `dccd59d9e3fe964aabce2458647013d772070c40a120f79f9a6b02605356e855`，194,489 bytes；source 与 observer 均为
   275 archives。
4. Historical control：历史 ledger SHA-256 固定为
   `b194b1bc88e561e77f982ae6f46d5ea7cccb745cc960c26da2661ea0ce8bad03`，不得更换锚点。
5. Fairness：沿用历史 archive path → competition 解析和 accepted/rejected 定义，不改变 disposition 口径。
6. Integrity：四类 disposition 必须互斥完备、pending=0、latest 被 accepted 记录引用、post-baseline payload hash 无重复。
7. Reason gate：只接受三类既有结构原因；未知原因直接 integrity fail，不并入“其他”。
8. Strong gate：当前 rejected competitions 至少 6 个，新增 settled archives 至少 50 个，并且 mixed fraction 必须精确为
   1.0；该门继承历史 6/6，不在当前结果后放宽。
9. Partial/Kill：mixed fraction 在 `[0.8,1)` 仅为 partial；低于 0.8 为 kill。任何 integrity gate 失败优先于科学分类。
10. Statistics：报告 current 与 extension 拒收率及 Wilson 95% CI；不检验或主张拒收率平稳。
11. Independence：producer 与不 import producer 的 verifier 分别重建全部 aggregate，A/B 必须逐字节一致。
12. Security/resources：只读 observer metadata 与公开历史 ledger；不打开 tar payload、标签、分数、预测、候选身份；
    GPU/API/model-fit/base-update=`0/0/0/0`。
13. Promotion：focused/full tests、精确 commit、输入 hash、trace/security、只读门和 post-push fresh checkout 全过后，
    才允许把 strong/partial/kill 写入 `CURRENT_DIRECTION.md`。

## 结果前输入绑定修订（revision 2）

首次正式运行固定在 commit `d821a55c93ef5efd7877f57176bf916471bded4f`。它在 producer 启动前即因 live
`observations.json` 的整文件 SHA 漂移而 fail-closed：正式目录中没有 focused/full-test 输出、producer 输出、result 或
verifier 输出。诊断时文件仍为 194,489 bytes，LATEST 仍为 `30945550...104f`，source 仍为 275 archives，四类聚合仍为
128 baseline / 126 accepted / 21 rejected / 0 pending；未读取当前 competition 集合、mixed fraction 或 rejection reason 分布。

因此 revision 2 仅把输入改绑到随后立即生成的远端私有不可变副本
`dccd59d9e3fe964aabce2458647013d772070c40a120f79f9a6b02605356e855`。Strong/Partial/Kill 阈值、历史锚点、统计口径和
访问边界均未改变。旧 live-file 绑定 `3b078099...1f470` 保留在机器可审计失败目录和协议的 superseded 字段中，不删除失败证据。

## 结果前 competition mapping 修订（revision 2）

输入绑定修订后的第二次正式运行通过 focused `12/12` 与全量 `1844/1844` 测试，随后在 producer 的第一个 archive
path 解析处停止；没有生成 result 或 verifier 输出。原因是旧实现错误地把所有 observer path（包括 baseline legacy path）
都假设成 `4-digit-day/competition-Nseeds.tar.gz`。

在仍未计算 accepted/rejected competition 交集的前提下，结构扫描确认：全部 275 paths 均为安全两段 tar.gz；accepted
126 个中 124 个有 `-Nseeds` 文件名、2 个没有；rejected 21 个全部有 `-Nseeds` 文件名。进一步只读固定 snapshot 的
hash-bound intake metadata，确认 126/126 accepted archives 都恰好对应一个 task，124 个可解析文件名与 task 规范化后
0 mismatch，另外 2 个由 task metadata 补足；共核验 520 条 source-provenance rows。扫描没有输出 archive、competition、
run 或 candidate identity，也没有计算 mixed fraction 或 reason distribution。

520 条 provenance 分属两个兼容 schema：25 条含可选的 `competition_id_source`，495 条来自更早 schema、不含该字段；其余
12 个必需字段一致。因此正式门把该字段定义为唯一可选字段，并把 `25/520` 结构计数冻结，而不是按最新模板拒绝历史行。

revision 2 因而固定为：baseline 不赋 competition；accepted 使用 snapshot manifest → transaction → intake summary →
source-provenance 的逐 SHA 单 task；rejected 使用既有 `-Nseeds` filename stem；两侧都只做小写字母数字 slug 规范化。
Strong/Partial/Kill 门、历史锚点和结论边界继续不变。

## 结论边界

即使 strong gate 通过，也只支持“逐归档 fail-closed 验证不可被 task whitelist 替代”这一 benchmark-audit 主张。
它不证明 metadata 修复造成 recovery，不比较被接收与被拒收 run 的模型质量，也不提供 predictor accuracy、scaling、
search utility 或方法效果。
