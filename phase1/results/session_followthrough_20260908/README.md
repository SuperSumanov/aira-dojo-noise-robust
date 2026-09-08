# 方案续行与0906摄取收尾（2026-09-08）

## 可核验的进展

原0906窗口的8次foreground调用全部完成，均有对应wrapper及独立post-audit。
前2次只观察，后6次完成新摄取事务；没有后台续跑，没有扩展窗口或启动第9次。

| 结构资产 | 窗口起点 | 收尾快照 |
|---|---:|---:|
| physical runs | 737 | 759 |
| eligible runs | 711 | 733 |
| eligible endpoints | 19351 | 19609 |
| structural pairs | 4380 | 4426 |
| tasks | 58 | 59 |

新增22 eligible runs、258 endpoints、46 pairs；距first-960还差227 runs，closure=false。
这只是前瞻人口积累，不是模型效果；6笔新事务也不表示0906全部11归档都已处理。
不得将这些前瞻数据挪入四fit训练，不读取受保护结果或私有候选身份。

固定source：`28a139f481764951485ad6d278920a2fa3efe62c`。
LATEST：`1b44e898bbae7ffc9098bbfa584ba842e0db2be5ae6bb8b5da0475d8ab34239f`。
snapshot summary SHA：`971d5bf25df0824ac69d28c7c88900218992b5fdb41e2e12e80403733f489baa`。
独立导出会话summary SHA：`3f8ccf17ae17743068ae59193446789c0f4e78c8f4b833dd0e597af28dac6e4f`。
`intake/manifest.json` SHA：`a4d0d0f0a8a01f3e26dae52ea80fefdb1029964fe6f61ea9208010ce40c43662`。
manifest绑定25个原始安全文件（8组三份回执加会话summary），不含本README或其它后来文件。

逐次核验包括原科学入口、已完成状态、至少300秒间隔、snapshot连续性、源码/hash/只读门及独立delta链。
导出后逐文件核对本地下载SHA和大小；没有输出私有archive名、run/endpoint身份、标签或预测值。
所有原失败、旧窗口和原始文件仍保留，没有清理用户数据。

窗口UTC03:40:46–05:40:46、max8、单call连独立核验2700秒上限均不变。
poll007虽打印了下一时间下界04:47:10.936892，但次数上限优先，不能据此启动第9次。

## 学长最新上传状态（04:36 UTC）

只读2个共享Drive目录页面；最新可见日期0906，11远端归档/11本地同名归档，未发现0907或0908日期目录。
0906无config-v2 sidecar、无额外非归档文件、无子目录。
这是当时的目录/名字检查，不保证名字相同的内容相同，也不代表本轮重新下载了归档或认证了训练来源。
当前冻结摄取源未改变。实际runner及`senior_upload_metadata.json`均保留，私有目录清单仅留远端。
安全summary SHA：`c38e0559551d19ddc4a8198437416abcbca85a28c561002fa43acc3623d67caf`。

## 模型主线不混淆

[新评分留存实现](../fresh_grade_capture_20260908/README.md)已通过29项Linux测试和6真实grader×31-case的A/B及独立重评分，
但尚未接入实际producer，不认证旧标签来源，也不是critic/scaling收益。
正式四fit仍缺独立开发范围和实际执行/评分记录位置；ADMITTED_RELEASES不变，0 GPU／paid API／model fit。
用户回复“可以”尚未提供实际记录位置，不将其当作来源证明。
下一关键动作是实际来源接入；若无可恢复记录，应明确事实后冻结新的开发生产范围，不继续用通用测试代替训练进展。
