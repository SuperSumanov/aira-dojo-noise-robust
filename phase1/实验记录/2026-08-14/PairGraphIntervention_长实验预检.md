# Pair-graph intervention：运行前预检

日期：2026-08-14。协议：`pairgraph_v11_train_oof_descriptive_v1`。本轮是单 CPU 有限总体审计，
预计远低于 10 分钟；仍按长实验同等级的 13 项门执行。任何新 graph accuracy 产生前冻结本记录、producer、
independent verifier、tests 与 launcher。

1. **artifact / knobs**：四个 input SHA、四个可分离 arms、固定 gap bins、共同支持门、task bootstrap、
   三个解释门和 wall cap 全写入预注册与产物；运行 commit 写入 summary。
2. **cheap tests**：producer/verifier `py_compile`；pairgraph 与上游 heterogeneous tests 全跑。
3. **输入/禁止路径**：CLI 没有 frozen/test/held pair 参数；四个输入 basename 逐一 fail-closed 检查。
4. **分布**：OOF/pair 必须 4,263 行逐行一致；333 runs / 23 tasks / 2,293 parents / 5,499 endpoints。
5. **balance/support**：预执行只读 metadata 审计固定得到 96 task×fold cells、跨 run 组合上界 196,980；
   outcome 后仍必须满足 common sibling share>=0.80、tasks>=15、dominant task<=0.30。
6. **checkpoint/resume**：该短 CPU census 不做 checkpoint；输出只通过 `.tmp` + `os.replace` 原子提交，
   append-only root 已存在即中止。失败不得把半成品当结果。
7. **leakage**：cards 先由 OOF endpoint allowlist 限定，只保留 selected ID 的 task/graded；code/obs/
   runtime/stdout/self-report 与非 allowlist cards 保留数都必须为 0；`frozen_read=false`。
8. **RNG/numerics**：候选 pair 为确定性全枚举；唯一 RNG 是 seed=9887 的 10,000 次 task bootstrap；
   score consistency/float tolerance=1e-12，tie=0.5，gap 恰落边界进入右 bin。
9. **secrets**：staged filename 扫描和高置信内容扫描必须均为 0；结果根再次扫描。
10. **wall-clock smoke**：synthetic fixtures 覆盖跨 run 枚举与三图 transport；真实 metadata 的组合上界
    196,980，要求低于冻结的 250,000 安全上界。
11. **统计支持**：这是完整有限总体描述而非随机 pair 样本；主不确定性按 23 tasks 聚类。协议明确不把
    train-OOF 描述写成 prospective confirmation。
12. **真实返回码**：producer/verifier 的 rc 在任何后续命令前立即保存并检查；任一非零则链失败。
13. **append-only + hashes**：输入逐字节 SHA 在运行前复核；source/prereg/input/output/manifest 全保留，
    `preflight.log` 因最终完成行继续追加而明确不进入先前生成的 artifact manifest。

资源矩阵：1 CPU process，0 GPU、0 API、0 底座更新；producer cap 600 秒，verifier cap 600 秒，launcher
cap 1,500 秒。若任何预检失败，不产生科学结果。
