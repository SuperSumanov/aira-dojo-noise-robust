# 固定历史程序的只读字节包（不运行、不含旧标签）

2026-09-07。固定原84run/24archive/3547canonical节点，不按旧metric、buggy、exit或实际成功筛选。
canonical投影25e4fc1cbfbb2bb97c4ab3e0550c221cd2ab591fcb0157b55c43663f8eb651ca已经A/B和独立pair计数通过。
实际3447非空程序、1579对distinct sibling、0缺父；这里只把代码保留为将来完整执行器可消费的原始UTF8字节。
空/None/仅空白源也保留在manifest中，不自动转成可训练标签；不择优或只保留语法通过程序。

每个run只读旧ledger已固定的checkpoint/journal.jsonl；精确成员、凭据扫描、归档前后hash/stat、原5输入SHA。
兩遍原member读取各自投影，必须与已完成的role/canonical节点逐条相等；第一遍原code写private文件，第二遍逐字节复核。
程序存成opaque run hash/step文件，不改代码、不导出本地/Git；UTF8 bytes SHA与code_bytes全部对齐原投影。
仅ast.parse和compile-to-code-object（不执行）检查语法，失败只记录类型/hash，不输出source文本。
AST两接口一致不冒称独立解析器；AST可接受但code-object compile失败的代码原样保留、分别报告。
原code=None与空字符串分别在manifest标记；全部节点、parents、recorded commit、component/完整timeout绑定，不含旧结果值。

CPU1/900秒、原日志累计3GiB/member256MiB、新code总bytes≤128MiB、零GPU/API/model-fit。
所有代码mode0400，private父目录0700，拒绝符号链接/重复路径/未知节点/源漂移；新输出，不覆盖旧失败。
访问trace只读已固定旧历史范围，无first960/Target300/522；源commit、helper、输入、归档、member/代码/manifest SHA留证。
语法可解析不是安全性或可执行性证明；未证明外部模型cache、数据路径和依赖齐备，尚不提交候选执行。
新包不是训练release，不恢复旧分数、不改变ADMITTED_RELEASES，不代替独立train/dev/最终确认门。
