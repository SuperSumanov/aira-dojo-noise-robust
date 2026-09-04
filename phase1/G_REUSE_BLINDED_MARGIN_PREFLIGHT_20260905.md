# G-reuse canonical endpoint-score到margin物化预检

冻结于2026-09-04 22:26 UTC，在任何真实endpoint score或效果结果前。

1. **问题**：把模型推理缩成无标签endpoint scalar后，能否不读`better/worse`确定性生成正式escrow pair margins？
2. **输入**：canonical无标签pair行与exact-support endpoint score行；pair只带原始endpoint ID和匿名cluster SHA。
3. **禁止输入**：truth orientation、grade/outcome、accuracy/utility、保护cohort结果；本轮只用合成fixture。
4. **方向**：强制`left_endpoint_id < right_endpoint_id`，pair hash为`sha256(left+NUL+right)`，margin固定left-right。
5. **同池**：score endpoint集合必须与pair endpoint并集逐项相等，不接受缺失或额外endpoint。
6. **矩阵**：每endpoint必须含五臂×三seed及TF-IDF共16个有限标量，字段不可增减。
7. **输出**：只写pair/task/parent/run SHA与margin map，按pair SHA排序；不写raw endpoint ID或truth。
8. **独立性**：producer与不导入producer的verifier各自解析、核hash、算差并逐字段比较。
9. **解释**：通过只证明物化逻辑；不证明endpoint score来自合法checkpoint，也不证明模型进程文件访问。
10. **资源**：纯stdlib、GPU/API/model fit/protected read均为0；不调用学长旧oriented evaluator。
11. **停止**：schema、重复、控制字符、非canonical、hash、support、finite或双实现任一不符即fail-closed。
