# 从实际历史配置恢复生产记录：前置检查

用户要求解决正式训练的来源阻塞。本轮先恢复实物证据，不再要求学长从零填写全部字段。
旧S0的失败裁决、所有test归属、确认集盲态和效果阈值都不修改。

已完成的只读定位：`aira-dojo-runs`仍存在，元数据枚举发现420份配置；此前固定历史selection的20份配置中，
20份记录Git commit/launch/Slurm，18份有meta_id，script_id均空。这不是待恢复676个学长run的覆盖率。
AIRA源码中meta_id来自RunnerConfig.id，是配置分组hash，**不是天然唯一的生产实例**；不得直接当独立experiment ID。

## 本次固定范围和资源

- 只使用旧a466888-v3目录已锁的146份archive manifest与676个run manifest。
- archive manifest SHA `72b74df7387254afc5ca3ec5d79029e74ae8371faa6216742e63be899419e8fd`；
  run manifest SHA `60846a3a68f4cc9644ad676aa89e0d250b5fb8c0a3b8f6c1a708f2b5d0fb3e4d`。
- 当前146文件共7935081757压缩字节；144个旧status=ok、另2个旧error不打开，保留明确缺口。
- 仅已有hash匹配的旧历史归档、且目录名匹配固定历史run的dojo_config成员可读取；日期必须不晚于2026-08-15。
- 两CPU线程、25分钟上限，每归档独立私有结果；不提GPU、不调API、不拟合模型。异常路径保留证据，不产生训练准入。

## 逐项预检对应

1. 只从实际配置读取版本、launch、Slurm、meta_id，缺失保留null；不从当前Git推定历史。
2. 配置重复key/凭据/日期错配/目录错配和tar重复成员先做便宜单测。
3. 不读pair标签、不改split；本轮只恢复固定历史run的配置证据。
4. 输出有配置/缺配置/多份配置/签名冲突计数，保留不匹配，不只报漂亮部分。
5. 无评估采样或模型指标；旧支持/效果门不改变。
6. 非模型运行，不生成checkpoint；逐归档落盘保留进度及失败。
7. 不解析journal、env、Cards、pair、outcome；真实数据训练仍需后续完整隔离核验。
8. 无随机抽样；固定历史清单全量扫描，不按结果挑归档。
9. 配置先credential-shape scan，再JSON解析；原文与run/路径标识均只留远端私有区，Git仅聚合回执。
10. 25分钟deadline在hash块和tar遍历中检查；预计10—25分钟，无无限自动重试。
11. 此次不是效果/功效实验；产物仅解除可恢复的来源疑问，不升级训练量或正结果主张。
12. 每归档FAILED_CLOSED记录原因且其局部记录不进入恢复映射；未知错误不伪装成功。
13. 不扩充旧抽签、不覆盖旧清单或S0；重建新训练包前另固定实际输入与分组规则。

构建命令与clean source证明仍分开：有记录的历史Git版本不等于已证明工作树无修改；
若历史pair构建命令无法恢复，下一步应从已核定原始输入进行一次新构建并记录当次真实命令，不能补造旧命令。

## 独立修复候选：0811共享副本（结果前补充）

共享盘四个历史问题文件已另存远端隔离区，只比较压缩SHA、未覆盖旧物件。
0811 leaf当前共享SHA为`8ade376fb045aa47bffa63b493fa5e4b02d376815d7700c9c9f441c1848edfa4`，
与旧错误拷贝不同。只核该固定物件的headers及先前恢复仍缺的8个历史run的配置payload；
不能依据archive日期猜run日期，必须由config.id+实际launch_time匹配旧run manifest。
单次300秒、A/B各一次、单CPU，无GPU/API。单元测试先验证重复成员、链接、凭据、日期错配、hash漂移拒绝。
独立核汇总与原668-run映射保持不变。此处是历史修复证据，非摄取/训练准入；不改变0904成熟期，
不覆盖旧S0或静默删除错误档案。journal/env只可查成员名，不读payload。

## 完整来源账本（在配置补齐后，读取journal字节前固定）

配置恢复已覆盖全部676run；本阶段仍不构建Cards/pairs，不解析成绩，不取“干净子集”追认旧S0。
固定combined mapping SHA=`fd8e0769f4561937f2959c055da18120e3715aaf3b772364cca72e1a4268aec6`。
重核其全部已知来源的配置SHA与对应regular checkpoint journal header；每个run全部来源都写入新私有ledger。
仅7个多来源run的journal做流式字节hash+credential-shape scan，不解析任何JSON字段；必须所有副本同hash，
否则停止，不按成绩/日期挑副本。此授权范围扩展仅为旧历史副本内容核对，不接触任何protected cohort。
两CPU，单次25分钟上限；每归档独立保存结构证据。新账本不等于旧S0改判或训练资格。
recorded-stratum仅删除明确的实例输出路径：solver.exp_name/checkpoint_path、interpreter.working_dir、
task.results_output_dir；所有输入路径、prompt/client/resource/image与recorded Git版本保留。
另固定保守关联组件：同一archive-hash+顶层batch目录，或同recorded meta_id的run必须同组；
组件任一run原hold=true，则整个组件不能用于train。只写这一结构闭包，不新分dev/test、不宣称真实experiment已获生产方认证。
本轮发现历史代码base_path无可访问目录（5不存在、4无权）；不得绕过权限或据Git字段补造pristine执行证明。

首次ledger入口64ba4b9在读归档前因reused_config_origin拒绝，未产生ledger。独立只读复核固定mapping发现：
7个多份配置run全部是相同archive SHA+同member+同config SHA的副本，不是不同origin；
全676run对应676个唯一origin，跨run origin冲突0。重试只合并这一精确等价键，所有物理archive副本都重新核hash，
原始出现次数保留。不同run或config SHA冲突仍拒绝；不存在distinct-origin重复时不额外读取journal字节。
