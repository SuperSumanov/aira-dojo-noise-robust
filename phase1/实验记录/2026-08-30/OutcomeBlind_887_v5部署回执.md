# Outcome-Blind 887 v5 部署回执

日期：2026-08-30
状态：`V5_LIVE_AT_BASELINE_887`

公开冻结 commit 为 `fc1ca43b28f61c5ce696914f2ad10f9cea79f86d`。第一次推前回执因 Git 把中文路径输出成
带引号的转义文本，使一个报告 blob 未真正进入扫描，却错误写出 PASS；该回执已明确作废，未据此部署。r2 改用 NUL
分隔的原始路径并重跑全套检查：changed paths=`6`，credential filename/blob=`0/0`，focused=`14 passed`，
full=`1677 passed, 48 warnings`，fresh detached worktree clean。

v5 launcher 随后从该公开 exact commit 运行，完整通过旧 intake 145-poll 正常完成、旧 guard RC1/poll71、baseline、
state/script SHA、死 PID/free lock、无 sidecar 与无 Target-522 candidate 等结果盲前置门。启动回执为：

- new intake PID=`883949`；
- transition/receipt/config-v9/Target-300/WL PID=`883964/883966/883970/883972/883980`；
- six-hour guard PID=`884262`；
- guard first state=`live_at_baseline`；
- launcher manifest SHA-256=`760c8300468e3093e24bb7eea013984c358aca3619eccc306ad571485d5dcf8c`。

fresh independent post-deploy 检查逐一确认七个 PID live、六个 monitor/guard lock held、launcher manifest 全成员通过、
guard 已写第一条 baseline 状态。`LATEST=887491a...62697`，config-v2 filename count=`0`，
`prospective_values_read=false`。GPU/API/model-fit/base-update=`0/0/0/0`。

后续只允许让固定链自然运行：若出现唯一稳定 successor，guard 只写 identity handoff，各 support monitor 按原协议处理；若
出现 config-v2 sidecar，只停在 metadata/redaction review 前；任何 FAILED、重复、锁或哈希漂移均 fail-closed。
