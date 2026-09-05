# 完整梯度累积与阶段末批：CPU接入边界预检

2026-09-06 03:24香港。仅补当前TRAIN文件入口未实际走过的8-microbatch边界。
已有consumer曾验证world2/pairs2/accum2；本次不把旧证据重报为新突破。
不改consumer、optimizer、输入生产资格或任一冻结研究协议，只扩展合成driver/verifier。

1. 目标：同入口真实128-pair更新、阶段短末批、完整AdamW/RNG恢复的消费与最终状态一致。
2. 固定32个合成endpoint、G130/L134互不重复边，G仅复用L已出现端点；每pair76 valid tokens。
3. Lbudget与full各seed6，2 CPU/Gloo，4433参数随机Qwen，float32/AdamW WD0/dropout0.1。
4. shape=2×8×8；每完整轨迹4更新，microbatch数为8/1/8/1。
   Lbudget真实pair数128/6/128/2，full为128/2/128/6；均264pair、20064tokens。
5. 每臂full、prefix2、resume2→4，A/B各6轨迹共12。每更新保存，不选择checkpoint。
6. 同seed同初始化，resume前故意不同RNG；独立验证器先核真实checkpoint文件/哈希再加载自有fixture状态。
7. 模型、AdamW、Python/NumPy/Torch RNG逐位相同；消费前后拼接相同；A/B稳定状态相同。
8. 无真实train/dev/test输入、无GPU/API；只读固定原reward类定义。不允许来源注册表准入。
9. 记录精确Git/依赖/命令/seed/失败和运行耗时；耗时不外推1.7B或GPU费用。
10. 每次重复≤900秒，单子进程组≤150秒，异常整组终止；外层930秒并10秒清理，不后台循环。
11. 同seed A/B不是统计复现；不输出accuracy/utility或声称正向效果/16K内存验收。
12. 本地先核endpoint、shape、确切token/pair布局；最初测试引用不存在的shape字段而失败，修正为实际pairs_per_rank。
13. 12535代码/环境不改，first-960/300/522和0904稳定门不变；CPU运行与成熟intake可独立并行。

运行前固定commit并按Git blob逐文件核导出包；原tiny模式保持默认。trace局限与上一轮一致，
仅文件调用证据，不声称OS/网络强隔离。不是新增方法实验或四fit真实数据效果确认。
