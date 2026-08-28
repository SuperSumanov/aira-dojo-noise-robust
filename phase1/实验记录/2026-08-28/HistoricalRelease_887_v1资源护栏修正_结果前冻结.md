# Historical release→887：v1 资源护栏修正（结果前冻结）

冻结时间：2026-08-28T07:35:06Z。完整 v11 release→固定 435-run future 的首轮正式执行在 producer A 阶段由
`timeout 1800s` 终止：formal rc=`124`，deployment rc=`1`，producer stderr=`0 bytes`，且
`producer_a.json` 未创建。该轮没有可读科学结果，也没有读取任何 aggregate、link count 或 classification；失败根与
`FAILED_RC` 永久保留，不覆盖、不删除。

根因类别为 pre-science resource-envelope underestimate，不是 integrity gate 或科学 classification 失败。结果前冻结的
人口、输入哈希、表示、17/20 primary、19/20 sensitivity、六个 gate、256×256 brute-force control、ordered
classification、producer/verifier A/B 与独立 postflight 均逐字节不变。唯一资源修正是把每个正式命令 timeout 从
1,800 秒扩至 5,400 秒；32 GiB 虚拟内存、单数值线程、CPU-only 与 GPU/API/model-fit/base-update=`0/0/0/0`
不变。新协议文件必须显式绑定旧协议 SHA、失败 commit、rc、结果文件缺失和未读声明。

新轮必须来自公开的新 commit、fresh detached worktrees 和全新 formal/postflight/deployment roots；不得复用首轮 partial
目录。若 5,400 秒仍失败，只保留第二个 immutable failure receipt，停止并先做结果盲性能工程，不能继续扩大 timeout
或改变科学参数。v8 evidence stack 最终必须同时绑定首轮失败史与新轮结果，不能把资源失败从审计链中抹去。
