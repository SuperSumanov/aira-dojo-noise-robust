# Task-balance guard forward audit：formal receipt

本目录封存 source commit `76bdaad398da675aa62614260d63a019594f172c` 的 fresh detached Linux formal。
它从仓库结构 artifacts 重建 `7cda→8579` forward result，不访问远端 prospective state、truth、prediction values 或 raw
archives。

- focused：`15 passed in 0.22s`；
- full：`1080 passed, 47 warnings in 73.13s`；
- result inner manifest：6/6 OK；
- producer：`PYTHONHASHSEED=0/1` 两份逐字节相同，均等于 committed `forward_validation.json`；
- independent verifier：两份逐字节相同，均等于 committed `independent_verification.json`；
- worktree 执行前后 clean；
- formal `SHA256SUMS` 文件自身 SHA-256：
  `688f8b4fa5a8a463ff6fbd20ff6402bce42e63a984750cb24789a0d87eb45721`。

formal 保留三次未接纳尝试：过强 byte-prefix invariant、runner 正则模式冲突，以及 Python 3.11/3.13 普通 float sum 的末位
差异。第三项通过将 HHI/TV 求和改为 `math.fsum` 真正修复；没有放宽逐字节比较。详见 `formal_failures.json`。

确认结论仍为：frozen debt accounting 精确，657→645（delta=-12），但 25% cap 未通过，且 debt 清零前新增 27 个
OSIC pairs，所以即时 route-away action 明确未遵守。HHI/TV 下降只作 descriptive secondary，不能挽救失败 gate。
