# G-reuse 匿名 prediction--truth join kernel 预检

冻结于 2026-09-04 22:43 UTC；只使用合成行，不读取或定位真实 truth vault。

1. **问题**：正式 escrow 与 pristine truth 揭盲时，能否在不写出逐行 truth 的情况下确定性连接并运行冻结统计？
2. **父协议**：固定 prediction escrow、left-minus-right margin 物化和 effect readout 三个既有 SHA。
3. **输入**：prediction 行只含四类 SHA+margins；truth 行只含同四类 SHA+`truth_sign`。
4. **同池**：两侧 `pair_sha256` 集合必须逐项相等；不允许 missing、extra 或 duplicate。
5. **簇绑定**：同一 pair 的 task/parent/run SHA 必须全部一致，不能只按 pair key 静默接受漂移。
6. **方向**：truth 只能是 ±1；margin 语义继承冻结 canonical-left-minus-right，不在 join 时翻转。
7. **顺序**：按 pair SHA canonical 排序后才交统计核；输入行顺序不产生分析自由度。
8. **双实现**：producer 使用正式 statistics；独立 verifier 自行解析/join并调用不导入 producer 的统计实现。
9. **输出**：只含输入 canonical SHA、行/任务数与聚合统计；不写 joined rows、truth signs 或 raw ID。
10. **资源/边界**：GPU/API/model fit/protected read 均为0；本文件不认证 escrow/closure，也不授权开 vault。
11. **停止**：schema、SHA、finite、support、cluster、协议或双实现任一漂移即 fail-closed；不得用敏感性结果救主门。
