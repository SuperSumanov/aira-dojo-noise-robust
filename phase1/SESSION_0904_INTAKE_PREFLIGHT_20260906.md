# 0904 成熟后会话内摄取（2026-09-06）

用户授权睡眠期间继续当前主线；在当前会话逐次调用，不创建监控任务或后台循环。
0904六个归档已下载，179805006bytes；下载safe receipt SHA：
282ae8972a9153e15cdffe1c3f0a8e3deb05b6d84769af4243548fd71d89a4c1。
其最晚mtime+21600秒为UTC2026-09-05T19:44:48.903091；入口最早19:45:00UTC。
窗口到2026-09-06T02:20:00UTC止，在本次八小时授权范围内。

1. 不改科学算法、registry、cohort、scorer；control=b20dd2682d609c0236c138c08797678cf31a2fc0，
   scientific=5ed1988045a3fd8c365d001c87977314572383d9，仍仅向escrow写预测。
2. 复用此前foreground base和精确派生shell；预检源码SHA、干净worktree、锁、PID和旧日志SHA。
3. LATEST起点76a2d7d426b1da88f30d28449506fea78208f9ca5cd012ba6316efe346462285；
   后续每次绑定上一回执，外部变化必须停止，不盲目把新LATEST当成功。
4. 保留最小年龄6小时、3次观测、至少300秒间隔、至少600秒稳定跨度。
   年龄满足不代表稳定观测已满足。只在会话内按间隔逐次调用，至多9次；每次最多一档案事务。
5. 到期、调用上限、未完成旧调用或未知结构问题都fail-closed；不改mtime、不补造观测。
6. credential-first由固定runner执行；raw/env/live-event不向模型或公开回执输出。
7. 不打开label/outcome vault、保护集值、accuracy/utility或候选身份，不做模型效果分析。
8. 新snapshot仍必须固定代码的A/B、独立verifier、hash、trace和只读门完成才提升LATEST。
9. CPU-only、GPU/API/base更新=0；不改变排队12535，不调用sbatch。
10. 单次外层限制45分钟，失败保留未完成poll阻止下一次调用；不自动重启失败流程。
11. 公开只报告SHA、结构runs/pairs/tasks、closure状态，不把采集增长叫方法收益。
12. 每个调用记录返回码、脚本SHA、sync receipt、base receipt；命令失败立即停止。
13. 不调整入选顺序/抽签/停止门；first-960仍须满额且另有closure，不提前揭盲。

这不是重启旧常驻monitor。源码名`once`指每次进程只调用一次runner，无内部sleep循环。
