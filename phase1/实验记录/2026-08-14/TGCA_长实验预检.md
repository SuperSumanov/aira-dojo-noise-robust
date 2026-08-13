# TGCA 长实验预检（13 项）

协议：`tgca_v11_train_oof_discovery_v1`。正式 launcher 必须逐项打印 PASS；任何一项失败不得开始 producer。

1. **产物/旋钮**：工作树 clean；commit、协议 JSON、预注册、producer、verifier、tests、launcher 全部复制并哈希。
2. **廉价测试**：py_compile；synthetic edge selection、control count、graph metric、fold isolation、gate literal tests 全过。
3. **输入与禁区**：命令行没有 frozen/test/held pair 参数；0812 vault 不在参数或代码常量中。
4. **分布精确**：4,263 pairs / 333 run groups / 23 tasks / 2,293 parents / 5,499 endpoints / 5 folds 精确。
5. **平衡/支持**：每 fold run/pair 计数固定；完整评测 dominant-task share 预先计算且不得按 outcome删任务。
6. **checkpoint/resume**：每 fold 原子目录、checkpoint key 与 score/edge SHA 校验；仅完整 fold 可恢复。
7. **泄漏**：每 fold fit/valid run、endpoint、raw-code SHA 交集均为 0；跨-run训练边两端都属于 outer-fit。
8. **随机/数值**：model seed 887、edge seed 20260814、bootstrap seed 20260815；float64、对称差分、finite、收敛检查。
9. **密钥**：staged filename secret count 0；高置信内容扫描 0；不读取 env/tar，0 API。
10. **wall-clock smoke**：synthetic 完整四臂与真实小规模 engineering smoke 不计算 validation accuracy；推算链小于 wall cap。
11. **功效/统计**：四臂同 support；20 次拟合；预注册的 3 个效果门、双 cluster CI、任务一致性门原样打印。
12. **真实退出码**：producer/verifier rc 在任何后续命令前立即捕获；timeout/异常不可写成科学 NO_UNLOCK。
13. **append-only/hash**：正式 root 不得已存在；全部输入逐字节 SHA 命中；final manifest 原子生成且独立核验。

资源：CPU only，`OMP/OPENBLAS/MKL/NUMEXPR_NUM_THREADS=1`；producer/verifier 各 cap 7,200 秒。无需也不得
为本实验占用 GPU。预估 25–50 分钟；中间 fold outcome 不读取、不触发早停。
