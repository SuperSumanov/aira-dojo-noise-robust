# Failure history

1. `formal-f9c6de2-v1` 在用户要求暂停时被精确终止；目录无 `COMPLETE`、无 producer JSON，随后写入
   `INTERRUPTED_NO_RESULT.txt`，SHA-256=`47a68d7129f4d9ae80ef2d10e61b7c7638e46fcfb7869c497db37e23807ddec5`。
   它不是结果，也不得复用。
2. 第一次外层 independent recheck 在比较 manifest 路径时没有把 `./file` 与 `file` 规范化为同一相对路径，因而在
   任何科学计数断言前停止。失败目录保留 `FAILURE`、无 `COMPLETE`。修正仅规范化 manifest 路径拼写，随后在全新
   `recheck-f9c6de2-v2b` 目录重跑并通过；未修改正式目录或科学代码。
