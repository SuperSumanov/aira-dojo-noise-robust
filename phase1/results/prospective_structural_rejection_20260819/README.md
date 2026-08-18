# 0817 LMSYS archive 结构性拒收

- 精确归档：`0817/lmsys-chatbot-arena-8seeds.tar.gz`
- SHA256：`c73582b32c98cb2ba2731dd867515a8624163998a3b3335a0f21e846ce4a3ffe`
- 诊断收据 SHA256：`2de964ea8bb1d49a084ccfd97f65f408dfd0556499d911dc5cf36a446a321ee1`
- 双跑结果逐字节一致；8 个 checkpoint journals 的 task identity cardinality 均为 0。
- 裁决：整包结构性拒收；不得根据文件名补 task，不得接纳其中任何 seed。
- 安全边界：先扫描 raw journal 凭据，未读 env/live-event journal，未输出 task identity、代码、stdout、grade 或 metric。

生产 intake 在 task identity 门 fail-closed，未提交该 transaction、未读 outcome。新 registry 与 clean commit
通过远端完整 `386 passed in 31.74s` 后续跑；0817 其余 7 个合法 archive 全部独立提交，标称 52 runs，最终为
35 transactions。当前 outcome-blind inventory 有 197 eligible physical runs、23 tasks、4,424 endpoints 与
1,216 structural sibling pairs；monitor 继续观察后续稳定 archive，但这些数据不能回填任何已冻结实验。
