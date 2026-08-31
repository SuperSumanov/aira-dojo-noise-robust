# Archive Disposition Longitudinal Replication v2：taxonomy-aware 结果前冻结

时间：2026-08-31。冻结时尚未计算当前 accepted 与目标结构拒绝的 competition 交集，也未得到 mixed-disposition
fraction。v1 已在 producer 写结果前以 `unknown rejection reason` fail-closed；该失败永久保留，不得改写成 v1 成功。

## 为什么需要 v2

v1 漏掉了早在 2026-08-26/27 已单独预注册并验证的 byte-alias quarantine reason，同时要求所有 post-baseline
payload hash 互异。8 个 aliases 按定义与 8 个 accepted transactions 逐字节相同，因此两个门相互矛盾。

在不读取 competition overlap 的 taxonomy-only 诊断中，当前 21 个 rejected archives 被完整分为：

- 13 个目标结构拒绝：三个历史 reason，hash 全唯一，与 accepted hash 重合为 0；
- 8 个 byte-alias quarantine：固定 reason，hash 全唯一，8/8 与 accepted hash 重合，registry hash 种类为 1。

v2 只修正这一分类错误：aliases 是生产完整性正对照，不能进入结构 mixed-disposition estimand，也不能增加结构拒绝
competition 数。它们仍属于已完成 disposition，故保留 v1 原先的“总体 extension settled archives”增长门。

## 固定问题与判据

问题：从 218 个 observed archives 的历史 anchor 增长到当前 275 个后，历史的“结构拒绝不是任务黑名单；同一竞赛也有
accepted archive”是否复现？

只有同时满足以下三项才是强复现：

1. 当前目标结构拒绝涉及至少 6 个 competition；
2. 相对历史 anchor 的总体 settled archive 增量至少 50；
3. 当前目标结构拒绝 competition 的 accepted-overlap fraction 恰为 1.0。

若第 3 项至少 0.8 但强门未全过，只能记 partial；否则 kill。阈值与 v1 一致，没有因为当前 taxonomy 诊断放宽。

## 必报分层

- historical：78 accepted / 12 structural rejected / 90 settled；
- current overall：126 accepted / 21 rejected / 147 settled；
- current target：126 accepted / 13 structural rejected / 139 target-settled；
- current quarantine：8 aliases；
- extension：accepted +48、structural rejected +1、alias +8、target-settled +49、overall-settled +57；
- overall、structural、alias 与 extension 比率均给 Wilson 95% interval；
- mixed-disposition 只用结构拒绝 competition，绝不纳入 aliases。

## 13 项 pre-flight

1. **问题**：结构拒绝的 archive-level mixed-disposition 现象能否纵向复现？PASS。
2. **estimand**：目标结构拒绝 competition 中同时有 accepted archive 的比例；alias 不入 estimand。PASS。
3. **输入**：冻结 observations、hash-bound snapshot/transactions/intake provenance、历史 ledger、既有 alias receipt。PASS。
4. **泄漏**：不读 archive payload、label/outcome/prediction/accuracy/utility；不输出 identity。PASS。
5. **对照**：alias 8/8 overlap accepted 是 taxonomy 完整性正对照；structural overlap accepted 必须为 0。PASS。
6. **样本量**：穷举 275 个冻结 archive；结构 competition 至少 6、总体 extension 至少 50。PASS。
7. **随机性**：无随机性。PASS。
8. **推断**：比例报 Wilson 95% interval；不做 stationarity 或因果主张。PASS。
9. **成本**：CPU metadata-only，预计 3 分钟；GPU/API/model-fit/base-update=`0/0/0/0`。PASS。
10. **恢复**：fresh root、write-new；失败根不复用。PASS。
11. **环境**：exact clean commit，focused/full suite 后才运行。PASS。
12. **安全**：trace/security、只读门、credential scan；private trace 不公开 identity。PASS。
13. **晋升**：producer A/B、独立 verifier A/B、哈希与 postflight 全过才可写正式结论。PASS。

## 允许与禁止的解释

若强门通过，只能说：在扩大后的 outcome-blind archive population 中，结构拒绝仍表现为 archive-level validity gate，
而非 task whitelist/blacklist；生产账本还能把 byte aliases 与结构无效 archive 明确分层。

不得说 predictor accuracy 提高、模型 scaling 得到确认、search utility 改善、metadata 修复有因果效果、拒绝率稳定，或
任何 task 应被排除。该结果是正面的 benchmark-audit / corpus-validity 资产，不是 critic 方法效果。
