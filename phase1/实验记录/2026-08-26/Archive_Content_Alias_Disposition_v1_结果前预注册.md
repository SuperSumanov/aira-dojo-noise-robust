# Archive Content Alias Disposition v1：结果前预注册

时间：2026-08-26（在显式汇总和验证全部 8 个待处置归档的内容哈希之前冻结）。需要诚实注明：触发本修复的旧
runner 已在失败路径中对排序首个待摄取归档计算过 SHA-256，并发现该 SHA 已存在于 transaction registry；虽然当时
没有输出 hash 值或处理其余 7 个文件，但“至少首个是重复内容”已经不是盲发现。因此本文件是生产修复协议冻结，
不是把 8/8 byte identity 包装成确认性科学发现。

## 1. 触发原因与边界

连续摄取在 poll 79 按协议停止：学长源目录新增了 8 个路径，文件名分别与已经提交的 `0824/` 归档相同，且观测到的 size/mtime 与对应旧路径一致。现有 runner 检测到首个待摄取归档的字节哈希已存在于 transaction registry，因此 fail-closed；这不是语料结果，也不能据此自动把任意重复内容忽略。

本操作只验证并处置预先声明的 8 个路径。它不修改 first-960 定义、不打开 outcome/label/prediction、不创建新 run，也不把“相同文件名或相同大小”提升为通用去重规则。任何未声明的未来重复仍必须 fail-closed。

## 2. 固定声明

alias 目录固定为 `0824-这里开始prompt变成system和user两部分/`，canonical 目录固定为 `0824/`；只允许以下同 basename 一一对应：

1. `cdiscount-image-classification-challenge-8seeds.tar.gz`
2. `lmsys-chatbot-arena-8seeds.tar.gz`
3. `new-york-city-taxi-fare-prediction-8seeds.tar.gz`
4. `osic-pulmonary-fibrosis-progression-8seeds.tar.gz`
5. `tensorflow2-question-answering-4seeds.tar.gz`
6. `tgs-salt-identification-challenge-4seeds.tar.gz`
7. `uw-madison-gi-tract-image-segmentation-8seeds.tar.gz`
8. `ventilator-pressure-prediction-8seeds.tar.gz`

声明 JSON 必须在任何 alias 内容哈希读取前生成并绑定 source commit、当前 `LATEST` snapshot 与自身 SHA-256；条目按 alias 路径排序且不可追加。

## 3. 固定协议

1. builder 只读 observation ledger、冻结 transaction registry 和源文件 stat；不打开、解包或哈希 alias payload。
2. builder 要求每个 canonical 已有唯一 committed transaction，alias 当前未 baseline、未 committed、未 rejected，且 alias/canonical/transaction size 一致。
3. builder 产出 hash-bound diagnostic receipt、pre-application observations 副本和显式 registry。
4. 独立 verifier 在应用前逐个流式计算 alias 与 canonical 整文件 SHA-256；绝不解包 tar；要求两者都等于 canonical transaction SHA。
5. production runner 再独立计算 alias SHA，并仅写入既有 rejected disposition 三元组：archive SHA、固定 reason code、registry SHA；不得新增 transaction、snapshot、run 或 endpoint。
6. 独立 verifier 在应用后再次核对 8 个 disposition、canonical transaction、byte identity 与 transaction 数不变。
7. 恢复 continuous intake 后，先执行一次 observe-only；再恢复 transition/WL/receipt/config 监控。未知重复继续使用原 fail-closed 分支。

固定 reason code：`ARCHIVE_BYTES_DUPLICATE_COMMITTED_TRANSACTION`。

## 4. 预注册通过门与杀死条件

全部满足才可恢复摄取：

- 声明数恰为 8，且 basename 一一对应；
- 8/8 alias 与 canonical transaction 的整文件 SHA-256 完全相同；
- 8/8 canonical transaction 在冻结 snapshot 中唯一存在；
- 应用前、应用后独立 verifier 均通过；
- transaction 数、`LATEST` snapshot、provisional first-960 run/endpoints 数完全不变；
- observation partition 中 8 个条目从 undisposed 精确变为 explicit rejected alias；
- 无未知 pending archive、无未知 duplicate-content 路径；
- outcome/label/prediction/raw archive member/env 读取均为 0；GPU/API/model-fit/base-update = 0/0/0/0。

任一内容哈希不一致、canonical 缺失、metadata 漂移、已有 disposition、条目数不为 8、出现第 9 个待处理路径或任一监控恢复失败，立即停止；不得扩大白名单或按目录整体忽略。

## 5. 13 项 pre-flight

1. **问题**：这 8 个新 source path 是否只是既有 committed archives 的逐字节别名？PASS。
2. **estimand**：声明集合中逐路径 byte identity 与 disposition partition；不估计模型效果。PASS。
3. **输入**：hash-bound declaration、observation ledger、冻结 transaction registry、整文件流式哈希。PASS。
4. **泄漏**：不读 tar member、journal、outcome、label、prediction、score/utility。PASS。
5. **对照**：同大小不同内容的单测必须被 runner 拒绝；未知重复不得自动处置。PASS。
6. **样本量**：穷举固定 8/8，不抽样、不提前停止。PASS。
7. **随机性**：无随机性。PASS。
8. **推断**：只做确定性身份与账本不变量检查，不报告显著性。PASS。
9. **成本**：总待读字节预估 183,409,093 bytes（alias；独立 verifier 另读 canonical），CPU-only，预计小于 10 分钟；GPU/API/model-fit/base-update=0/0/0/0。PASS。
10. **恢复**：任何失败都不写应用完成标记；修复后可从未处置状态重试。PASS。
11. **环境**：部署必须来自 exact-clean detached worktree 与固定公开 commit。PASS。
12. **安全**：只做 stat 和整文件 hash，不解包；边界感知凭据扫描与文件访问审计。PASS。
13. **晋升**：只有 pre/post verifier、账本 partition、monitor smoke 与 manifest 全部通过才标记 COMPLETE。PASS。

## 6. 允许的结论

若通过，只能写：这 8 个明确声明的 source paths 是已提交归档的逐字节别名，已在不改变 transaction/run/snapshot 的情况下被显式、可审计地处置。

不得写：新目录没有新语料、所有重复都安全、目录名所描述的 prompt 变化不存在，或未来同名文件可自动忽略。

## 7. 结果与恢复记录（2026-08-27 香港时间）

固定 8/8 aliases 全部与 canonical committed transactions 逐字节相同，合计 183,409,093 bytes；显式 reason code
写入后 transaction count/hash 仍为 `86` / `a8a445744371ae6809cf5eb80071790079875447303d2553874aee5e617a2160`，
snapshot 仍为 `8579d7cd...d9248`，first-960 暂定人口仍为 366 runs / 10,683 endpoints / 2,755 pairs。
fresh post-verifier、partition verifier 与语义门全部通过；label/outcome/prediction value/utility/tar-member 读取为 0。

formal-v1 的最终 broad filename gate 把 Git status 的 6 次 `newfstatat` 误计为禁读，故其目录诚实保持无
`COMPLETE`；独立 postflight-v2 证明实际 forbidden `open/openat=0` 并在新根完成，manifest SHA-256=
`1fa3c81c257316d2c2886ddbd36f72e60f1d8ed85f889450916e4d59de3a8625`。

公开 monitor commit=`bc362dfe95287f199f6bc4a1dc8f781f3b1b6ee0` 在 fresh Linux 通过 focused/full=
`32/1196 passed`。live initialize 与 poll 0 通过；archive path observations=`246`、baseline=`128`、ready=`0`、
rejected=`20`、transactions=`86`，因此新增 12 个路径尚只处于稳定性观察，不能称作新 run。transition chain 已从
`8579...d9248` state 恢复并记录首轮 no-change。GPU/API/model-fit/base-update=`0/0/0/0`，outcomes_read=false。
