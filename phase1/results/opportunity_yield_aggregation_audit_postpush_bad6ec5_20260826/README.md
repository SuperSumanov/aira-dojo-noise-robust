# Opportunity-yield audit：公开提交复现 receipt

本目录记录从 GitHub 发布提交 `bad6ec5428c62b6a213b0d75fa0d1e58d858b5d4` 新建 detached、
`GIT_LFS_SKIP_SMUDGE=1` Linux worktree 后的独立复现。contract 六个核心 blob 被逐一验证与原 source commit
`f97026221e099c11fa1ca8f2c13a95c389bea743` 完全相同；验证不使用本地未提交文件或 prospective state。

结果：

- focused：`20 passed in 0.42s`；
- full：`1067 passed, 47 warnings in 72.20s`；
- 结果包内 `SHA256SUMS` 四项全部通过；
- independent verifier 18/18 checks PASS，两个 hash-seed replica 逐字节相同，并与已提交 receipt 逐字节相同；
- fresh worktree 执行前后均 clean；
- remote formal `SHA256SUMS` 文件自身 SHA-256：
  `068322783ea6328c8b9f5c457c3a919d55e6e09bfe1f1d375ae0f5e39f3ee246`。

本 receipt 只认证公开提交的可复现性、机器 contract、结果包哈希与 authority firewall。它不认证 statistical semantics，
不产生 predictor accuracy/effect/search utility，也不把 informative-cluster-size 理论主张为新颖。prospective
label/grade/outcome/orientation、prediction values 与 raw archive payload 均未读取；GPU/API/model fit/base-LLM
update=`0/0/0/0`。
