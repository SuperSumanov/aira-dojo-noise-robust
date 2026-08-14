# Prospective production runner：长任务预检

日期：2026-08-14。对象：单 archive、追加式、标签盲 first-960 收样。这里的“长任务”是 8 小时 CPU monitor；
每次事务 0 GPU、0 API，不修改底座 LLM。

1. **方向**：唯一主线仍是 run-clean、decision-local benchmark 与 first-960 prospective confirmation；不恢复
   HCE、多保真、probe 或已关门的 selective/Qwen E1-Q。
2. **代码身份**：生产只允许 detached、exact-clean、完整 40 位 commit；日常开发分支前进不改变生产 worktree。
3. **输入**：首次部署前后两份 128-archive 元数据 snapshot 必须逐字一致；之后一 archive 一 drop。
4. **选择与 estimand**：生产期间不计算 outcome metric；first-960 仍只由 root time/source SHA/run ID 全序决定。
5. **稳定门**：新路径至少 6 小时未改、三次观察、相邻至少 300 秒、总稳定跨度至少 600 秒；mtime 不作为
   activation eligibility。
6. **安全**：`umask=077`；不读取/extract `env_variables.json`；journal 先 credential scan；state 不进 Git。
7. **泄漏**：固定 activation receipt、667-run denylist、16,012 endpoint ID + exact-code SHA denylist逐层复核。
8. **原子性**：intake、固定 scorer、全 score registry verifier、accumulator 全部成功后才更新 `LATEST`；输出拒绝覆盖。
9. **独立审计**：score-drop、score-registry 和 accumulator 均要求 `strace`；出现 label vault、frozen、first960 或
   D_test 路径即失败。
10. **复现**：保存精确 argv/rc、代码 commit/source SHA、archive/intake/score/registry SHA、递归 `SHA256SUMS`。
11. **资源**：CPU only；GPU=0；API=0；base-LLM update=0；每轮最多处理一个 archive。
12. **失败语义**：任何非零 rc 立即停止 monitor；未进入 `LATEST` 的目录只能叫 recovery artifact，不是科学 drop。
13. **恢复**：每个成功批次是不可变 snapshot；监控重启从 `LATEST` 和 observation ledger 继续，closure 前 cohort
    仍为 provisional，不读标签。
