# 短交接：真实对照无收益；单池选中好程序、CV错位已验证
最后观察：2026-09-13 05:51 UTC；本连续工作窗口02:58开始、目标05:58。不要创建automation替代会话内工作。
恢复先fetch→CURRENT_DIRECTION 0L193→本文件→核现场。长期约束见AGENTS，详细历史在报告/Git。

## 最新事实与裁决
- 主实验13213/13214已闭合：8技术合格、4配对0胜1平3负；停止扩大同配方，不启动24run。
- 13227 COMPLETED121秒：全部9未尝试原程序零API补齐，合全16为1有效14失败1历史未知。
- Space32唯一有效原程序.81494已被critic排第一且入top2；两个便宜排序前二漏掉。只是一池探索性正信号。
- 原程序CV折预测拼接对原行标签错位，指标缺失、被debug替换；e2e终点仍.79655，不回改。
- 13232 COMPLETED49秒：真实7823行同预测错误CV .49431164514891984，对齐 .8097916400357918；独立提交.80690。
- 原Optuna未seed，诊断固定20260913；不是原模型精确重放，不是31个百分点模型收益；预处理/HPO偏差尚未修。
- 原最终debug自报CV .810431高于诊断对齐值；不能替回旧轨迹宣称修复必然恢复收益。提交有效不代表原CV正确。
- 32近期开发run中5journal缺失；157可见节点/52有效提交，仅1此类案例。不称普遍解释/算法突破。
- OOF组件5测试及真实数组复核通过；真实MCTS解析器没有stdout标记自动回退。两次预期失败保留，最终负接入回执已生成；不宣称生产修复。
- action-delivery组件15测试+真实ForeTS钩子CPU接线过，但也未部署/未证e2e收益。
- 主线仍同预算e2e。新公共修复须两臂同版；研究修复本身则单独旋钮，不能与critic改动混因果。
- 旧first960/Target300/Target522保持封存；旧HCE/多保真/Probe/score-channel优越性/K>=1不自动恢复。
- 不训练agent底座；不要重做G0/模型验收。学长本地Qwen服务细节尚待外部事实，不猜端口/地址。

## 结果与单次读出（全部已经完成，禁止重跑）
报告 FORETS_THREE_HOUR_FINDINGS_20260913.md，以及FORETS_REFERENCE_RESULTS_20260913.md。
source f1cdee3a9e553e8efeedaa1a66a2c6bd778f9798。
主root /research/d7/spc/yzyang4/forets-wallclock-20260912-5_czzimk
主stage /research/d7/spc/yzyang4/forets-reference-stage-20260913-m3U9toWD
主controller 9cf2e7ec921730630568f3a090d81ca49cda46d2
主finish 6a456108ae1e9895bc4ae8902d3d58eac33e297a5cf2117c626694dfbac40f1e
初次flat-metric解析失败后独立兼容续读已完成；原intent/三个结果保留，原冻结reader不改。
lineage、anytime、机制、selection、analysis mismatch、incidence全部读完，禁止再跑。
新补齐root /research/d7/spc/yzyang4/forets-pool-completion-20260912-n3c3ijtb
补齐stage /research/d7/spc/yzyang4/forets-reference-completion-stage-20260913-YAc7gQ
补齐summary 9112b9d4a5bd5c7c0508e28b382d2777689e0fa7625220889929df37c2ca9013
CV root /research/d7/spc/yzyang4/forets-pool-completion-20260912-dcrffcf9
CV stage /research/d7/spc/yzyang4/forets-cv-alignment-stage-20260913-ywSbfE
CV controller d413bc6a8f30c8cd697159d12b84f24a99494d59
CV summary 60b903f151eda292a251b6579c570086292c8e4662b9a47a01f4f3086a688da7
OOF负接入回执38426ebf28dc17dc38949909ac3887b2c48645d95f31f93ebe659b24289aadd7。
CV逐行NPZ只留远端，不下载/推Git。本地results保存聚合证据；JSON/CSV相关目录已设置-text保留字节。
旧30/31主root y_p2tlmi、旧补齐cwhdnjnp均读完，不重跑；旧正Leaf31不能归因改选。

## 运维与保留边界
SSH linux5；Python /research/d7/spc/yzyang4/venvs/aira/bin/python。
SLURM_CONF=/opt1/slurm/gpu-slurm.conf；MLE任务用gpu27/gpu28 RTX3090，不是projgpu28/39；镜像不升级、无CPU回退。
本轮新GPU作业均已结束；旧held12535不动。不要按历史队列盲投。
累计责任账最后闭合1310调用、5388558392nUSD责任、3988558392nUSD已结算、仅2旧未知；原帽不重置。
PRIMARY_KEY远端映射OPENROUTER_API_KEY；不要读/记密钥值，不要再次向用户索取。
最近已核公开commit d413bc6a8f30c8cd697159d12b84f24a99494d59；新报告提交以实际git/ls-remote为准。
只push myfork HEAD:phase1-value-critic；不改学长分支、不新建分支、不强推。
05:46 fetch学长dojo-reproduce仍113e25e7fa2570cb5f60401d051a1de3cce307c2；Git未更新不证明远端语料未更新。
官方1TB研究盘到期2026-09-29，延期未知。无清理授权范围外删除。
SSH复杂引号会被剥；脚本用apply_patch+scp。远端无rg，可用grep；不要反复尝试带引号的squeue格式。
本地无关untracked codex_tmp/output/tmp/旧release/旧tests.xml保留；本轮新文件应选择性提交。
