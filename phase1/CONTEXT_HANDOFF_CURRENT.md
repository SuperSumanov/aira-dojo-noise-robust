# 当前短交接：只保留现场、方法边界和恢复动作

最后核验：2026-10-17香港07:15；用户窗口02:49–08:49，同范围批次统一批准。
本窗口GPU已全部闭合，无当前GPU作业；不启动第三GPU方案。继续会话内分析至08:49，再简报。
整理前完整交接在Git3c0981b057befa2f9af5702831ef641fff81969a；不重复载入旧队列、审批或长日志。

## 本地和远端

- 活跃checkout：C:/Research/New/my_project/MLEvolve/_codex_tmp/publication-feedback-20261001；detached HEAD有意。
- 本轮fetch后公开HEAD为3c0981b057befa2f9af5702831ef641fff81969a；新收尾内容尚待提交/发布。
- dojo-reproduce仍e4d478350e704e8c5927eba566b2847aaa6dcbab，未修改学长分支。
- 学长95journals/5任务是其报告、非我方复现；selected改善不等于best-found，跨天硬件/负载未控制；senior_update_20261017.safe.json。
- SSH linux5.cse.cuhk.edu.hk；备用137.189.88.148带HostKeyAlias及StrictHostKeyChecking=yes；网络断开不重投作业。
- PY=/research/d7/spc/yzyang4/venvs/aira/bin/python；SLURM_CONF=/opt1/slurm/gpu-slurm.conf。
- stage=/research/d7/spc/yzyang4/pairing-source-20261017-GWteBV；脚本/SCP退出0后才执行/核hash。
- 本地Python=C:/Users/yanze/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe；文件编辑apply_patch。

## 本窗口真实分母与全成本

| job | root（前缀/research/d7/spc/yzyang4/） | 闭合事实 | GPU秒 |
|---|---|---|---|
|18987|clock-pairing-20261017-v2|首组4wrapper/3有效后原门停止，无完整比较|733|
|18997|scheduling-selective-20261017-v1|32完整，35评分，结构/策略过门，质量false|30540|
|19004|scheduling-generation-quota-20261017-v1|32完整，但干预绕过，冻结读出失败|30576|

- 合计61849GPU秒=17.18027777777778GPUh；window_20261017_allocation_receipt.json。含启动/空闲/失败/清理。
- 上窗口39139GPU秒另账；18770更早。不得重复加总或称有效计算成本。
- 19004 Slurm COMPLETED0:0，5096秒×6，HK05:37:27–07:02:23；搜索完成不等于有效对照。
- 已封存readout禁止覆盖/重执行；不以新seed/延时补旧批。条件scheduling-diverse-20261017-v3父门false，永不submit。

## 18997：有效方法比较，但未赢

- source8384f405d58ee8e5173b8039fba4fa5b3b14bab7；planSHA1783555a7c680021b2a1bae874798f1042c0bfe79d0b11af70fa7f2a75d26e32。
- 比较sharedFIFO cap1与selective仅Aerial同类共置；Denoise在两臂都独占。32条、两次反序池比较，不是32独立处理。
- Denoise有向best差−.028238214366029694/−.0018636732167496284；Aerial+.00012828530652175818/+.0001363031381792501。
- selective实际共置3/4，保护延迟7/7；故不能说没有执行。原质量门false，停止该任务先验配方。
- 本地selective_18997_closed：原独立Node/12传输SHA通过；新增independent-metrics-20261017.json独立AUC/RMSE复算35/35，maxerror1.1102230246251565e-16。
- 独立metrics不是独立源数据构建或选解溯源。全76候选及时，35评分中34匹配+1较差未匹配；不得叫晚到有效解。
- 16对相同首prompt/seed仅3对同首代码（去噪0/8）；32均匹配nativejournal。4配置/12CPU末端调用seed正确，不是实际HTTP抓包。
- 多的是Debug/Analyze而非稳定Improve增量；计数不证明因果。历史分析入口见ROUTE_DECISIONS，不重新做。
- 新adaptation-lineage回执SHA6ec665d244a8cd54820542b175526975d2a13ed24a0185ddd56a7d8dd2d19698：76返回/34有效，2谱系未解；新父后代12返回/3有效，Debug12有效；4/8池首提案后还有收益。独立聚合通过，原始关联未独立重提取；不是无反馈反事实，不得据此盲删Debug或称新策略收益。

## 19004：处理没有生效，禁止当成方法负结果

- source044cd889471417f357edfa6dcf8fdd2c7e262477；planSHAf08b3052fcecf467f500b5b9aa6638087c602321ca3a81bf22ef8b65a55b41f9。
- 原计划partitioned2+2 vs pooled4，同全局仲裁，执行均cap1。原唯一readout-20261017-v1在generation_audit失败，无summary.json，保留原部分文件。
- 原生host/worker取common.original.base.c.trial.install_hooks；只改上层facade，故实际仍selective readiness wrapper+旧每任务2FIFO。
- readiness仍存在，不误称也被绕过。4池均无跨任务借用；名义pooled池全局顺序违例12/7，旧每任务规则违例全0。
- 本地generation_quota_19004_closed含13安全源文件、独立逐事件重放/传输SHA、原读出失败receipt；quality_comparison_valid=false。
- closureSHAce69cc04504d7160c2d85024ad34b519047e09aeb5934f779c14b2432dbcd43b；hookSHAe5bfce70161aa611c3894a719c09b738f448d0768c809301a55e82347a66b571。
- 独立诊断远端failure-audit-20261017-v1不替换原readout，不从分数救方法或重新命名成A/A实验。
- 本地新hook修复shaec1b52590b7bda69cc6d651f53a3d9588e84a14cdae3764d0eb2d34eb31df2b6；未写回原root。
- cpu-hook-regression.json：旧绕过2复现；新真实host绑定/selector/readiness/10信号场景通过，0GPU/0model。仅CPU修复，线上干预仍未验证。
- 新production_gate源码改走actual host，但未独立运行其完整main；不能把回归脚本通过称整个生产批已验收。

## 继续工作而非新审批

- 整理三短记忆、记录On the Clock近邻限制、审查修复/安全产物，显式清单提交并只向我方分支FF推送。
- 不开新GPU；窗口余时优先能改变研究判断的分析，不重复已通过测试填时间。
- 下一轮quota若继续必须新root/原矩阵原门、真实worker干预回执先成立；统一批准有效，不反复索批。
- 18819局部排序翻转仍成立，但18845/18987未确认；早期严重干扰可被廉价监测发现，未胜SchedMate。
- 保工作量不保证保质量，Aerial是反例；shared服务/同seed不同提案限制纯执行因果归因。
- 无API/底座训练；不读first960/Target300/522/D_val/officialtest/16560，不碰Held12535、学长分支或用户dirty。
- 未跟踪用户报告、_codex_tmp、pooling_host_compat_20261016.sh保留。旧checkout只更新明确记忆主题，不触动其实验改动。
- 旧一次提醒已删除，无新自动跟进/新goal；08:49在本会话简报。实际发布日期/HEAD须在push后更新。
