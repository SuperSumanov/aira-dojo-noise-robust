# Independent Sibling Graph Gate v1：Post-Push 回执

日期：2026-08-29

被复验发布 commit：`9a8ab7e4ecfd9d43f006a83f5eb891468e6a4251`

fresh detached r1 已通过 package manifest 与 focused=`15 passed`，但错误地对整个 `phase1` 目录调用 pytest，误收集
`amplifier_test.py` 和 `premise_test.py` 两个命令行脚本，因而在 collection 阶段 fail-closed；没有 `COMPLETE`。该失败根
原样保留，未改代码或科学产物。

r2 只将全量测试范围修正为正式 test root `phase1/tests`，从共享远端重新 fetch 并 checkout 同一精确 commit。14 个 changed
files 和 11 个 package manifest members 全部复验；producer/verifier SHA-256 保持
`ea66df81b640c8623936c40bd2742245361c684f6d270ef53b59f4432e65fa18` /
`6f7c3a3ca782e4d18d9d67ee6954f0a6bcbbafedac0d1a134a1b1fdfa6e0c8a1`。

focused/full=`15/1573 passed`（47 warnings）；commit filename/blob credential hits=`0/0`。senior test rows 与 prospective
values 未读，GPU/API/model-fit/base-update=`0/0/0/0`。权威 post-push manifest=
`8d8865d84dfee76eeb5715e648df584dfa23efe9454878ba31d8c5d6125e840b`。因此 0IO 的人口资格正分类和全部边界不变。
