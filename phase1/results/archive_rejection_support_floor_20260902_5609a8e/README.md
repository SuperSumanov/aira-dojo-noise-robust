# Rejected-competition support floor（2026-09-02）

这是对已完成 14-event support census 的 **post-hoc、identity-erased、完整描述性审计**。它不重新估计
`13/14` event 或 `6/7` competition 的 prior-support 比例，而是回答：6 个已有 prior eligible support 的匿名
competition，支持是否仅来自一个脆弱 run，还是具有足够深度与冗余。

## 正式结果

6 个 prior-supported competition 在 prior 126-transaction anchor 上合计有：

- accepted archives：total=`20`，min/median/max=`1/4/5`；
- physical runs：total=`94`，min/median/max=`4/17/29`；
- eligible runs：total=`92`，min/median/max=`4/17/29`；
- eligible endpoints：total=`2,558`，min/median/max=`50/458.5/944`。

没有 competition 只靠一个 physical run 或 eligible run（两项 exactly-one count 均为 `0`）；只有一个
competition 只有一个 accepted archive，但该 competition 仍至少包含 4 个 eligible runs 与 50 个 endpoints。
最小 `eligible_runs / physical_runs = 5/7 = 0.7142857`，最小
`eligible_endpoints / eligible_runs = 25/2 = 12.5`。

支持也不是由单个 competition 完全支配：prior accepted archives、physical runs、eligible runs、eligible endpoints
的最大 concentration share 分别为 `1/4=25.0%`、`29/94=30.85%`、`29/92=31.52%`、
`472/1279=36.90%`。current 7-transaction window 只给其中 1 个 competition 增加了支持（`+1` archive、
`+4` physical/eligible runs、`+96` endpoints），因此上述 prior floor 不是由该窗口普遍补齐产生的。

这加强了一个有限但正向的 benchmark-audit 结论：当前结构拒绝通常是在已有、且往往具有多 run 深度的
competition support 上做冗余/质量过滤，而不是系统性删光可评测覆盖。唯一 no-support competition 仍证明 gate
不是 vacuous。

## 完整性与边界

- public exact commit：`5609a8e70098af0a912e61284529ca20d0a91f8e`；
- formal root：`formal-5609a8e-support-floor-v1`，mode=`0500`，files=`29`，`COMPLETE=true`，无 `FAILED_RC`；
- focused/full tests：`12 / 1,963 passed`（48 warnings，full=`147.02s`）；
- producer A/B、非导入独立 verifier A/B、read-only before/after 均逐字节一致；
- network / forbidden path / identity schema / credential hits=`0/0/0/0`；
- result / verifier SHA-256=`ce8b3010...f4248` / `3ab7085a...796c`；
- remote manifest SHA-256=`86973b22...06a1`。

该结果是 aggregate census 已揭盲后的 post-hoc 深度描述，不是新的 fully blind confirmation；样本只有 7 个匿名
competition，不作抽样推断，不估计未来 rejection 频率或因果效应。prior anchor 也不等于 rejection event-time
preexistence。不得由此声称 predictor accuracy、model scaling、search utility、方法效果或建立 task 白/黑名单。
本次未读取 label、grade、outcome、prediction、accuracy、utility、candidate identity/profile，也未启动 GPU、付费 API、
model fit 或底座更新。
