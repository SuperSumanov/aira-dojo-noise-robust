# 截止预算开发e2e源码快照（2026-09-12）

来源为原aira-dojo派生树900fa3bdf6971381c37a9792723dba42c63e5ac6；本包派生树
6780e383d20d6051ba53cace793f0db910027315，239源码文件。代码与方案commit ee544097a59b70b51493184a6d19b2ea7453ba8e。

source.tar SHA256：1207df148f3d8ba1a838c76df168ee070376d10add5e5b31db011d9ad07d93d6。
每个文件hash、确切改动路径及完整矩阵在artifact.json；MIT来源/第三方许可遵循仓库原LICENSE与
[前置源码包的THIRD_PARTY_LICENSES](../forets-readiness-source-20260912/THIRD_PARTY_LICENSES.md)，原文件头保留。

用途：新seed22/23、两任务、两臂共8run，600秒搜索截止，完整迭代后冻结原journal选出的incumbent与原提交关联。
源只增加被动留存、请求截止准入和监督时钟，不修改模型/排序/任务镜像/执行设备。
POSIX只能约束进程组，Slurm步骤清理与真实资源必须另核验；这是效果对照的执行工具，不是正收益证据。
无模型权重、数据集标签、API密钥或封闭cohort内容。17本地测试+实际导入CPU集成通过；不是新的GPU/G0验收。
