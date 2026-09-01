# Archive rejection support census（14-event complete census）

## 结论

在冻结的 283-archive observer census 中，共有 14 个结构拒绝事件。按结果前固定的四级规则：

- 13/14（92.857143%）在 prior anchor `30945550...104f` 时已同时拥有 accepted archive、eligible run 和 eligible endpoint；
- 0/14 只在后续 7-transaction window 才获得 eligible support；
- 0/14 只有 accepted archive、但没有 eligible run/endpoint；
- 1/14 直到 current anchor 仍完全没有 accepted archive support。

按匿名 competition 去重后是 6/7（85.714286%）prior support、1/7 no support。唯一 no-support competition
就是此前单事件审计已经披露的最新事件；因此此前未知的第 13 个事件属于 prior support。reason 分层、完整整数聚合和
event-weighted 支持量见 [result.json](result.json)。

最稳妥的正向解释是：在这个固定 census 中，结构拒绝绝大多数充当**冗余/质量门**，不会删除该 competition 在语料中的
全部可用支持；同时 gate 不是 vacuous，因为它也识别到一个真实的 coverage gap。这个结论补强 Decision Corpus 的摄取与
审计可信度，不是 critic accuracy、模型 scaling、search utility 或方法效果。

## 重要边界

这不是 fully blind headline：旧 12 个事件来自 6 个 competition，且旧分析已知这 6 个到较早快照时均有 accepted
transaction；最新第 14 个事件的全零 support 也已先由单事件审计披露。真正新增的信息是第 13 个事件的类别和全 14 个事件的
统一四类 census。prior anchor 也只表示“到该快照时已有支持”，不证明拒绝发生前已有支持，更不支持因果解释。

`event_weighted_support_quantity_aggregates` 会对同一 competition 的重复拒绝事件重复计数，不能当作 7 个 distinct
competition 的唯一支持总量。不得据此建立 task 白名单/黑名单或外推未来 rejection 的频率。

## 复验

- exact commit：`7ad0164d85b892fc0e809bcc43b3c235344620d0`
- focused/full：`12 / 1,947 passed`，full 有 48 warnings，119.83 秒
- producer A/B、非导入 independent verifier A/B、read-only before/after：全部逐字节一致
- formal root：mode `0500`，29 files，manifest `69fdc6cb...76764f`
- result / independent verification SHA-256：`f904ff54...917fad` / `39a634f0...276e6`
- network / forbidden path / identity-schema / credential hits：`0 / 0 / 0 / 0`
- GPU / paid API / model fit / base update：`0 / 0 / 0 / 0`

公开 release commit `361e941...01e3` 的 post-push v1 因外部 harness 未设 `umask 077`，一个既有权限测试在
`16 focused passed / 1,950 full passed / 1 failed` 后停止；fresh v2 只修 harness umask，随后 focused/full=
`16/1,951 passed`（48 warnings，145.85 秒），发布哈希、身份擦除、安全扫描与 clean-worktree 门全部通过，manifest=
`4cbbd83b...2f270`。这两个 post-push 都没有重算 census。

第一次 `ec2bf65...5e0e` formal 在 `12 / 1,947 passed` 后、首个 producer 导入阶段因 module path 错误停止；没有生成
result/verifier，也没有科学 readout。fresh `7ad0164` 只修为 exact worktree 内 `python -m` 启动，未改协议、输入或分类规则，
且未复用第一次 partial root。
