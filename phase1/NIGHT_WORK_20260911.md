# 六小时执行单：2026-09-11香港04:38—10:38

复用已有g0-r5 heartbeat，每20分钟续跑，02:38 UTC截止；不创建重复任务。
恢复时fetch，读CURRENT_DIRECTION最新节及CONTEXT_HANDOFF_CURRENT。只处理未完成项，不重复成功的验收。
目标是同预算e2e收益；不是赶稿，也不是增加审计或人工测试数量。没有GPU任务就明确说没有。

## 已完成，停止重复

- 0907/0909八个新压缩包已隔离下载，配置/预算metadata已检查；未进入生产/训练，目录数不是run数。
- 当前训练/服务编码差异已用4个人工tokenizer例复现；历史checkpoint模板未知，不擅自更改生产。
- common-priority显式可选源码补丁与真实批处理人工接入已测试。
- 新8份真实RunConfig与4对独立核对完成；不重生成、不重开13004余下6项。
- 外层预算更正已追加：280分钟/块；两块名义18.666666666666668 GPUh，含allocation KillWait为19.0。
  prepared.json里的17.0是旧提案；当下入口为results/forets_next_package_20260911/PACKAGE_STATE.json。
- 新两块控制器核心13项CPU测试通过，并绑定远端已有8配置；不是GPU部署、模型验收或新收益。
- 新读出模块20项CPU测试通过，并用人工关闭状态核过8份真实config；没有正式runtime manifest/实际成绩，不重复校验。
- 新runtime/collector接线22项CPU测试通过，Linux阻塞计时与SIGTERM清理已核；未发行可执行release，不重复写核心。
- 13004首对有效但负向；全部旧GPU尝试终态。G0/12892/16K/基础CUDA不再重复。

## 剩余工作，按依赖推进

1. **已完成接线，未发行**：新读出、runtime、独立collector都已完成CPU准备，见FORETS_RUNTIME_AND_UNBLOCK_20260911.md。
   不再拆模块重复实现或索批；CPU边界不等于真实调度器/模型实测。硬件/输入事实未补齐时入口保持关闭。
   两块各4run固定顺序、不自动retry/resume、不看结果选下个seed，保留失败/未开始槽位；每块单独新鲜路由回执。
2. **隔离新解已通过13040**：不使用--nv、仅绑定已分配设备和只读驱动/loader/ICD；原Torch与OpenCL GPU实测通过。
   正在把相同adapter接到实际Jupyter入口，双卡至多5分钟、两个单卡步骤人工验证；不重复13040直调测试。
   **仍等待外部问题**：checkpoint历史指令前缀。GPU9共享事实仍未知，但新路径不使用它。
   未回复不重复追问、不猜事实、不重复失败的/dev/null遮蔽。不改任务SIF、Torch或退CPU。
   自主已查权重header无历史记录、gpu28登记9卡/Slurm19.05.4；计算节点只读SSH缺已验证主机身份，未绕过。
3. **有变化才查外部动态**：fetch学长branch，新outcome先扫描再脱敏；新网盘metadata才触发增量下载。
   已有八包不重扫、不打开env/journal结果；first-960/Target-300/Target-522继续保护。

## 最小记录规则

- 用户要求优先在当前会话连续处理，不在每个小模块后结束。先尽力自行排障，再集中报告确实需外界的事实。

- 真实变化写短交接；精确证据写一次dated报告，旧版本留Git。不要再向恢复索引叠加多轮相互矛盾摘要。
- queue最后观察时点与SHA在短交接；没有复查不得写“现在仍然”。不干预12535/他人作业。
- 只push我方phase1-value-critic，先检查明确staged名单和完整内容；不修改学长分支。
- 没有新的实测收益就如实说明。遇外部事实缺失保留明确下一步，不以扩大预算或合成结果绕过。
- 窗口结束不新增工作、不取消无关作业；留下完成项/真实结果/未解事项。

详细路径、结果、哈希与边界均以 [短交接](CONTEXT_HANDOFF_CURRENT.md) 为单一恢复索引。
本文件旧执行历史保留在Git aac4acc0d74c3ac27a64f4959b1225ee9df54951的同路径。
