# 原canonical检查点的程序与完整重执行成本清点

2026-09-07 UTC02:18。依据已完成的role诊断，不合并实时日志、不修改原范围或原摄取。
原source ledger faf04cc（2026-09-05）已固定checkpoint/journal.jsonl；新角色选择不是看成绩后更换。
角色诊断source3b593af，A/B私有投影SHA052777ca3ab0ff2c2b265bd91d7488b561a3c708261418e37ccf1092d34cabad。
实际84run/24archive，检查点3547行，无重复step/未知格式；live内部1run有10个冲突step且174额外step。
这些live行及旧r1/r2失败均保留，不回填canonical、不静默去重成新节点。

本次只读已hash验证的A/B结构投影和原config/component元数据；0原archive/代码/label读取。
先复验角色诊断的访问trace、安全扫描、原5输入与源SHA、失败目录SHA、A/B原字节；
原merge函数仅接收每run一个checkpoint投影，独立组合枚举校验全部pair与family统计。
所有84run都保留：空代码、缺父、重复代码明确计数，不据此筛成绩或声明可执行性。
每个task/保守component统计至少2个不同字节的同父程序是否存在，报告支持范围与完整timeout成本。
不选择具体程序；完整成本只报候选条件上限，不等于已提交或已测GPU消耗。

CPU1/300秒/新目录，零GPU/API/model-fit；27项已有角色/投影Linux测试绑定。
生产A/B和独立组合计数完全一致；原投影不改、输入SHA前后相等，公开仅聚合，私有候选身份不导出。
成本双实现（组件最小完整timeout排序与全组合枚举）一致，不使用label/status/is_buggy过滤。
程序可用≠历史评分来源合格≠完整重执行成功≠训练准入；ADMITTED_RELEASES仍空。
