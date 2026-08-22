# Prospective 0821 Plant task-identity fail-closed 与恢复

日期：2026-08-23。状态：精确结构拒收已冻结；尚未恢复剩余 archive。

## 发生了什么

连续 monitor 已先提交 `ranzcr` 与 `tgs` 两笔 0821 transaction，共 8 个 accepted physical runs；第三个
`plant-pathology-2021-fgvc8-8seeds.tar.gz` 在 frozen intake 返回
`journal must identify exactly one competition`，poll 57 按约定 fail closed。前两笔 transaction、LATEST 与
其不可变 snapshot 不受影响；本次失败没有产生新 intake/score transaction，也没有读取 outcome。

## 精确诊断与裁决

当前 Plant archive 被绑定为 size=`119572767`、mtime_ns=`1787408006000000000`、SHA-256=
`5213f40cb0246d927b5e825943232a8f6e2bf0eba7c7d7005a13740ba0a67b20`。固定 auditor commit
`5ee342f549311ece7bc111ddd0cb7ff08b740210` 先通过其实际拥有的聚焦测试，再独立双跑；diagnostic 逐字节
一致，SHA-256=`8277d6dfe0651d88179735d8e2088d2de1cf329e9c2720272804833b65d226fc`。

4/4 checkpoint journals 的 competition identity cardinality 全为 0。raw journal 每份都先做 credential-shape
scan，随后才解析 JSON；env/live-event journal、task 值、代码、stdout、grade、metric、prediction 与 outcome
均未读或未输出。模式虽然与 0816/0819 Plant 相同，但裁决不按任务名泛化，只绑定本次精确 bytes。整包按
`JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE` 拒收，不从文件名补 task、不做部分 salvage。

当前 control commit 的 registry-builder 聚焦测试 5/5；双构建逐字节一致，registry SHA-256=
`7c16889eb5ec57b1ca391b4171a997ad0fcd35d076ad6b34fddb53b556e35e6e`。第一次审计包装曾错误要求旧 audit
commit 中尚不存在的 builder test，因而在归档访问前退出；该失败目录保留。正式重跑把 audit/builder 测试按
各自 source commit 分开，没有删除或覆盖失败证据。

## 恢复边界

恢复前必须把 0821 registry 与此前全部不可变 registry 同时绑定到新的 clean control commit，并通过完整测试及
exact-commit 复验。恢复仍固定 scientific commit、activation、estimand、frozen scorer、6 小时 age、3 次观察、
300 秒间隔和 600 秒稳定 span；只做 CPU intake，GPU=0、API=0、model fit=0。transaction 真正 commit 前，剩余
archive 不能计入 cohort；score-channel truth vault 继续关闭。
