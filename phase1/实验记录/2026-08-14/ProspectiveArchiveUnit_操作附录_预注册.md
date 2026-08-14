# Prospective archive unit：追加式收样操作附录

日期：2026-08-14。状态：**activation 后首个新 archive 出现前冻结**。本附录只固定
`prospective_drop_intake_v1` 的操作粒度，不修改 active scorer、eligible run 定义、first-960 全序、支持门、
closure 或最终 estimand。

## 1. 触发事实仅来自文件元数据

远端 senior source 截至写入时共有 0724--0812 的日期目录。每个目录含 4--11 个 `tar.gz`，但所有目录均没有
`COMPLETE`、`DONE`、`CLOSED` 或 manifest 标记；0812 后尚无新目录。本判断只读取路径、大小与 mtime，没有列 tar
member、没有打开 checkpoint、label vault 或任何 activation 后 outcome。

因此整日期目录不是可证明闭合的事务边界。若先 intake 一个目录、之后同目录又出现迟到 archive，则重跑整目录会
与 append-only registry 中已有 source archive/physical run 重叠；忽略迟到 archive 又会造成选择性漏样。

## 2. 冻结操作规则

1. 一个正式 `drop_id` 只绑定一个 source `tar.gz`。intake 允许用重复的 `--archive-name` 显式选择安全 basename；
   生产路径固定每次恰好传一个。目录名只作来源，不决定 cohort 顺序。
2. 生产 runner 首次部署时把当时已存在的 128 个 archive 封成 baseline；此前连续 8 小时的元数据 monitor 无变化，
   且 0812 影子回放已确认其 root 全部早于 activation。baseline 只排除这些部署时已存在的路径，不能靠日期名扩张。
3. 此后首次出现的 archive 必须是 source root 下的普通非 symlink 文件；至少 6 小时未修改，且至少三次、相邻
   不少于 5 分钟的 `(path,size,mtime_ns)` 观察完全一致，才允许进入 intake。mtime 只用于稳定等待，**不得要求晚于
   activation**：上传工具可能保留旧 mtime，最终 eligibility 仍只能由 journal root time 决定。
4. intake 仍在读取前后逐 archive 重算 SHA。稳定观察、首次 SHA、intake manifest SHA 或读取后 SHA 任一不一致即
   fail closed；后续同路径 bytes 改变必须作为完整性事故记录，不能生成第二个科学 drop。
5. `drop_id` 由 source 相对路径的安全 slug 与 archive SHA 前缀确定；同一 archive SHA 只能登记一次。迟到 archive
   作为新的单 archive drop 追加，不改写既有 registry。
6. first-960 仍只按 root `generation_started_at_utc/source_sha256/run_id` 排序。上传目录、mtime、观察时间、
   archive 名和 `drop_id` 都不得进入科学排序或标签筛选。

## 3. 代码与进程边界

生产 intake/scorer/registry/accumulator 必须在同一个干净、detached、精确 commit 的独立 worktree 中运行；日常开发
分支前进不得改变该 worktree。state root 位于 repo 外，`umask=077`，label vault 不进入 Git，scorer/accumulator
命令不接受 vault 路径。每批只有 intake、固定 scorer、全 registry 重验与 provisional accumulator 全部成功后，
事务才可原子追加；失败产物不得伪装成已登记 drop。

本附录不授权读取 label/outcome，不产生方法效果结论；CPU、0 GPU、0 API、0 base-LLM update。
