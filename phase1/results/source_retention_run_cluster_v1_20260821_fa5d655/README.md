# Source Retention Run-Cluster Robustness v1

正式代码 commit：`fa5d65507bd6bab76b7bfaeda04584fae21b78c9`。
正式状态：`INSUFFICIENT_RUN_CLUSTER_TASK_SUPPORT`。

本目录保存远端只读正式产物的紧凑副本。完整产物位于：

`/research/d7/spc/yzyang4/source-retention-run-cluster/fa5d655-v1`

固定的 15-task universe 中只有 9 个任务同时达到 train≥5、frozen≥3 个 distinct physical runs，低于
预注册的至少 10 个任务支持门。因此即使九任务 run-equal Spearman rho=`0.7`、train-defined tertile 的
frozen high-minus-low=`0.1973544973544974`，也不得宣称 run-cluster robustness 通过。冻结程序在支持门失败后
不运行置换、hierarchical bootstrap 或 LOTO，相关字段均为 null/空。

producer×2 与 verifier×2 逐字节一致；独立重建最大差为 0。focused tests=`5 passed`，完整
`phase1/tests`=`632 passed, 25 warnings`，forbidden-path 与两类秘密扫描均为 0，正式产物可写文件为 0。
本地保存的所有选定文件均通过远端 `SHA256SUMS` 校验。

允许的裁决仅为：原 parent-equal transport 仍是有效描述性正结果，但当前 release 的 frozen physical-run
支持不足，尚不能把它升级为 run-cluster robust。不得结果后降低 run 门、减少最低任务数或将九任务点估计
包装成确认性结论。
