# Selective execution v11：13 项运行前预检

协议：`selective_execution_v11_retrospective_discovery_v1`。这是零 GPU、零 API 的 CPU 二次分析；仍按长
实验标准 fail closed，且任何 smoke 不计算 accuracy、risk 或 gate。

1. **artifact/knobs**：记录 git commit、producer/verifier source hash、input hash、seed、q、arms、输出根；
   worktree 必须干净。
2. **cheap tests**：producer/verifier `py_compile`、定向 pytest、两份 `--help` 都必须 rc=0。
3. **forbidden inputs**：CLI 只有一个固定 OOF CSV 与 output；filename guard 禁止 frozen/test/held/first960、
   cards、stdout、runtime、self-report 与 external-score 输入。
4. **distribution**：独立重算 4,263 rows / 2,293 parents，以及 exact-two 1,520 parents / 294 runs /
   23 tasks、fold counts `[285,215,222,373,425]`。
5. **balance**：dominant task 336/1,520；20% task quota 总和 295；只允许标签不可见结构数进入 preflight。
6. **resume/overwrite**：正式 output root 若已存在立即失败；staging 写完、verifier 通过后才原子提升。
7. **leakage**：每 parent 唯一 fold/run/task；policy selection 不读取 gap、better identity 或 `*_hit`；记录
   `frozen_or_first960_read=false`。
8. **RNG/numerics**：SHA256 tie/random；bootstrap seeds 20260814/20260815；所有 score/gap finite，gap>0。
9. **secrets**：staged filename scan 与 high-confidence content scan 均须为 0；输入不含环境文件。
10. **wall-clock smoke**：合成 fixture 只检查 schema、selection support、control identities 和 verifier；禁止打印
    科学 accuracy。按两份实现×10,000 bootstrap 外推，正式 cap=1,200 秒。
11. **power/utility**：primary 至少 228 selected、100 runs、20 tasks，双聚类 CI 与成本/retention 门已冻结；
    不是小样本 smoke。
12. **true rc**：producer 与 verifier rc 在任何后续命令前立即捕获；任一非零不创建完成标记。
13. **append-only hashes**：逐项重算 input/source/result hashes；结果目录拒绝覆盖；结束后生成 manifest，再做
    独立全文件 hash 验证。

任一项失败则不运行 formal producer；producer 成功而 verifier 失败时状态为 `INVALID`，不得解释 producer
数字。最终结果无论正负都保留，不以新参数覆盖。
