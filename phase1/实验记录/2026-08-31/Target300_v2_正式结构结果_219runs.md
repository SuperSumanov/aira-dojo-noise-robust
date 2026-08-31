# Target-300 v2 正式结构结果：219/300 runs（2026-08-31）

## 正式结论

schema-amendment v2 在 v1 自动冻结的同一 `30945550...104f` candidate 上一次运行成功，formal rc=0。远端固定 venv 中
14 focused tests 与 1,877 full tests 全部通过；producer A/B 与独立 verifier A/B 均逐字节一致，manifest、只读门、
forbidden-open 与两类 secret scan 全部通过。

当前 cohort 为 `FUTURE_COHORT_COLLECTING`，不是 closed：219 physical runs / 69 archives / 31 tasks，距 target=300
还差 81 runs；boundary archive 与一次性 anchor 均不存在。83 个 observed future archives 已全部 settled，其中 69 accepted、
14 structurally rejected，没有 pending head。因此目前的限制是后续新增语料数量，而不是 unresolved intake 或 schema 错误。

相对独立验证的 `98f2` 前缀，新增 26 runs / 9 archives / 1 task；原 193 runs / 60 archives 全部 exact-prefix survived。
这证明 v2 兼容修正正常工作并保留 cohort 契约，但只是结构进度，不是 predictor accuracy、scaling、search utility 或方法效果。

## 精确收据

- release commit：`4a68c83fba90655e9d60344081ae2b53b7c36104`
- formal result：`4a68c83-30945550b6b1-8e42f764cc05`
- summary SHA-256：`6a9301af50fd8d471ffb40b55e59dee4dec987f73c94f0eccbbe6c803dd42428`
- verifier SHA-256：`5d3dec87aaab9e38f03fab7c89f05c390e54d091b004bf41cc7e3db69dcd785a`
- formal manifest SHA-256：`f05446579f8d808a7b37ad78566a0339a7999a9d70e1b2fec5388bce9b8fcbdc`
- safe verifier SHA-256：`b2b7a1a8cf869d3ee4b8c8a963df4281f32a6ac7189ca6d069ee0a1753de9b83`

v1 的 rc=2 失败原样保留且未重试；v2 没有换 candidate。全程未读取 candidate identity/profile/private selection，未读取
truth/outcome/prediction/accuracy/utility，GPU/API/model fit/base update 均为 0。
