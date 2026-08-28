# Senior 0819 pair benchmark：run/endpoint 完整性与依赖结构审计预注册

日期：2026-08-29
状态：`FROZEN_BEFORE_OVERLAP_COMPONENT_AND_RUN_READOUT`

## 为什么做

学长在 `f534114e60658043c07f7a15d6440492caffc8ad` 新增的 0828 报告给出 mixed decision test 上的
探索性容量信号，但两个 Qwen3 seed 只在 seed 7 出现规模趋势，seed 6 没复现；RL 也还不是 matched comparison。
继续烧 GPU 前，更高价值的问题是：报告中使用的 1,160-row decision test 是否真的做到 frozen physical-run、endpoint
和 unordered-pair 三层 train/test 隔离，是否被单 task/run/component 支配，以及 mixed builder 是否逐行保留了同一个
decision test。若通过，它是 predictor benchmark 的正资产；若不通过，现有 scaling 数字只能继续留作探索。

这不是 first-960/Target-300 揭盲，不计算任何 accuracy、loss、scaling 或 search utility。报告中的已有模型数字在冻结前
已经看过，因此本审计永远只能称历史完整性证书，不能称前瞻模型结果。

## 冻结输入与已知/未知边界

机器权威为 `phase1/senior_0819_pair_benchmark_integrity_v1.json`。输入全部绑定
`f534114e...` tree 下的 Git-LFS OID：Cards=`5e0f3807...6c343`、run split=`593117cf...03bb`、mixed=
`7792a7da...cf6e`、decision=`1a01d3a1...1442`、value=`8a01dfb9...405`、hardware/time value=
`60e9bbfb...3d9`。builder/apply-runsplit/build-runsplit 源码 SHA-256 也分别绑定为
`e7302d5f...1e63` / `4c110661...fc08` / `bb5b5c98...402b`。

冻结前已知：报告数字、总/train/test 行数、字段 schema、run manifest 为 845 all / 189 hold。冻结前未看：

- mixed train/test 的 unordered pair、endpoint、physical-run overlap；
- mixed test 是否与 decision test canonical multiset 完全相等；
- test 的 task/run/endpoint/component 广度和最大贡献；
- mixed train 每行是否来自声明的三套 source train union，以及 source membership 是否唯一。

## 固定分类门

所有 hard gates 都必须通过：输入 hash/计数、Cards 对 manifest 全覆盖、Card ID 唯一、已存在 parent 不跨 run/task、
所有 pair endpoint/task/split 与 Card→run 映射一致、decision 两端共享 recorded parent 和 physical run、mixed test 精确保留、
mixed train 有声明 source 支持、train/test 的 unordered pair/endpoint/run 均零交叉、test 无 unordered duplicate、全 mixed 无
反向冲突。任一失败直接分类 `HISTORICAL_PAIR_BENCHMARK_INTEGRITY_GATE_FAIL`，不许被模型分数或某个子组救回。

全部 hard gates 通过后，strongest breadth 还固定要求：test pairs/tasks/runs/endpoints/components 至少
1,000/20/50/500/100；最大 task/run/component pair share 不超过 1/4、1/10、1/4。全部通过才是
`HISTORICAL_RUN_ENDPOINT_DISJOINT_EXACT_TEST_PRESERVATION_BROAD_SUPPORT`；hard 通过但 breadth 不全过只能是
`...LIMITED_BREADTH`。

source membership 只能证明某行存在于哪些输入池，不能证明它实际由哪个 sampling draw 产生；若 value 与
hardware/time value 重叠，必须如实报告不可唯一恢复，不能反推 8:1:1 最终组成。

## 安全与失败史

Cards 为 779,146,574 bytes。正式解析前先做全文件 credential/private-key 扫描；扫描为 0 命中，safe SHA 与原 OID
相同，receipt manifest=`8dd2c4ef...bf21`。没有打开 senior raw archives、`.env`、first-960/Target-300、outcome 或
prediction 文件。

首次扩展 materialization 根 `input-f534114-v2` 因手抄 mixed SHA 时写错一段而在 scientific read 前退出；失败根保留。
新根 `input-f534114-v3` 从 Git LFS pointer 机器核对的 SHA 重建，8/8 文件 credential scan 为 0，readiness manifest=
`0553e626...131a`。不得把 v2 改写为成功。

另外，安全预检发现学长 0828 报告正文含 credential-bearing dashboard URL。没有访问该链接；临时本地/远端报告副本
已经删除。正文路径和 commit 可以保留作事故定位，但不得复制 token。需要维护者撤销该 token 并清理 Git 历史；本次审计
不依赖该 dashboard。

## 实现与资源

protocol/producer/独立 verifier/test/runner SHA-256=`8991d304...eb30` / `16997ff0...7352` /
`5bdb7834...4e7b` / `f4e5faef...fba3` / `8dbf88a1...7917`。独立 verifier 不导入 producer；formal runner 固定做
producer A/B、verifier A/B、逐字节比较、focused/full tests、file+network strace 和 aggregate-only manifest。

资源上限：CPU/network only，预计正式四次 streaming parse 加测试约 20–45 分钟；GPU/API/model-fit/base-update=
`0/0/0/0`。任何 OID/schema/run/split/source ambiguity 均 fail closed，不增加 threshold、不改 population。

## 即使 strong pass 也不能说什么

- 不能把 seed 7 的 14B proxy 数字升级成 clean scaling law；seed 6 未复现仍必须同表披露；
- 不能把周期 validation 使用过的 1,160 rows 称为 untouched frozen final test；
- 不证明 semantic/pretraining contamination absence；
- 不证明 critic 能改善 AIRA/MLEBench end-to-end search；
- 不授权 RL、agent 底座微调、GPU 重训或付费 API。
