# 新重执行标签的外部 grader 边界（不修改旧标签）

2026-09-07。仅准备与测试独立评分入口，不读取真实答案/提交/保护cohort，不训练。
固定 MLE-bench recorded commit 507f92e1138bb6e40dac5c6ee7a6758e6424bf97；当前187 Python文件已与Git比对。
源码检查发现不能假定各任务都严格验证ID集合，也不能把NaN视为有效分数，未知grader错误不应等于差标签。
新增公共边界只接受非空、唯一、同类型int/string ID与相同集合，排序副本后调用未改的trusted grade函数。
非法submission保留失败状态，不赋零；未知运行异常直接fail-closed；保留原始精度和五位舍入两列。
这是新完整重执行路线的明确协议，不用于重写旧成绩或对旧实验追加选择。

实际Linux检查拟固定6个具有至少两个历史组件的任务：dog-breed、google-quest、histopathologic、
kuzushiji、tabular-dec2021、tabular-may2022。全部使用手造小表及数学已知期望，0真实dataset payload。
正控：multiclass logloss=log(C)、单调Spearman=1、AUC=1、单框中心命中F1=1、accuracy=2/3。
负控：错误/重复ID在grader前拒绝；缺目标列由官方grader拒绝；常数Spearman的NaN被边界拦住。
生产A/B一致，独立数学期望与排序/ID对照复核；这只证明这些测试，不声称全面安全sandbox或真实label gain。

固定CPU1、0GPU/API、最多300秒、输出新目录；执行前exact commit、源hash/依赖metadata/源码树只读门。
与原187文件的Git blob字节一致；运行前后source hashes与import来源核验；脚本只导出fixture结果。
访问trace不得出现真实数据/保护cohort/用户凭据；记录所有失败，不自动改期望、不省略坏case。
如果source/dependency/格式错误，先保持失败证据再另版修复，不把未知异常吞成模型负结果。
