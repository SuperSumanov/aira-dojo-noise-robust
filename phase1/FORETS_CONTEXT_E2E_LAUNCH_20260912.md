# 资源条件化裁判真实对照已启动

2026-09-12。实际单次提交00:52:57 UTC，00:53:11 UTC观察13123在gpu28运行，首run开始、其余3等待。
不是G0、训练或模型验收；这是两任务×seed13×两选择器的4个MLE-bench真实搜索run。

部署controller `4c00af32133c411827a0f3d9678ccec0e1318656`，task source tree `5950c7d3acf1e03173ba2ea7081d8ba6593279d9`。
根 `/research/d7/spc/yzyang4/forets-context-e2e-20260912-5xz0w6iy`。
原镜像/生成器/6step/300秒/3540秒不变，两臂均一张RTX3090与6CPU，280分钟分配、最多5GPUh。
新选择器对完整未执行池作正逆两次Plus排名，以预先固定的平均Borda分接原top2/common-priority选择。

已通过实际源码导入、237源文件哈希及凭据检查、24父Python派生语法、typed config往返及同任务A/B归一一致、
host-only留档路径、shell语法、队列去重与两次真实生成路由。Plus公开价格/能力复核通过，未新增Plus验收请求。
生成路由结算0.00015366USD；所有旧费用及0.70USD未知责任完整结转，原100人民币预算不重置。
新的累计责任上限4.942593566USD，额外最多3.50USD；两臂所有API共同100请求/run上限。

公开回执在 [results/forets_context_e2e_20260912](results/forets_context_e2e_20260912)。原请求/代码/排名/提交只留远端。
独立收尾检查已另写，不修改运行代码；将核对真实双序排名/Borda、实际执行slot、最终选中节点、
原始提交的数值重评分与费用。全4终态前不读最终成绩，不在看到结果后改规则、不补失败槽。
目前仅能声称已开跑，不能声称产生critic收益；即使单seed正差，也不等于稳定收益或clean scaling。
