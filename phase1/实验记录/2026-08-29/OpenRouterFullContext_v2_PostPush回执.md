# OpenRouter Full-Context v2：Post-Push 回执

日期：2026-08-29

被复验发布 commit：`845751f05016f6093f7be3a1bfe57af811413ee3`

fresh detached worktree 只含相对 formal commit `932ef387439c1f3a27ec0ec358bc986226f81bae` 的 7 个预期发布文件；
4 个 package manifest 成员全部通过。aggregate receipt 与 independent verifier result SHA-256 分别保持
`8736be6a685e207eb39c25f1e7f7fa60f44adc0a908975fc1f7eb6e625343968` 与
`4ab25eaacdc17758c282541871ccf36d125f6c2424c68c5d1044ecd5cc7933a5`，并从发布 commit 再次精确重建。

full tests=`1551 passed, 47 warnings`；filename/blob secret hits、network calls、forbidden prospective opens 均为 0；
GPU/API/model-fit/base-update=`0/0/0/0`。因此 0IL 的结构分类与边界不变，私有 panel、身份、代码、方向和 gap 未发布。
