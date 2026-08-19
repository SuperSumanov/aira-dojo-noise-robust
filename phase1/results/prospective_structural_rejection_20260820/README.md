# 0818 Multi-modal Gesture archive 结构性拒收

- 精确归档：`0818/multi-modal-gesture-recognition-8seeds.tar.gz`
- SHA256：`300e602a694075d05b1634d0126a660b0c2f44508cb7ae618732b95f39843d74`
- 诊断收据 SHA256：`a5c2a0d832ef6923664c6caeffde71d5f3950fe2fd2870edc942bc54f4ca6f93`
- 独立双跑逐字节一致；4 个 checkpoint journals 的 task identity cardinality 均为 0。
- 裁决：整包结构性拒收；不得根据文件名补 task，不得接纳其中任何 seed。
- 安全边界：先扫描 raw journal 凭据，未读 env/live-event journal，未输出 task identity、代码、stdout、grade 或 metric。

生产 intake 在 task identity 门 fail-closed，未提交该 transaction、未读 outcome。精确拒收登记后，监控器可以继续处理同批后续归档；该扩展不能回填任何已冻结实验。

## 0818 批次完成状态

同批 8 个新归档最终为 7 个合法 transaction、1 个上述结构拒收。相对 0817 完成快照，outcome-blind inventory 增加 26 eligible physical runs、2 tasks、1,219 endpoints 与 257 structural sibling pairs；累计为 42 transactions、223 eligible runs、25 tasks、5,643 endpoints、1,473 pairs。

独立 verifier 不 import 生产 accumulator，从 42 份已登记 blind manifest 重建 sibling 组合；双跑逐字节一致，得到 222 个 finite-decision runs、1,473 pairs，所有八项 accumulator 交叉核验均通过。完整收据 SHA256 为 `af494085faded657d3486f75c6b7ce7b39ae25d00e69a7d5cd405a2a769894b7`，两份文件访问 trace 的禁读路径命中均为 0。依赖齐全的远端 clean worktree 全套测试为 `435 passed in 39.77s`。

旧 first-960 结构门中，任务数、finite-decision run 数与最大任务占比三项已经通过；pair 数仍为 `1473 < 1500`，只差 27。因此 `vault_open_allowed=false`，不得提前读 label、outcome 或 scorer prediction。6 小时稳定窗监控继续运行，等待未来 append-only 归档。
