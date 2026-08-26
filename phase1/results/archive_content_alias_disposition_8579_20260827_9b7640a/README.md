# Archive content alias disposition：8 路径显式处置与 postflight-v2

状态：`ARCHIVE_CONTENT_ALIAS_POSTFLIGHT_V2_PASS`

本结果包记录一个生产完整性修复，而不是 predictor 效果或新语料发现。固定声明中的 8 个 source paths 均与各自既有
committed canonical archive 逐字节相同；它们已使用固定 reason code
`ARCHIVE_BYTES_DUPLICATE_COMMITTED_TRANSACTION` 写入 observation ledger，未创建 transaction、run、endpoint 或
snapshot。

## 固定输入与结果

- source commit：`9b7640ae44bd4fabb0b06a28cc1887eec3983adf`；
- production commit：`90842c49dbd73d41d405a5ecdad2224ee447b375`；
- snapshot：`8579d7cd32091a11089b935217f7189e321b1d623dbaa69233182ba2fedd9248`；
- declaration SHA-256：`bccaa02bfc4ca07befc52ef16d5a1d8dcd1eebb38dd71b1cf614ac50645ae17b`；
- alias registry SHA-256：`080a6df133c8b8184267f074e0620b2a9ebf1d21616b0dfb7674eebad2c28dcb`；
- 8/8 aliases byte-identical，合计 183,409,093 bytes；canonical transactions=8；
- transaction count/hash 保持为 `86` / `a8a445744371ae6809cf5eb80071790079875447303d2553874aee5e617a2160`；
- first-960 暂定人口保持 366 runs / 10,683 endpoints / 2,755 structural pairs；closure=false；
- disposition partition：observed/baseline/accepted/rejected/pending=`234/128/86/20/0`；其中 alias reason=8；
- label/outcome/prediction value/utility 读取为 0；tar members 未解包；GPU/API/model-fit/base-update=`0/0/0/0`。

fresh post-verifier 重新哈希全部 8 组 alias/canonical 整文件并通过；fresh partition 与 v1 产物逐字节相同。postflight-v2
远端 manifest SHA-256 为
`1fa3c81c257316d2c2886ddbd36f72e60f1d8ed85f889450916e4d59de3a8625`。

## 失败历史与访问审计

首次 formal-v1 已完成实质状态写入和 pre/post verifier，但最终 wrapper 使用了过宽的文件名正则：Git status 对 6 个
含 `prediction` 的路径做 `newfstatat` 元数据检查，因而被误计为 payload 读取。v1 保持无 `COMPLETE`，所有原始产物
未覆盖，并新增不可混淆的失败标记。

postflight-v2 对 v1 原文件逐个校验后确认：pre verifier、runner、post verifier 对禁读路径的实际 `open/openat` 调用均为
0；6 条命中全部是 `newfstatat`。fresh verifier 的禁读 `open/openat` 同样为 0。失败尝试不能被描述为成功 formal；允许
引用的是独立的新 postflight-v2 完成件。

## 公开复现与 live 恢复

alias-bound monitor 修复由公开 commit `bc362dfe95287f199f6bc4a1dc8f781f3b1b6ee0` 固定。fresh no-smudge Linux
post-push 验证通过 focused/full=`32/1196 passed`，47 warnings；提交文件名与 blob 凭据命中均为 0。首次完整测试因数值库
线程过度并发停滞，失败根保持无 `COMPLETE`；在全部数值线程池固定为 1 的新根中，完整测试耗时 78.87 秒并通过。

live deployment 在启动前重新断言 snapshot、86 条 transaction 及其 SHA-256；poll 0 返回 rc=0，snapshot 与 transaction
均不变。observation journal 看见的 archive paths 从 234 增至 246，但该轮 `ready=0`、transactions=86，因此只能写“12 个
新增路径已进入稳定性观察”，不能写“新 run 已入库”。transition snapshot chain 随后从同一 `8579...d9248` state 恢复，
首轮为 no-change；WL、receipt、config 与 successor supervisor 同时保持 live。所有恢复步骤均声明
outcomes/effect=`false/false`，GPU/API/model-fit/base-update=`0/0/0/0`。

公开复现、摄取 smoke 与 transition relaunch 的 operation summaries（仅做 LF/行末空格标准化）、原始 log segments 和
远端 manifests 均随本包保存；远端原始 operation-summary hashes 以对应 manifest 为准。

## 允许与禁止的解释

允许写：**这 8 个预先声明的 source paths 是既有 committed archives 的逐字节别名，已在 transaction/run/snapshot
不变的情况下被显式、可审计地处置。**

禁止写：新目录没有任何新语料、目录名描述的 prompt 变化不存在、所有重复内容都安全，或未来同名/同大小文件可自动
忽略。未知重复仍必须 fail-closed；本结果不提供 predictor 效果、模型提升或 first-960 闭合证据。

结果前预注册：`phase1/实验记录/2026-08-26/Archive_Content_Alias_Disposition_v1_结果前预注册.md`。
