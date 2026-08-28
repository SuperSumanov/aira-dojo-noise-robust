# Decision Corpus 435-run provisional split-integrity certificate

状态：`PROVISIONAL_ZERO_LINK_SPLIT_INTEGRITY_CERTIFICATE`。

证书把两个独立、结果前冻结且共享同一 future snapshot 的审计组合成一个机器可验证结论：

- within-future：11,906 endpoints 中 11,894 可 fingerprint；Jaccard≥0.85 的 11,421 个高相似链接全部
  位于同一 physical run，跨 run=`0`；0.95 下 4,068 links，跨 run 仍为 `0`。
- historical→future：5,519 个历史 critic-train endpoints 对 11,906 个 future endpoints；Jaccard≥0.85
  精确检查 6,172,443 个候选，链接=`0`；0.95 下仍为 `0`。

两侧使用同一 `python_token_identifier_erased_v1` 表示、0.85 primary / 0.95 strict threshold 和同一
snapshot `887491a...`。七个 certificate gates 全真。builder A/B 与不 import builder 的 verifier A/B 各自逐字节一致；
正式 source commit `25efd3a9237e93177e3c8c91b8f73169a70d4213` 上 focused=`7 passed`、full=
`1260 passed, 47 warnings`。四个输入 formal/postflight 根及两个 Git 结果包 manifest 均重新验证。

允许主张：在固定表示与阈值下，没有发现跨 future physical runs 的高相似链接，也没有发现固定历史
critic-train population 到该 future snapshot 的高相似链接。边界：证书仍是 provisional（435/960、closure=false）；
不证明 semantic clone/pretraining contamination 不存在，不覆盖 12 个不可 fingerprint endpoints 或全部可能历史来源，
也不计算 predictor accuracy/effect/search utility。first-960+closure 后必须原协议重跑。
