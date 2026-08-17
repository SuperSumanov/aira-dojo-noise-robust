# 0816 plant-pathology 结构性拒收

- 精确归档：`0816/plant-pathology-2021-fgvc8-8seeds.tar.gz`
- SHA256：`859f6ca0a54664c74ea2ae31fa005f24e846c99f764dd729bd251b3de9924776`
- 诊断收据 SHA256：`a0a8669681926d3bfa971a904e3ead3263b2f2f2fd64f64fdfbcccd79a36b59c`
- 双跑结果逐字节一致；完整测试：`362 passed in 30.49s`
- 16 个 checkpoint journals 中，8 个任务身份 cardinality=1，另 8 个=0。
- 裁决：整包结构性拒收；不得根据文件名补 task，不得只接纳其中一半。
- 安全边界：先扫描 raw journal 凭据，未读 env/live-event journal，未输出 task identity、代码、stdout 或 grade。

首次生产 intake 在 task identity 门 fail-closed，未提交 transaction、未读 outcome。该目录只冻结结构性
诊断与精确拒收绑定；不改变 score-channel estimand 或 150-run 固定门。
