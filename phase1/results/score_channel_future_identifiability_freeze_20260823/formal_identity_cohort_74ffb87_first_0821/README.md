# First 0821 append-only future-cohort receipt

状态：`PASS_COLLECTING_TRUTH_UNREAD`。固定 commit `74ffb87cb39e90062db6a4ace4e13cf1a12041f2`，协议
SHA-256=`54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d`。

第一批稳定事务到达后，formal identity cohort 纳入 ranzcr 与 tgs 两个完整 archive，共 8 个 unique physical runs、
2 tasks，remaining=292；前一份 0-run cohort 的 archive/run 前缀精确存活。状态仍是 collecting，未打开 tar payload、
blind code、label vault、score/outcome，未计算 truth，也不授权 replay。

成功 run 的 producer×2、独立 verifier×2 逐字节一致；focused=11/11，完整 phase tests=766/766；forbidden-open、
文件名凭据扫描、内容凭据扫描均为 0，且验证前后 production state SHA 不变。远端不可写结果包与本目录下载件的关键
哈希见 `formal_receipt.json`、`summary.json`、`verification.json` 和 `remote_SHA256SUMS`。

第一次 wrapper 在 producer 读取前一 cohort 时以 rc=2 失败：传入了 formal 包装目录，而实际 append-only 输入位于其
`producer_a/` 子目录。测试已全过，但没有 producer output，也没有 truth 读取；失败目录原样保留。失败后 tgs 事务
按既有 monitor 自然追加，使 retry 的 transaction/observation SHA 从一笔前进到两笔。retry 启动前重新绑定两笔状态，
只修正 previous-dir 层级并换新隔离 worktree 名；commit、协议、排序、样本规则和门槛均未改变。
