# 历史启动前模块来源核对（结果前冻结）

> 执行后勘误（2026-09-06）：以下为79164e0执行前的原规则，未事后放宽。首个未知行已经被读入，
> 它可能属于任务阶段，故“启动前前缀”仅是解析目标，不能保证零任务阶段字节读取。
> 原summary的task_phase_log_reads=0不被独立复核接受为字节级保证；原回执保留，修订源码仅纠正未来字段和说明，未重跑归档。

问题：已固定结构条件较完整的84个历史run，实际启动时导入的dojo/MLE-bench路径是否来自manifest记录的snapshot？
只填运行出处记录，不推断安装revision/pristine，也不构建Cards/G/L或读科学结果。

输入固定ledger SHA `8e48b4c6598cf8efe205fc6cba5cdd27d14621eb13fad42a7fd4180953da00d1`，
launcher lineage SHA `fe05dddcd4fe8a3f2208652ce51c9b06df9b9b8f57a5fa655d2029caddcf9981`。
84由既有规则确定：旧hold闭包clear，整个组件无unmatched成员、uncovered run或step异常。不能根据本轮可读性改挑子集。
完整676映射与旧hold不动。单条Slurm异常另有两份实际worker身份文件，第二次身份与config相同；仍在原hold中，不扩入84。

## 唯一新增读取范围

- 只读84run在其固定archive中、由原launcher manifest最新attempt明确引用的stdout/stderr文件的**启动前前缀**；不挑先前成功attempt。
- 只接受固定main_run源码里的Current working directory、三个package source path、Saving experiment artifacts、Output dir消息及空行。
- 读到`Instantiating the task...`立即停止；遇其它消息、凭据、重复字段、相对/异常路径、超64KiB或超64行也立即停止。
- 只在全部三个模块路径+cwd且任务边界出现时认定“完整启动出处记录”。任务内部日志、journal/env、worker result正文不打开。
- 不因stdout不可读转而扫描整份stderr；每一文件独立遵守相同严格前缀规则。未知前缀宁可报告不支持，不能找分数后再过滤。
- 输出路径只留远端私有记录，Git仅计数与哈希；模块路径相同不是模块内容版本相同。不得据此填写evaluator_commit。

## 执行与核验

源码、输入与规则在真实读取前固定；负控制含未知前缀、评分行、凭据、重复路径、相对路径、无边界、读边界后即报错的stream。
归档前后SHA/stat，重复/unsafe tar成员拒绝。两CPU、每遍600秒上限，逐archive落盘；CPU A/B比对完整公开与私有投影。
每次真实命令、时间、seed不适用、Python与Git/hash记录；独立核对日志绑定、84范围不变、边界与来源匹配计数。
本轮无随机抽签、GPU、API、训练或效果统计。若不支持，不放宽前缀去捞更多可用例子。
