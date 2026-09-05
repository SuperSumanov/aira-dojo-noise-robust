# 新输入桥接全链路验收与存储恢复（2026-09-05）

结论：**新train投影→参考编码→token计划→实际CPU critic→AdamW保存/恢复已整体验收通过**。
修复了Ghash上游仍要求真实G标签的问题。研究盘配额异常已作可恢复清理，12510恢复原配置排队。
这不是G-reuse/scaling效果，也不是合格真实数据包或GPU ZeRO-3已通过。

## 本轮实质改动

`PreparedTrainingInputs.required_label_keys(plan)`先验证plan及其输入/encoder/protocol绑定，
再列出该臂实际需要的标签。`true_sign_provider(..., plan=plan)`只接受这组keys，拒绝额外标签。
Ghash只接收L标签；Gbudget只需实际消费的G；L-only只需L。消费顺序和token计划不接收真实方向。
这是调用边界修复，不是声称旧Ghash曾在模型批次内读过G truth；旧批次已有禁止读取的检查。
caller依然必须先取得真实来源资格，不能把这个纯内存接口当成数据准入器。

固定合成48端点、G11/L13对、8-token head/tail、随机4433参数Qwen3、float32/AdamW、
dropout0.1、seed6、两CPU进程。截断后强制48种不同输入，逐端点对照原CardEncoder实际输出。
两臂G_to_L/Ghash_to_L各full4、prefix2/resume2、prefix3/resume3，A/B独立执行；
复用已有session/consumer worker，没有重写训练或恢复算法。Ghash模型回调若请求G真值立即失败。

结果前代码：`5b6e0bdd65f3e42860fd40e2d28120de90ed6d7e`。
原奖励模型/encoder source：`5f3bc362db922c8edee2ef134656dfdb9a2b74fb`；只抽取固定哈希的定义，
不调用原数据读取或训练main。运行时与24个导出源码无漂移回执见`source_binding.json`。

|检查|实际结果|
|---|---|
|远端输入/session/consumer单元测试|63 passed in 7.05s|
|A/B真实CPU工程轨迹|20条完成，wrapper退出0|
|每次完整轨迹实际valid tokens|384，与计划精确一致|
|独立加载真实model/AdamW/各rank RNG|16组比较逐位相同|
|实际检查点文件清单及SHA|36个bundle通过|
|A/B summary、CSV、trajectory|逐字节一致|
|Ghash传给标签provider的真实G标签|0|

独立验证器只在核清单后加载本轮私有合成checkpoint；没有加载真实语料、预训练权重或保护cohort。
同seed的A/B是重复执行验证，不是跨seed效果证据。代码和核验参数见`operations/run_train_input_session.sh`；
remote root为`/tmp/train-input-session-5b6e0bd-H87Jhq`。

## 失败和局限均保留

- 首轮`c0dc128`的共同代码尾部经8-token截断后只剩1种编码，不能用作有效的新输入集成验收。
  它通过63项单测，实际完成6条轨迹后触发240秒CPU时限，退出1；未执行B和独立复验。
  `diagnostic_c0dc128/`保留原始输出。修复端点尾部后强制48种编码，保留原算法/seed/验收标准；
  根据每次约38秒的框架启动耗时，将整个CPU A/B硬上限明确修正为1200秒，每次启动新轨迹前检查480秒门。
- 开发单测曾因异常类型不一致失败：外来plan已被拒绝，但暴露的是TokenPlanVerificationError而非PlanError。
  统一接口后23项本地检查通过，没有放宽非法plan接受条件。
- A的首次trace审计有161种未分类临时路径；保留`a.trace_audit.json`。
  v2要求观察到这些路径的成功O_CREAT及O_EXCL/O_TRUNC，再把之后的访问归类为该进程的临时文件。
  A/B分别4173602/4265984行，均无剩余未知路径、未解析调用或未完成调用；credential/protected字面命中0。
  `%file`不覆盖全部fd继承、网络和内容读取；**不是OS隔离证书**。两版审计代码和局限均保留。
- 导出器曾在B的trace审计文件尚未落盘时拒绝导出；等待审计终态后仅重做导出，未重跑训练或改变标准。

## 配额事件与排队状态

零GPU候选节点环境检查的提交函数，在记录sbatch.stdout时遇到EDQUOT。
原sbatch返回值未能持久化，因此当时先按“提交状态未知”处理，未直接重试。
核队列/记账未见对应metadata作业；后续test-only复现原`--gres=none`被拒绝。
`gpu:0`还受到站点CPU:GPU比例/partition/qos规则限制；未获得可用零GPU检查路径，未切换硬件。
注意：后来的test-only错误不是原调用返回值的替代证据。未来提交回执须先在可靠临时盘记录再镜像到研究盘。

12510在仍PENDING且身份/脚本逐项匹配后held，避免配额失败浪费GPU。
仅将11个经名单审查的软件包下载缓存body复制至远端临时盘、fsync并逐文件核SHA后移除原件；
移除分配量**3217080320字节**，未修改安装环境、训练检查点或语料。
备份仍在`/tmp/research-pip-cache-backup-svbm2hko`，可按清单恢复；临时盘不是长期备份。
原缓存包名/版本来自wheel元数据，不声称这构成上游软件真实性证明。

随后研究盘目标目录真实分配**1073741824字节（1 GiB）**并fsync通过，仅移除本次自建检查文件。
这足以覆盖当前微型验收的空间检查，不是后续大规模训练的4 GiB或长期配额保证。
12510恢复原d22a17f代码、两PRO6000、30分钟、no-requeue及4320 GPU秒上界；未重投。
19:02香港时间仍PENDING/Resources、实际0 GPU秒，调度暂估9月6日15:19:29，非承诺时间。
回执与精确路径见`storage/`及`scheduler_reconciliation.json`。

## 来源包与下一步

本轮fetch后的学长分支仍`b8d095180415957aa1bab31fa53ead1bba261c03`（9月2日提交）。
本轮已知Drive根metadata检查43 children/37日期目录、最新0903，无0904/0905，payload读取0；
不能据此断言其它共享位置没有上传。具体缺口仍是获准历史开发范围、真实run→experiment映射和生成/评分出处，
详见`../../SENIOR_MINIMUM_SOURCE_HANDOFF_20260905.md`。通用授权不能代填生产事实。

主假设仍为完整G-reuse→L的同token预算收益；不恢复旧方向，不启动不合格来源的15-fit，不揭盲。
剩余关键依赖：12510真实ZeRO-3验收、生产端事实支持的完整隔离训练包。
本轮使用固定配置、故障保留和独立复验约束执行，工程通过不累加为论文效果或录用概率。

导出tar SHA：`50befdc54378e7dca94c69a131a3bb57994253fb4200dd9c07e129015bad4bc4`，645120字节。
172个成员中171个文件由`artifact_inventory.json`逐项绑定，下载后全部本地复核；
不含二进制checkpoint、原始trace、语料或密钥。README是随后撰写的解释，不在原始回执清单中。
