# Source Choice Decision View v1

正式状态：`SOURCE_CHOICE_DECISION_VIEW_READY`。控制 commit：
`fd5c3ee0fdfffe399088e2e3a4394598264239a6`。

## 结果

对 S1v2 固定的 3,000 groups/8,027 candidates 做了纯结构投影，不删组、不换 winner、不改 candidate 顺序、
code bytes 或 code SHA。train/frozen/extension 仍为 2,109/778/113 groups 和 5,739/2,041/247 candidates；
23 个任务不变。

每个 candidate 的 `provenance` 与 `source_journal_sha256` 均被结构化删除，两个字段的 removed count 都精确为
8,027；所有模型对象中的 blocked-field count=0。模型 candidate exact allowlist 只含 identity/code/code SHA 以及
decision-time `operator/step/depth`。`role/run_id_sha256/parent_id_sha256` 不再暴露给模型，单独进入 cluster
manifest，供 sealed evaluator 做 task/run 聚类统计。

train 保留 2,109 个公开 winner labels；frozen 与 extension 的 winner fields 仍分别为 0/0。S2 producer、独立
verifier 和 formal syscall audit 均未读取 frozen/extension vault。新的 aggregate-only evaluator 对 group、candidate
与 cluster manifest 使用 exact-field schema，遇到 provenance、公开 winner、额外字段、hash/order/run closure 漂移
都会 fail closed。

## 完整性

- producer x2、独立 verifier x2 均 byte-identical；view/verifier diff 均为 0 bytes；
- independent verifier 不 import producer，状态为 `INDEPENDENT_SOURCE_CHOICE_DECISION_VIEW_VERIFIED`；
- focused=`18 passed`；完整 phase tests=`704 passed, 25 warnings`；
- forbidden scientific or vault path hits=0，credential filename/content hits=0，worktree drift=0；
- 正式目录 writable files=0；GPU=0、API=0、base LLM update=0；
- 远端只读正式目录：`/research/d7/spc/yzyang4/source-choice-decision-view/fd5c3ee-v1`。

模型视图 SHA-256：

- train：`9d0ea764de59b3d0e9f2723d2663ecfb23e80c968078f0ed32425f35d31d77e3`；
- frozen：`62ffced17d045c979a29e972c16a7bfe53d7f47467a6d9728305b4b7dee84005`；
- extension：`206974ea5efd0ca3d65b3d96d9fae725d033ec66213a8dc60f9771edf5c5b050`；
- cluster manifest：`a8f328a3972708e52126157774204647698d2f8b00cc5f7ad06fd8b1d38b4035`。

关键回执 SHA-256：

- summary：`295c31a88b17e8b98b798cd2792ca54ac9ee8bdd2b93f86592f9c44c1a84da39`；
- view manifest：`5b24423079d09889e3e809cb866b9b2615e8d3023bcbf5d5ab80d588d008f820`；
- independent verification：`53b044a486520ad879224c9ae96f415cf3c01fe8a9a098258575fde698fb12b2`；
- 回传的远端 `SHA256SUMS`：`029e9356d0d16e87b274b6845ffa9738002ef368e8b4bc3cee1a68ce031c8516`。

## 主张边界与下一步

允许主张：选择性记录下恢复出的 source-choice 原料已经有一个严格、可复现、无 reconstruction-provenance 泄漏的
decision-time 模型视图；这把 0DJ 的 release blocker 真正解决，而非隐藏。

禁止主张：本轮没有训练 predictor、没有 frozen accuracy、没有 search utility 或 prospective outcome，因此不能写
listwise 方法收益或算法 novelty。下一步可以分别开展：（1）对 sanitized immutable role files 做 credential/hash
复核后通过 Git LFS 发布；（2）另立 train-only OOF baseline 协议，模型冻结后才允许一次性调用 sealed evaluator。
