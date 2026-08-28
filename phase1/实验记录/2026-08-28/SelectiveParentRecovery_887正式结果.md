# Selective parent recovery：snapshot 887 时间切分正式结果

日期：2026-08-28

## 裁决

结果前冻结的最强分类一次通过：
`DEVELOPMENT_TIME_SPLIT_HIGH_PRECISION_SELECTIVE_PARENT_RECOVERY`。

这不是把 0HN 的 94.42% 总体 concordance 换个标题。新实验先按 immutable run-ledger 把 435 个 physical runs 固定成
较早 290 个 train runs 与较晚 145 个 test runs；margin 阈值只在 train 上按 precision≥99%、support≥500 后最大化
coverage，test 一次读取。最终 train-only 阈值为 `1006/16929`。在 2,907 个 test ambiguous edges 中接受 2,691 个，
其中 2,684 个指向 recorded parent：coverage=`2691/2907=0.92569659442724461`，
precision=`2684/2691=0.99739873652917133`。全部 support、precision、coverage、error reduction、task/run breadth 与
anti-dominance 门均通过。

因此当前可守的实质正结论是：**在已披露 development snapshot 的预先声明时间切分上，只从较早 runs 学到的简单
exact-Jaccard margin reject rule，能以 99.74% precision 和 92.57% coverage 恢复语料中已记录的 exact-depth parent
pointer。** 这把 parent content concordance 从总体描述升级成了可供发布的 selective self-audit 层。

## 为什么不是分母幻觉

无 reject 的 test unique-top 为 `2845/2907`，错误 62 个；固定 reject rule 后为 `2684/2691`，错误 7 个。任务与
run 维度不是由一个大组撑出来：25/25 个可条件化任务达到 0.95 reference，138/138 个可条件化 runs 达到 0.90
reference；最大 accepted contribution share 分别为 task `44/207`、run `55/897`。

错误候选必须同时报告三种口径：

| 口径 | exact value | decimal |
|---|---:|---:|
| all wrong alternatives micro FPR | `7/11257` | `0.00062183530247845781` |
| 每 child 均匀替换一个 wrong parent | `58/43605` | `0.0013301226923517946` |
| 可定向挑错的 child-level adversarial vulnerability | `7/2907` | `0.0024079807361541109` |

不能只展示最小的 micro FPR，也不能把三个分母互相替换。

## 完整性

- protocol 在 margin distribution、阈值与 chronological test profile 未见时冻结；
- train/test physical-run overlap=`0`，没有 edge random split、task 重平衡或 test-label threshold selection；
- producer A/B 与独立 verifier A/B 各自逐字节一致；独立 verifier 不 import producer；
- focused/full=`23/1448 passed`；文件与网络访问审计、凭据扫描均通过；
- prospective truth/prediction、Target-522 profile 与 raw senior archives 未读；GPU/API/model-fit/base-update=`0/0/0/0`。

正式 aggregate / verifier / manifest SHA-256 分别为 `2aca589f7d8f943360e9d1d7c3716744b0357d99918913729aecf898a59a2690` /
`50b3a280ffbc4ea7d404065a97a7450b41c18ec5a89c95bc5644b88bfdbe2955` /
`c51ad0948510a2d092bf3aa9db905558fbb645454296b587c921d973e6b2e281`。正式包位于
`phase1/results/tree_content_selective_parent_recovery_887_20260828_63d37cf/`。

## 主张边界与下一步

recorded parent 不是外部语义或因果真值；primary 排除 orphan；一般 similarity lineage、selective classification 和
parentage verification 都已有直接先例。当前只主张 MLE Decision Corpus 的 provenance+graph+content 三层完整性资产，
并只建议输出 `suggested_parent + confidence + provenance`，不静默重写 canonical edge。

下一步应在 Target-522 首个自动锁定、至少 87 个不重叠未来 runs 上冻结复用同一阈值，做真正 forward confirmation；
不得在未来样本上重选阈值、降低 coverage/precision 门或用累计 887+future population rescue。
