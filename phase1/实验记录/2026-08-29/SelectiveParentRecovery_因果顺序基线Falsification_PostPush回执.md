# Selective Parent Recovery 因果顺序基线 Falsification：Post-Push 回执

发布 commit `c030d362e13e1a5f1545fd4d5e743e7c98cc15ae` 已在远端 fresh detached worktree 完成独立 post-push
复验。

- 发布包 manifest：25/25 members 通过，SHA-256=
  `0a667d45022d6b08265268cf78cf2c91cd7ff41b45b0afe7dab0f6f4cfcaf373`；
- focused/full tests：`13/1528 passed`，full 有 47 warnings；
- formal result / independent verifier：均从固定 887 snapshot 重建，并与发布包逐字节相同，SHA-256=
  `34412b5281ceae6091536ac811b7b141edb15ba1b6043465abf8d00892927532` /
  `a9cf85a8aeae4145d1bba12ae1de8e0641b58bdcba9143ade0c43e2a692e8509`；
- 正式分类 `DEVELOPMENT_ORDER_BASELINE_FALSIFICATION_INTEGRITY_FAIL` 原样保留；有效 max-prior-step 的强描述性
  反证原样保留，无效 manifest-order baseline 未用于救回；
- syscall forbidden-open / network trace：`0/0`；commit filename/blob secret hits=`0/0`；
- prospective values、Target-522 candidate/profile、raw senior archives 未读，无 row-level release；
  GPU/API/model-fit/base-update=`0/0/0/0`。

## 失败保留与操作修复

第一次 post-push 目录
`/research/d7/spc/yzyang4/selective-parent-order-baseline-falsification/postpush-c030d36-r1` 保留 `FAILED_RC=1`。
它在 package、focused/full tests、result/verifier exact rebuild、forbidden-open/network 和 filename secret scan 全部通过后，
因 line-delimited `git diff-tree` 把一个中文路径输出成带引号的 octal escape，旧 blob scanner 将该显示字符串误作真实路径，
在创建 blob-scan 回执前退出。

新 r2 没有重跑或改动任何科学值，只逐项核验 r1 已有产物哈希与逐字节相等性，并将 commit path traversal 修为
NUL-delimited、`core.quotepath=false`。诊断精确复现 old quoted lines/failures=`1/1`；修复后读取 `29/29` changed blobs，
secret-hit files=`0`。r1 失败与 r2 修复同时保留，未覆盖目录。

权威 post-push root：
`/research/d7/spc/yzyang4/selective-parent-order-baseline-falsification/postpush-c030d36-r2`；其 9-member manifest
SHA-256=`4ab54a464fd0a9d9da8c656f6f7fc12f468e57a3ec17ec5f36161d8abc19e438`。
