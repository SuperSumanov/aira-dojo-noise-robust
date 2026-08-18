# Score-channel replay 完整数据恢复与执行前预检（2026-08-18）

状态：`PRECHECK_PASS_NO_SUBMISSION`。本报告不读取 label value、candidate replay outcome 或科学效果，
记录时真实 GPU job=0、结果行=0。`sbatch --test-only` 输出中的 11119–11122 只是调度器预测编号，绝不是已提交
作业。

## 数据门与新批准

用户接受 9 个 Kaggle 竞赛规则后，官方 `mlebench prepare` 对 9 题全部返回 rc=0；下载文件先通过官方
checksum，再生成 prepared public/private。最终覆盖 verifier 独立运行两次、receipt 逐字节一致：17/17 tasks、
320/320 candidates、0 missing，SHA-256=
`dd986c78a2f7f411ce16a1f1b757b7b8a77140aff99a36c9a311f7b81eeb8181`。第一次仅含 ventilator 的中间覆盖检查
按设计返回 rc=3，因为当时仍缺 8 题；它不是 prepare 失败，也没有被当成最终 receipt。

旧 approval `d34354dd...` 继续以 `VOID_INCOMPLETE_PREPARED_DATA_ROOT` 作废。新 receipt 绑定完整数据覆盖、
frozen replay/summary/shards、worker commit、container size/mtime、pristine grader SHA 与 data root，SHA-256=
`b107075810e5af0da084be087cfa70740cd846d198a155116a061599e3057e09`。它同时记录此前 5 个 fail-closed jobs
实际占用 20 GPU 秒，因此本次四片墙钟只允许 38,380 秒；20+38,380=38,400 秒，恰等于原批准硬上限。

## 13 项长实验预检

1. **旋钮产物验证**：approval、四份脚本和 dry-count 共同显示 cap=120s、4 shards、1 GPU/shard、
   RTX3090、API=0、base LLM update=false；不是只检查变量展开。
2. **便宜路径验证**：worker frozen commit 已有聚焦/完整测试；本轮四片 dry-count 各双跑一致，Slurm
   `test-only` 4/4 通过。最近使用同一容器的 jobs 10850/10851 在 gpu27 完成且 rc=0，排除了旧文档中已过时的
   “3090 无容器”担忧。
3. **测试查重**：本实验无训练/过采样；冻结 support audit 已验证 320/320 candidate IDs 唯一、跨 parent
   duplicate membership=0，selection/replay SHA 不变。
4. **先看分布**：17 tasks / 94 physical runs / 158 parents / 320 candidates，最大候选任务占比=0.15；正式
   analyzer 固定输出 run/task 分解，不凭首行或单一均值裁决。
5. **评估配平**：旧训练命令的 `eval-stratify/eval-len-control` 不适用；这里 primary 为 run-cluster bootstrap，
   secondary 为 task cluster，并固定 run exact sign 与 task LOTO。
6. **模型保存**：本实验不训练模型、不产生 adapter，N/A；只保存 append+fsync 的逐候选结果行和绑定 SHA。
7. **泄漏三查**：run-clean cohort、candidate/card/code SHA 和 parent membership 已冻结；label vault 在 analyzer 前
   不打开，worker 只执行 manifest code 并调用 pristine grader。
8. **RNG 复现**：本轮 replay 无 shuffle；所有抽签在结果前冻结为 selection/replay SHA，扩数据没有重排 cohort。
9. **密钥扫描**：prepare 日志在线整行脱敏，最终日志扫描通过；approval/run-root secret filename 与 credential
   content 命中均为 0。worker 不保存 raw code/stdout/stderr/grader 文本。
10. **墙钟核算**：四片为 100/85/78/57 candidates，对应 03:20:00/02:50:00/02:36:00/01:53:40；合计
    38,380 GPU 秒，加历史 20 秒恰为 38,400 秒。
11. **功效与覆盖**：结果盲 sensitivity 已确认 exact sign 门至少需 6 个 informative runs，冻结 cohort 有 94 runs；
    仍不声称 80% power，common coverage/ties 由正式 analyzer 决定。
12. **rc 先保存**：9 个 prepare rc 与两个 worker rc 均独立保存为 0；每片 Slurm 脚本先写 `worker_rc=$?`，再写
    唯一 rc 文件并以该 rc 退出。
13. **扩语料前冻结抽签**：selection/replay/orientation 均在数据结果前冻结；本次只补执行数据，不重新选 parent、
    不改 task、cap、shard 或方向。

## 预检输出

dry-count 双跑均为 done=0，todo 分别为 100/85/78/57；旧 result root 与新 root 的非空结果文件均为 0。
四份 Slurm script SHA、预算和 test-only 状态见 `preflight_summary.json`。后续只有再次运行完全相同的预检并显式
进入 `--submit` 模式后才允许产生真实 job ID；任何 SHA、数据覆盖、队列占用或 secret scan 改变都会 fail-closed。
