# 生产来源事实：已追到哪里，还缺什么

## 2026-09-06 00:43：实际启动记录也已找回，缺口进一步收窄

固定143种旧归档SHA已恢复srun/local两类真实launcher：144份清单、143记录实例，676/676run均定位。
A/B和独立连接/闭包验证通过；447个Slurm step一致、1个未解释，228个local execution_id有记录。
此处补齐了真实启动范围证据，不等于所有scientific experiment关联已认证。
来源结构闭包后84run无旧hold/缺失成员/执行标识异常，仍非训练准入；运行环境快照实际85无权限、58不存在。
现阶段应解决快照/外部评分实际版本证据与未匹配成员，不应继续笼统称runner清单完全缺失。
详见[实际launcher恢复](results/historical_pool_lineage_20260906/README.md)。本次仍未重建Cards/G/L，没有新增模型收益。

## 23:28重要更新：不再是“找不到实际来源映射”

已从真实历史归档恢复全部676run的配置与journal定位，并发现/验证共享盘正确0811 leaf，补回原缺8run。
完整来源账本和旧hold保守闭包已物化并独立复核；见
[真实来源恢复报告](results/historical_source_recovery_20260905/README.md)。
139关联组件中38组件/138run没有旧hold关联，但这不等于完整开发资格；recorded版本、实际experiment语义和pristine环境不能混称。
仍缺可验证的生产端runner/experiment范围及当时执行/评分环境记录。下面22时的“三项全缺”表述已部分被本轮证据取代。
Cards/G/L尚未重建，不能把来源账本回执当成它们的构建记录。后续采用新构建实录，不伪造旧命令。

2026-09-05香港21:47后的核查。目标是解锁合格训练包，不是补造历史生产回执。
学长分支再次fetch成功，仍为`b8d095180415957aa1bab31fa53ead1bba261c03`，没有新outcome提交。

## 本轮新增的实物与来源事实

- 共享Drive新出现0904文件夹：6份压缩归档、无独立sidecar或子目录。已按原凭据隔离流程下载、
  fsync、逐包复算SHA、原子移入远端原始归档目录，并独立复核只读权限、mtime、文件数和hash。
  合计179805006压缩字节，归档数325→331；**归档数不是physical run数**，尚未解析内部内容或判定新run数量。
- 原始位置为`/research/d7/spc/yzyang4/external/senior_data/mle/0904`；私有文件名、原始包与可能存在的密钥不上传Git。
  稳定年龄最早在2026-09-06 03:44:48香港时间满足；之后仍须原冻结摄取协议，不能仅凭时间宣告资格。
- 当前已摄取快照仍为`76a2d7d426b1da88f30d28449506fea78208f9ca5cd012ba6316efe346462285`：
  649 physical / 623 eligible runs、3919 structural pairs、51 tasks，closure=false。这不是0904新增量。

## 已从确切源码确认的构建链

本节只描述该commit的代码行为，**不证明过去的发布实际执行了这些命令或默认值**。
所有下面列出的源码都先在远端做credential-shape检查，0 hits；没有执行数据构建。

|环节|已确认事实|仍不能据此推出|
|---|---|---|
|原始输入|下载脚本默认写`data/augmented_mle_critic/raw_journal`，保留Drive目录结构|发布包与我方归档逐一对应、输入范围已合格|
|batch Cards|`build_batch_cards.sh`遍历指定目录的每个直接子目录，每个子目录生成一个`batch_cards.json`|每个目录在真实生产端的experiment含义；全部run确属同一实例|
|physical run key|`build_cards.py`使用`dojo_config.json.id`与`metadata.launch_time`日期拼接；重复key拒绝|仅凭字符串就证明真实run隔离，或原始目录映射仍完整|
|配置记录|代码从config读取time limit、execution timeout、draft client model；硬件取env文件的`HARDWARE`|完整operator/generator/evaluator/config版本相同；substring筛选也不是exact-stratum证书|
|draft pairs|每个batch调用augmented builder并启用`--draft_pairs`；它能合并跨run根节点，代码明示假设输入为同一experiment|这些pair是真同父sibling，或输入experiment同一性已验证|
|improve pairs|每batch调用同builder、不启用draft合并；代码默认budget=0|发布的merged文件实际由这组默认参数生成，或没有混入其它关系|
|value pairs|batch脚本实际调用`build_subtree_pairs`，默认`budget_steps=-1`、seed=7、cap=200|仅凭文件名就确认目标定义、实际参数或与当前G定义一致；本轮没有运行它|
|运行出处|现有脚本只做构建/拼接，不在所读代码中持久化输入manifest与实际code/runtime调用收据|当前commit就是旧发布的执行版本|

与上述行为绑定的SHA-256：

|源码（相对学长repo）|SHA-256|
|---|---|
|`src/mle_critic/src/preprocess/download_and_resolve/build_cards.py`|`5390846d0c686c2b1014130743953d3ae1b6f26c4040fe19787256fbf931c0df`|
|`src/mle_critic/src/preprocess/download_and_resolve/download_journals.py`|`8d8dab84f687aa3ec838959afd8aa7e2facd18cf69112ba6bd305f5259f3d8b4`|
|`src/mle_critic/src/preprocess/build_bt_pairs/build_augmented_decision_pairs.py`|`8c9020a2745fb88ad7a8ca8fcd54df1d9e93f5daea63badc9ef7bd137c8bd524`|
|`src/mle_critic/scripts/preprocess/build_batch_cards.sh`|`5caf0be334791386404a1423cfb6e5298ffdd726167300722b4171d4ee175a70`|
|`src/mle_critic/scripts/preprocess/build_batch_cards_all.sh`|`481f32bf9e1a7105e5bb3cc9e0e9105688740cd4b5037fdad0a5794bc65bf881`|
|`src/mle_critic/scripts/preprocess/build_batch_draft_decision_pairs.sh`|`84e3c94bc07c36316aac500e1b94b5f2694125110125f86099a64b4c0be49fb3`|
|`src/mle_critic/scripts/preprocess/build_batch_improve_decision_pairs.sh`|`fdf23488a745d72498a0e2b0695af44e60728190cf469646066f8e9956456891`|
|`src/mle_critic/scripts/preprocess/build_batch_value_pairs.sh`|`461a4d06071ecaf912e6c51ed45720b7fcee59c4a0aa958b86970cd43a97290c`|

## 可以缩短交接，但不能跳过的三项事实

### 22:44补查：value目标不是由文件名决定

已读`build_subtree_pairs.py`全部源码，SHA为
`3121b14703bcb67007c8070adb6e7a7dd8d4844c00a9d7de8621161fce7a73cf`，credential-shape命中0。
`budget_steps=-1`排除所有后代，只比较节点自身成绩；`0`在这个构建器里是不限后代深度，不能直接映射为口语K=0。
批处理默认显式传`-1`。固定checker `7967ced39996173c0c921cedd3f1bcca7c260262`只执行`-1`的合成检查，
两任务10节点18pair与独立当前成绩比较相同，A/B回执字节相同；未执行lookahead或读取真实语料。
源码实际保留有成绩的叶节点，与其排除叶节点的文字描述不一致；`-1`仍先遍历lineage/runtime后过滤，
所以不能将该脚本当作保护全集上的结果盲工具。

另核上述三个构建器与三个value/draft/improve批处理脚本：当前b8d0951与候选LFS发布5baccb1源码逐字节相同。
**同发布树源码不等于历史实际执行版本或参数证明**；下面三项来源事实仍未齐备。
回执与复现方式见`results/source_target_semantics_7967ced_20260905/README.md`。

仍沿用[SENIOR_MINIMUM_SOURCE_HANDOFF_20260905.md](SENIOR_MINIMUM_SOURCE_HANDOFF_20260905.md)，不用手工编七份JSON。
我们需要生产方提供现成记录的位置：

1. 哪个明确输入范围可作为历史开发，而不属于first960/Target300/Target522或被改名的旧test。
2. 原始run-group目录到真实experiment/producer-instance的对应关系及含义；尽量保留原归档/目录层级。
3. 对应发布实际使用的Cards/G/L生成版本、命令/输入清单，以及生成与外部评分的运行配置/版本出处。

已知原始目录位置能帮助回填映射，但**当前没有该实际映射和执行记录，来源包尚未合格**。
无法追溯的旧字段保持unknown，不用今天的Git SHA代填。若旧发布不可恢复，可以明确另一个有完整执行记录的开发范围；
不能悄悄拿新前瞻语料或旧失败S0子集替代。

## 我方交付与后续动作

G0真实1.7B/16K工程执行已通过；新consumer的ZeRO3恢复验收另行排队12535，不与G0混称。
新0904归档的安全回执与独立复制复核见
`results/zero3_padding_repair_20260905/source_0904/`。
旧摄取守护已自然结束，本轮没有新建守护，不声称0904会自动入库。
GPU验收和来源资格全部通过后再物化受控train/dev并核算正式训练矩阵；当前没有新的方法收益/scaling确认。
