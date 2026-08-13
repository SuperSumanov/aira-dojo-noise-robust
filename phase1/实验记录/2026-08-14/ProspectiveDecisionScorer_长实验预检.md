# Prospective decision scorer freeze：长实验 13 项预检

日期：2026-08-14。协议：`prospective_decision_v1`。本文件与 launcher 必须在正式 scorer 产物出现前
提交；正式结果只允许写入按 commit 命名的 append-only 目录。

1. **旋钮与产物**：两臂、特征、LR 参数、seed、输入 SHA、667-run denylist、blind schema、first-240
   cohort 与确认门已写入 `ProspectiveDecisionConfirmation_预注册.md`。输出固定为 NPZ、train reference、
   denylist、producer summary、独立 verifier 和 activation receipt。
2. **cheap tests**：producer/verifier `py_compile`；fixed scorer、heterogeneous OOF、pairgraph 三组 tests 全跑。
3. **入口/合同**：producer 的 `build/activate/score --help` 与 verifier help 落盘；build 输入路径出现
   frozen/test/held 即 fail closed；score 只接 strict code-only manifest。
4. **数据分布**：正式输入必须精确为 4,263 train pairs、333 train runs、23 tasks、2,293 parents、5,499
   endpoints；完整 run map 必须恰有 667 个 pre-cutoff runs。
5. **平衡/前瞻样本规则**：本轮只冻结模型，不读取未来 outcome。未来确认固定 first 240 fresh runs，至少
   15 tasks、150 个有 finite decision 的 runs、1,500 sibling pairs、dominant task <=25%，否则 insufficient。
6. **checkpoint/resume**：预估单次 CPU refit 远低于 1 小时；因此无需中间模型 checkpoint。结果目录禁止
   覆盖，所有文件原子写；中断只产生未激活 staging，不能被 scorer 使用。receipt 仅在 verifier rc=0 后生成。
7. **泄漏**：训练 loader 只保留 code/task/run/lineage，label 与执行后字段保留数为 0；不接受 frozen/test/
   held 路径。未来 score 入口的 JSON schema 不能包含 grade/score/runtime/stdout/obs 等字段。
8. **RNG/数值**：seed=887；两臂均对称加入正负 pair difference、无 intercept；所有数组 finite；NPZ
   `allow_pickle=false`；训练分数与反序列化分数最大绝对差 <=1e-12。
9. **密钥**：提交前执行 staged filename 扫描与高置信内容扫描；正式 launcher 对相关源/协议再扫描。0 API，
   不读取远端 `.env` 中的值。
10. **墙钟 smoke**：远端完整测试必须包含真实 sklearn/scipy 的 fit→NPZ→load→score round-trip；正式 build
    wall cap 3,600 秒，producer 与独立 refit 各由 `timeout` 约束。
11. **功效/停止**：模型冻结不产生科学显著性结论。未来确认不按 outcome 停止，只取 first 240；达到前
    monitor 只能看标签盲计数。按 v11 的 pair/run 密度仅作资源规划，不作为改变 240 的依据。
12. **真实 rc**：producer、verifier、activate 的 rc 在各命令结束后立即保存并检查，不能被后续 `tee`、hash
    或 archive 命令覆盖。
13. **append-only + hashes**：正式开始前重算全部五个输入 SHA；source snapshot、命令、软件版本、模型数组、
    reference scores、denylist、summary、verify 和 receipt 全入 manifest。任何 SHA/数量/round-trip/refit 失败均
    fail closed，禁止生成 active receipt。

资源上限：1 个 CPU 进程，0 GPU、0 API、0 LLM 权重更新；producer/verifier 各 1 小时 cap。QOS GPU 配额不
占用。正式运行前预计总墙钟 1--4 分钟；若超过 10 分钟先诊断 I/O，不扩大资源或悄悄换输入。
