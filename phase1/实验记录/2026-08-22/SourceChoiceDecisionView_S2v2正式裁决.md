# SourceChoiceDecisionView S2v2：正式裁决

日期：2026-08-22。控制 commit：`3ceb99f8030fb196d2abc388e277b11dbd1bc571`。正式状态：
`SOURCE_CHOICE_DECISION_VIEW_V2_READY`。

## 裁决

0DL 发现的 operator 大小写 provenance proxy 已按结果前冻结的唯一 diff 修复。全 3,000 groups / 8,027
candidates 中，raw train/frozen/extension 的 697/192/10 个小写 `improve` 均规范化为 `Improve`；输出只含
`Draft/Improve`，小写或未知值=0。未删除 899 个 journal-recovered candidates，也未改 group/candidate identity、
winner、candidate SHA 顺序、完整 code bytes、step/depth、split 或 cluster metadata。

显式 `provenance/source_journal_sha256` 各删除 8,027 次，model blocked fields=0；train winner fields=2,109，
frozen/extension=0/0，sealed vault 路径未读。v2 train/frozen/extension/cluster SHA 分别为
`e5ca6dc94f59d54fe31d4b1c4e796deef0006f489fd76a05663410d4911aa6e1`、
`2e8371c1890bee9c7a33cb04238f94aa130e5114b307a233e21ca5d1af2152df`、
`2a6d7c4bf5157e00e5fe59dd6100db23bb7771bfce32f55b93573d1b5d4fdd0b`、
`a8f328a3972708e52126157774204647698d2f8b00cc5f7ad06fd8b1d38b4035`。

## 复核

producer×2 与不 import producer 的 verifier×2 均逐字节一致；focused=`20 passed in 0.23s`，完整 phase1
tests=`706 passed, 25 warnings in 54.92s`。repro diff、stderr、forbidden scientific/vault path、credential
filename/content、worktree drift 和 writable formal files 均为 0。正式只读目录：
`/research/d7/spc/yzyang4/source-choice-decision-view/3ceb99f-v2`。

## 边界与下一步

本轮只证明 model-view integrity，不是 predictor 或搜索方法正结果。S2 v1 继续封锁，不能与 v2 混用。允许以 v2
train SHA 另立 task-LOTO 主结果、physical-run-grouped OOF 次结果的 train-only baseline；模型族与选择门冻结前
继续不读 frozen/extension vault。v2 可在新 immutable Git LFS 目录发布，不能覆盖 v1 文件。
