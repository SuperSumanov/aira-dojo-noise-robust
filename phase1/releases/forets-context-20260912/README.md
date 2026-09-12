# seed13真实部署的代码包

使用 `release-code-capsule-v3.tar.gz`；SHA256 `302e5b703846fc40fc7f7e8e14127a86c58131db24e50189d88e43eb7d142a82`。
controller `4c00af32133c411827a0f3d9678ccec0e1318656`，task source `5950c7d3acf1e03173ba2ea7081d8ba6593279d9`。
共284文件：237 source逐字节匹配Git，28 controller匹配部署哈希，许可证匹配源Git blob。
无模型/任务数据、候选、答案、结果或密钥。绝对路径配置用于复现说明，不应直接运行提交脚本或重置费用账。

v1/v2未发布：源码均匹配，但Windows换行转换导致两许可证不逐字节匹配；
v3使用 `git -c core.autocrlf=false archive` 的原字节，独立复验通过。此修复不影响13123任何运行文件。
