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
3. Population：observer metadata SHA-256 固定为
   `3b0780991fd55fde5d49f1dbd56ff28a27513cf3d71a74954d00e8367df5f470`，194,489 bytes；source 与 observer 均为
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

## 结论边界

即使 strong gate 通过，也只支持“逐归档 fail-closed 验证不可被 task whitelist 替代”这一 benchmark-audit 主张。
它不证明 metadata 修复造成 recovery，不比较被接收与被拒收 run 的模型质量，也不提供 predictor accuracy、scaling、
search utility 或方法效果。
