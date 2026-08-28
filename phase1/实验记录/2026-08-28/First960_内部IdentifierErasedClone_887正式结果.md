# First-960 内部 Identifier-Erased Clone：887 正式结果

状态：`STRICT_LINEAGE_LOCAL_PASS`。本项是 provisional Decision Corpus benchmark-integrity 正结果。

## 冻结与执行链

结果前协议 SHA-256=`a0c5e73c2e6bde6eed920c69909d13d6b0207271758e327b30eb0b346e654f52`；正式 source
commit=`519815df29ef1f7073e93aa1835dd7df06a7a035`，snapshot=`887491a...`。formal/deployment roots：

- `/research/d7/spc/yzyang4/prospective-identifier-erased-clone-887/formal-519815d-887491a-v1`；
- `/research/d7/spc/yzyang4/prospective-identifier-erased-clone-887/deploy-519815d-887491a-v1`。

formal 与 deployment `SHA256SUMS` 文件 SHA-256 分别为 `bff2ca4d...893b30`、`128e3f16...ba586`。
独立 postflight 逻辑在 formal `COMPLETE=false` 时冻结，逻辑 SHA-256=`1b4ee9dd...720ee`；完成后 postflight
manifest=`e2535105...2a106`。

## 固定表示与结果

表示为 Python tokenizer 去 comment/layout，保留 keyword/operator，其他 NAME/NUMBER/STRING 分别替换为
`<IDENT>/<NUMBER>/<STRING>`；token 5-gram、BLAKE2b-128、minimum 20 distinct shingles。primary Jaccard=17/20，
strict=19/20；不按 task/run 过滤 candidates。

435 runs / 11,906 endpoints 中 11,894 可 fingerprint，coverage=`0.9989921048210986`。primary 精确检查
7,990,766 个 candidates，得到 11,421 links：

- parent-child：5,713；
- same-parent siblings：235；
- same-run other：5,473；
- cross-run same-task / cross-task：0 / 0。

primary cross-run affected endpoints/components 均为 0；strict 有 4,068 links，cross-run 仍为 0。五项 gate、384-doc
brute-force、producer A/B、non-importing verifier A/B 均通过；focused=`27 passed`，full=`1240 passed,
47 warnings`。结果前冻结的 independent postflight 重建同一最高档分类；forbidden/credential hits=`0/0`。

## 可主张内容与边界

可主张：在变量名和字面量均被抹去的固定 syntactic abstraction 下，高相似代码很多，但全部局限于同一 physical run
的 lineage；没有发现跨 run 高相似链接。这直接支持 physical-run split 的完整性与 run-clustered inference，而不是依靠
简单 raw-string uniqueness。

不能主张：semantic clone 或 pretraining contamination 不存在；12 个低于 fingerprint 条件的 endpoints 也未被认证。
当前 closure=false，first-960+closure 后必须原协议重跑。本项没有读取 prospective label/outcome/prediction，也没有计算
accuracy/effect/utility；GPU/API/model-fit/base-update=`0/0/0/0`。
