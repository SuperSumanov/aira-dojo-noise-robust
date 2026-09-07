# 历史日志角色差异诊断：不合并、不补标签、不准入

2026-09-07 UTC02:10前冻结。固定原84历史run、24archive及原输入SHA，不选程序、不执行。
旧r2在混合两个role时conflicting_duplicate_step失败，无正式A/B结果；完整失败目录保留。
此时不能称原语料损坏。faf04cc的source ledger已固定checkpoint/journal.jsonl为历史canonical；
b5c76eb的原摄取将json/JOURNAL.jsonl识别为live，仅取checkpoint。这两项在本诊断前已存在。

问题只为：冲突在canonical内部、live内部，还是两个role之间？
新入口只接受run根下上述两个精确路径，每run每role一份。先凭据扫描，原project严格结构门不改。
保留所有投影行，分别统计重复step、投影冲突、相同重复、未支持行和跨role字段差异；不挑最后一条。
只读step/parent/code SHA与长度/id SHA。历史成绩字节进入JSON parser但成绩字段不访问、不作选择。
private保存两遍投影及role差异，不向本地输出代码或候选身份。公开仅范围与聚合数。

13项检查：
1. exact source commit与helper SHA；2. 本地与Linux全部新旧测试；3. 原5输入SHA前后相等；
4. 原84范围/24归档；5. 精确role路径、一run一role，未知journal拒绝；6. 所有归档前后SHA/stat相等；
7. 256MiB/member、整轮3GiB/900秒/CPU1、零GPU/API；8. 凭据扫描先于解析；
9. 原旧失败目录SHA绑定且末尾再核；10. 独立JSON decoder逐member与role计数双实现；
11. 生产A/B及独立结果一致；12. hash/private输出/访问trace核查，不触保护cohort；
13. 不修改原merge/intake，不作source admission，不训练、不选择/运行任何程序。

即使canonical无内部冲突，也只足够继续制定完整重执行矩阵，不能证明历史评分、运行成功或critic提升。
本诊断不产生正式程序可用性训练包；若后续需要，另立canonical角色清点并独立复核，不消除失败记录。
