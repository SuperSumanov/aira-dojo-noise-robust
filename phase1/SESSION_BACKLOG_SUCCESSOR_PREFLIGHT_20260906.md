# 0903积压与0904新归档：有限续接预检

2026-09-06香港04:37。此前把完成六次调用解释成0904六归档已全部处理，属于叙述错误，撤回。
实际原session七次都来自0903；metadata-only核验显示还有0903一档、0904六档，均按原规则ready。
没有重复交易路径/hash/drop ID；没有读归档内容、保护候选身份或成绩。
结构回执SHA `474d458845b97fda6f527a764bdebd4044dc4350ed7c5a7e2fcf90563d719cf3`。

原session停在7次，既有记录和MAX_CALLS=9不改。新独立output目录最多8次调用，
用于7个实际积压事务+1次确认ready=0；不预先宣称第8次必然为空。
首调用不早于UTC20:39:13（前次完成至少300秒），截止UTC2026-09-06 02:20。
每次只处理一个原ready队首，预计7×约2–3分钟CPU加300秒间隔，约一小时；GPU/API=0。
若新归档数变化、旧七回执变化、未知重复或结构失败，立即停止；不自动增额度/改登记。

13项预检：

1. 产物核base/entry/control/scientific SHA，续接只改会话输出、时间和调用上限。
2. 复用已经实际成功的同一foreground driver；先做源码字节、Python编译与旧前缀检查。
3. 原transaction prefix和固定drop/run identity规则不变，新快照逐次A/B+独立grounded复验。
4. 区分来源日期队列与新增run数；总归档331、baseline128、committed174、rejected22、pending7。
5. 没有accuracy/按score筛选；不改任务配对或读取评测结果。
6. 无模型；保存每次receipt、完整失败流和不可变快照。
7. 不读label/outcome/prediction values；rawstdout可能含archive名只留远端私有目录。
8. 不新增抽签；生产LATEST和事后独立audit state是两种promotion，不宣称后者先于前者。
9. credential-first规则/拒绝登记/alias登记原样；发布前扫描全部改变版本。
10. 单调用2700秒上限，整体不超过原睡眠窗口；不另挂monitor或占GPU。
11. 这是样本摄取，不证明训练量、模型效果或first960闭合。
12. 真实rc由原driver记录；失败留下不完整目录后不换索引重试。
13. 保留旧run归属、raw源和全部既有事务；旧session不再调用，新session绑定旧最终snapshot。

修正的待办：最终导出器须按实际交易和日期统计，而不是拿下载文件数当已完成事务数。
此前准备的“六事务+一次空检查”导出器未运行、未发布；不能复用其错误假设。
