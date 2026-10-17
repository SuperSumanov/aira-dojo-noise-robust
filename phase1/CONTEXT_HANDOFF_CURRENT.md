# 当前短交接：现场、方法边界和恢复动作

最后整理：2026-10-17香港18:38；新窗口18:28:03–21:28:03，用户明确批准修复quota原矩阵/预算/终分门。
18:34队列只见旧Held12535；新quota-v2入口准备中，尚未创建远端root/提交，无自动跟进/goal。
整理前完整交接与精确SHA在Git b1603f953f1e20e8080e075ec2ebb6e1a4cc802f；不重读全历史。

## 位置与最新引用

- 活跃checkout C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001；有意detached HEAD。
- 08:45最终发布前fetch成功：我方公开b1603f953f1e20e8080e075ec2ebb6e1a4cc802f；学长dojo-reproduce仍e4d478350e704e8c5927eba566b2847aaa6dcbab。本文与服务边界诊断随下一提交发布，确切发布SHA见Git/会话最终回执。
- b160发布13文件：真实多进程CPU许可与78Analyze/107生成发布链；34e4fb0d发布53文件：195准入/谱系/247角色提示/时序。均安全扫描/显式清单/字节核验通过。
- 学长95journals/5任务是其报告非我方复现；selected≠best-found、跨天硬件未控；senior_update_20261017.safe.json。
- SSH yzyang4@linux5.cse.cuhk.edu.hk；备用137.189.88.148须HostKeyAlias及StrictHostKeyChecking=yes。
- PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
- stage=/research/d7/spc/yzyang4/pairing-source-20261017-GWteBV；脚本/SCP退出0后才运行依赖。
- 本地Python=C:/Users/yanze/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe；编辑apply_patch。
- 本地MEMORY/OPERATING_RULES在aira-dojo-codex-20260813/phase1/memory，不在活跃checkout；不把其旧方向当实时。

## 实际GPU分母与全成本

远端root前缀/research/d7/spc/yzyang4/；本地证据phase1/sandbox_scheduling。

| job/root | 闭合事实 | GPU秒 |
|---|---|---|
|18987 clock-pairing-20261017-v2|4wrapper/3有效后原门停止，无完整比较|733|
|18997 scheduling-selective-20261017-v1|32完整/35评分，策略有效，质量false|30540|
|19004 scheduling-generation-quota-20261017-v1|32闭合，干预绕过，唯一冻结读出失败|30576|

- 合计61849GPU秒=17.18027777777778GPUh；含启动、服务、失败、空闲、清理；window_20261017_allocation_receipt.json。旧窗口另账。
- 08:40 sacct复核：18987 FAILED1:0/gpu27/733s×1；18997 COMPLETED0:0/gpu3/5090s×6；19004 COMPLETED0:0/gpu3/5096s×6。本轮无未闭合作业；Slurm完成不等于干预有效。
- 两32条真实在gpu3六卡完成；18997 source8384f405d58ee8e5173b8039fba4fa5b3b14bab7，19004 source044cd889471417f357edfa6dcf8fdd2c7e262477。
- 原readout/评分不覆盖、不重执行，不延时/补seed。条件scheduling-diverse-20261017-v3父门false，永不submit。

## 方法结果与未证实部分

- 18997：shared cap1 vs仅Aerial同类可共置；去噪两臂都独占。去噪有向best差−.028238214366029694/−.0018636732167496284；Aerial+.00012828530652175818/+.0001363031381792501。
- 实际共置3/4、保护延迟7/7；原门false。独立AUC/RMSE35/35/maxerror1.1102230246251565e-16；未发现迟到好解或选解补救。不是32独立处理重复。
- 19004：worker取common.original.base.c.trial.install_hooks旧绑定，上层facade新hook未到达；两臂均每任务2，借用0。readout-20261017-v1失败、无summary.json；不当方法负结果/A-A研究。
- generation_quota_19004_closed含13安全源文件、独立事件重放与SHA；旧原件保留。closureSHA ce69cc04504d7160c2d85024ad34b519047e09aeb5934f779c14b2432dbcd43b。
- 新hook shaec1b52590b7bda69cc6d651f53a3d9588e84a14cdae3764d0eb2d34eb31df2b6，未写回旧root。
- 修复过selector/实际生产门main10场景/真实wrapper8进程竞争：峰值4/4、借用0/4、全部释放；模型body为stub。CPU修复≠线上借用/效果；不再重复绿灯。
- 三有效批195Improve准入，76新父；40/26/10余时在<300/300–600/600–900s。3联结改善均末组但小且混杂；8谱系未知含2有效，不补失败。
- 新父自身wait median .015124320983886719s，54次完成生成median108.86853349208832s；总等待不能当有价值反馈被堵。
- 18807的13新best发布：Analyze有借用wait仅2次均<1s；Debug新best受阻仅1次9.184827327728271s。长wait主要无效/未联结，提前救活仍未知。
- 247返回Improve完整父代码；V1混入Analyze假警报已纠正。18412 metric新父3改善仅首重复，不能救权重门/混合30与17min。
- 独立计数/时间/代数不等于原始谱系join独立提取。所有细节回执及旧完整说明在b1603f95；不重复分析凑进展。
- 08:35服务端边界复查：三闭合批12间隔/21采样均Running/Waiting=0；只否定“日志已有跨池忙碌证据”，不证明持续空闲或缓存无影响。回执SHA9339b98d853488e7787238e31d36b2eac033c7e40a0dbf58d6f4f2b1e1eeef71及独立代数通过，无GPU/模型/评分。

## 唯一下一分支与禁止重做

- 未来仅一次quota资格：原32矩阵/seeds，partitioned2+2 vs pooled4，同全局Analyze优先/FIFO，执行cap1；2服务+4执行，≤100min/10GPUh含全部成本。
- 新入口R已改为scheduling-generation-quota-20261017-v2，窗口硬限UTC13:28:03；源冻结/远端准备进行中。旧v1/19004不修改。优先已跑通gpu3，检查必要源/实际hook及相同输入，不重复问批准。
- 先验证真实worker借用；有效干预但原终分门false则停配方，不靠等待下降/补seed/新规则扩大。当前无新算法阳性。
- 公平契约/原质量门见CURRENT_DIRECTION；近邻与旧路线见ROUTE_DECISIONS。18819局部排序反转不等于新来源确认或胜SchedMate。
- 无API/底座训练；不读first960/Target300/522/D_val/officialtest/16560；不碰Held12535、学长分支或用户dirty。
- 未跟踪用户报告、_codex_tmp、pooling_host_compat_20261016.sh保留；旧checkout只改明确记忆主题。
- 三入口≤100/140/80行；长期经验放主题，详细证据留Git，不追加长历史/新长报告。仅最后观察标当前状态。
