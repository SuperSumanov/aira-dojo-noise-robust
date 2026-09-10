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
- 13004首对有效但负向；全部旧GPU尝试终态。G0/12892/16K/基础CUDA不再重复。

## 剩余工作，按依赖推进

1. **控制器适配**：用户已明确批准的新读出模块完成，接口见FORETS_BLOCK_READOUT_20260911.md，不再索批或重做。
   现有BlockPoolControl只是核心，不得冒充完整production入口；CPU人工边界通过不等于调度器或模型实测。
   保持两块各4run固定顺序、不自动retry/resume、不看结果选下一个seed，保留失败/未开始槽位。
   仅推进已批准范围的CPU实现；已有拒绝校验不重跑。未具备实际环境事实时不启动资源型子进程、API、模型或训练。
2. **等待已发外部问题**：GPU9共享/受支持单卡OpenCL方式；checkpoint历史指令前缀。
   未回复不重复追问、不猜事实、不重复失败的/dev/null遮蔽。不改任务SIF、Torch或退CPU。
3. **有变化才查外部动态**：fetch学长branch，新outcome先扫描再脱敏；新网盘metadata才触发增量下载。
   已有八包不重扫、不打开env/journal结果；first-960/Target-300/Target-522继续保护。

## 最小记录规则

- 真实变化写短交接；精确证据写一次dated报告，旧版本留Git。不要再向恢复索引叠加多轮相互矛盾摘要。
- queue最后观察时点与SHA在短交接；没有复查不得写“现在仍然”。不干预12535/他人作业。
- 只push我方phase1-value-critic，先检查明确staged名单和完整内容；不修改学长分支。
- 没有新的实测收益就如实说明。遇外部事实缺失保留明确下一步，不以扩大预算或合成结果绕过。
- 窗口结束不新增工作、不取消无关作业；留下完成项/真实结果/未解事项。

详细路径、结果、哈希与边界均以 [短交接](CONTEXT_HANDOFF_CURRENT.md) 为单一恢复索引。
本文件旧执行历史保留在Git aac4acc0d74c3ac27a64f4959b1225ee9df54951的同路径。
