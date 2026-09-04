# G-reuse label-blind prediction escrow验收预检

冻结于2026-09-04 22:22 UTC，在任何新模型效果或保护结果读数前。

1. **问题**：全部15个checkpoint锁定后，能否在不向模型进程暴露truth orientation的情况下生成同池margin escrow？
2. **输入**：模型进程只允许读取canonical无标签pair manifest、Cards和锁定checkpoint；validator只读四个escrow产物。
3. **禁止输入**：模型进程不得读oriented pair、label/outcome vault、accuracy/utility；本轮不运行模型或读任何真实预测。
4. **行契约**：每pair仅四个匿名cluster SHA与15个seeded margins加一个TF-IDF margin；禁止原始身份和truth字段。
5. **checkpoint门**：五臂×三seed恰好15个final checkpoint；逐个绑定checkpoint/training manifest/config SHA和final step。
6. **同池门**：margin字段必须完整、有限、pair唯一；summary的pair/task计数与JSONL重算一致。
7. **访问门**：access receipt绑定blinded-pair/Cards/checkpoint manifest，声明label/outcome/forbidden opens均为0；只是自证。
8. **文件门**：四角色各一次，拒绝额外/缺失角色、路径逃逸、symlink、hardlink、大小/hash漂移、重复JSON key和凭据形状。
9. **解释边界**：通过只叫hash-bound escrow；不证明OS级文件访问、不证明checkpoint训练合法，也不授权与truth连接。
10. **复现与资源**：validator纯CPU/stdlib；GPU/API/model fit/protected read均为0；合成包测试正反例。
11. **停止条件**：任一schema/hash/身份/finite/完整性/访问声明不符即fail-closed；不得从旧accuracy输出反推margin补包。
