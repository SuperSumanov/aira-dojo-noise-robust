# Failure history

- `formal-065d0b5-v1` 在旧 snapshot `8579d7cd...d9248` 上完成了计算，但执行期间 live intake 推进了
  `LATEST`。终态稳定门按设计失败，目录写入 `FAILED_RC=1`，没有 `COMPLETE` 和最终 manifest；该次只作
  diagnostic，不晋升、不引用其科学字段，也没有被成功目录覆盖。
- 本包来自全新 worktree 与全新输出根 `formal-065d0b5-ad0b624d-v2`。它在 5×300s 静默门之后启动，
  source/snapshot/LFS hash 重新绑定，四次计算全部从头执行，终态 `LATEST` 仍为固定 snapshot。
- formal 完成后的第一次手工 `sha256sum -c /absolute/path/SHA256SUMS` 从错误 cwd 调用，因 manifest 使用
  `./relative` 路径而报告文件不存在；它没有修改任何文件。随后 non-importing recheck 显式把每个相对路径
  解析到 formal root，24/24 payload 全部 hash 匹配。该命令错误不是 formal failure，也不作为完整性证据。
