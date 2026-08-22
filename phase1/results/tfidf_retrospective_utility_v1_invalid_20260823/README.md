# TF-IDF retrospective utility V1：结构性 INVALID

结果前 commit `cd8254567d5234fef215acb40acb0b569e44516e` 已先通过 fresh-worktree 9/9 聚焦测试与
818/818 全测试；文件名/高置信凭据扫描为 0/0。随后正式 producer 在 6.71 秒处 fail-closed：冻结的
`(split, task, parent, semantics)` margin graph 并非全部连通，故没有创建 producer artifact 目录，也没有输出
任何 raw-gap、utility 或 gate aggregate。

结构-only 复算确认 796 个 parent groups 中 786 个连通、10 个各有两个分量；test 是 550 groups 中 9 个断连。
将每个图确定性分成最大连通分量后，1,482 条 pair 可零丢弃、恰好一次地归入 806 个 comparison components，
其中 test 为 559。语义合并不改变数字，且没有 mixed-semantics parent，因此不是 Draft/Improve 分组错误。

V1 永久裁决为 `V1_INVALID_STRUCTURAL_GRAPH_ASSUMPTION`，不得把 786 个连通 parent 当 complete-case 结果。
V2 只允许在尚未观察任何 utility aggregate 时，冻结“所有 pair 零丢弃、连通 comparison component 为可识别单元”
的修复；它不再声称能从断连 margins 识别整个 parent 的唯一 winner。
