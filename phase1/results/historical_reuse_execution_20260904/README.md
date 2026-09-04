# 复用候选的消费计划与L1前缀机会

2026-09-04。**真实历史输入的只读计划验证；不是模型fit、真实checkpoint验证或GPU节约实测。**
旧冻结v2与历史开发v1保持原字节，新预算和前缀共享尚未采用或获正式fit授权。

## 本次解决的问题

此前两轮已经证明3058条额外比较/28任务的复用支持和一次遍历54407806tokens。本次不重复图或来源四格诊断，
而是把这一候选接入既有完整pair预算规则，检查实际seed/hash顺序、阶段/循环末批、各rank参与和LR进度。
复用4095个既有L端点的编码长度和摘要，不重新编码，不读标签选边，不筛掉来源不合格pair。

A/B两次实际运行均rc0、stderr为空，耗时110.65613516326994与104.20196581818163秒；输出逐字节相同。
各含30份计划的独立逐描述器重放、6组G/Ghash输入及L1/Lbudget前缀对照。两种形状的pair/token/update账相同，
padding可不同。它们是30份计划，不是30次训练；没有扩大GPU/API/model-fit或前瞻评估访问权限。

| 臂 | 优化更新数（各seed/形状一致） | 双卡seed6/7/8的valid tokens |
|---|---:|---|
| L1 | 37 | 32187742 / 32187742 / 32187742 |
| Lbudget | 63 | 54401901 / 54396240 / 54403742 |
| Gbudget | 59 | 54399942 / 54392399 / 54404994 |
| G-reuse→L | 61 | 54407806 / 54407806 / 54407806 |
| Ghash-reuse→L | 61 | 54407806 / 54407806 / 54407806 |

G/L分界为24次G更新后接37次L更新。whole-pair上限54407806；Lbudget/Gbudget在下一个完整pair会超预算时停止，
余量逐单元公开，未截断末pair凑数。G/Ghash的输入、token、padding、update和LR计划一致，仅目标方向契约不同。
不声称五臂optimizer步数或GPU计算完全相同。

## 不删对照的潜在节省

L1的全部37次更新是Lbudget的精确输入/归一化/LR前缀。未来若能把第37步checkpoint作为L1只读评估产物，
保留五臂×三个seed的15个评估单元，可以将独立训练流由15变为12；本次没有真正创建这些训练流。

| seed | 五条独立流tokens | 假设共享L1前缀后tokens | 可免重复tokens |
|---|---:|---:|---:|
| 6 | 249805197 | 217617455 | 32187742 |
| 7 | 249791993 | 217604251 | 32187742 |
| 8 | 249812090 | 217624348 | 32187742 |

各seed减少比例为0.12885137053413664、0.12885818161513288、0.12884781517179572，约12.9%。
这项机会不删除L1评估、不降低收益门，也不提供新的独立seed。没有测实际GPU节约，未验证真实模型状态等价。

不能将中间checkpoint改名或改plan hash冒充另一臂。既有Accelerate checkpoint gate只服务合成CPU案例，
并不是生产入口。共享需要额外的原checkpoint/hash、parent-plan/固定边界、child-L1前缀绑定与实际状态证据；
中途不评估L1，完整训练和checkpoint锁定后再按获准协议评估。不同评估权重仍需保留，检查点数量/存储/I/O不会
自动减少。G0只预检一个4GiB保存空间，不能覆盖完整五臂模型资产。

## 尚未解决的门

复用池143对配置不一致、193对来源未明，L365对来源未明，同版本producer与experiment-closed划分缺口均未变。
本次不物化池、不更改旧S0，也不把metadata计划变成训练许可证。完整pair规则若遇到不足以供所有rank参与的末批
仍会拒绝；本次既定六组输入没有触发，不据此许诺任何新来源包必然同样可行。

静态G0批量形状与双卡计划相符；但其原Trainer/cosine和十步局部数据只用于计价，不能验证新阶段adapter、
constant LR、四卡或所有G输入的实际训练。必须等G0真实完成、来源门及明确GPU小时，不能把pending称在训练。
最终若critic指标提高，仍不能直接称agent end-to-end收益；另行固定完整执行预算的实际选择实验才回答后者。

## 复现与证据

- as-run code commit：`586cdc94a13fd0f8467d32d4bf246df4b0dd0a85`。
- archive SHA：`dcb47e0b24ecc41b0a5b74a5bdcdfb9b14373a2e2ee4c0b1aabb12c406335df1`；12个export文件与Git blob字节相同。
- 运行根：`/tmp/reuse-execution-plan-20260904-SOMkBg`，CPU单线程、A/B各上限300秒。
- receipt SHA：`5a8ddba9d8d1cf4acbf62a31d7ec06cfdcc9d9ff3f11c2fcb53872c52ff12a88`。
- 实际调用/退出码在runs.csv；输入SHA和诊断合同在producer_a.json；6个源文件/环境在execution_context.json。
- 下载后5个as-run manifest条目逐字节验SHA，6个as-run源码与精确commit blob相同；独立聚合账本验证见
  publication_verification.json。该后验聚合验证不替代生产进程中的独立逐描述器重放。
- 执行前25项接口/既有planner回归通过；新代码未加载模型、tokenizer或GPU上下文，未打开保护cohort。
  Python audit hook不是OS沙箱；原始旧JSON会被解析，只保留历史身份字段，不宣称从未读取含标签字节的文件。

manifest.json保持as-run原样；README和publication_verification.json是事后说明，不在原manifest中。
本轮定位文件时一次PowerShell通配路径传给rg报错、一次旧目录无匹配；均未改变实验或数据，不冒充计算失败。
