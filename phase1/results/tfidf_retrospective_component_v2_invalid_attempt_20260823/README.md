# TF-IDF component utility V2：首次运行无效

V2 结果前 commit `db7069db570523ac740b920202e37abb6493bc02` 已通过 13/13 聚焦测试、822/822 全测试与
0/0 凭据扫描，但正式执行发现两个工程/复现问题；两次失败目录均保留，不作为科学结果。

1. 初始 launcher 用文件路径启动模块，`phase1` 包根不在 Python 搜索路径；0.22 秒在 import 阶段退出，max
   RSS=39,360 KiB，Cards 未打开、无输出。修正仅为 `python -m`，使用全新目录。
2. 修正 launcher 后两个 producer 均完成，但 artifact 不逐字节一致，独立 verifier 以
   `V2 component rows differ` 拒绝。A/B summary 有 82 个数值字段差异，最大绝对差
   `3.552713678800501e-15`；40 个 component 行和 37 个 task CSV 行不同。根因是 V1 通用 solver 从 Python
   `set` 迭代候选后做浮点均值，不同进程 hash 顺序造成末位漂移。

尽管两个未认证 producer 打印了同一分类状态，该状态必须丢弃，不能引用。修复只把 endpoint 顺序显式排序；协议、
输入、component partition、estimand、bootstrap、阈值和 gate 全部不变。新增跨两个 `PYTHONHASHSEED` 子进程的
逐字节回归测试；修复后聚焦测试为 14/14。再次正式运行前仍须新 commit/push 和 fresh exact-commit 全测。
