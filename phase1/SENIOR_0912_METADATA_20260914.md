# 0912 新包：已到达，尚未纳入训练或确认语料

观察时间：2026-09-13 21:59–22:06 UTC（09-14 HK）。这是结构事实，不是模型效果。

新日期子目录两次查询一致，发现一个压缩包。只读元数据记录在远端
`/research/d7/spc/yzyang4/senior-0912-metadata-20260914-s1xb8y5z`，私有清单 SHA256
`918ff8f1018309a232e5f937c718ba8fcb9c22c5c0a09027877089a567260239`。

隔离根为 `/research/d7/spc/yzyang4/senior-quarantine-0912-20260914`。
下载共 11,844,727 bytes，manifest SHA256
`d7297d76a39a1e141ff2b63f1f22c45148b9d5b8075fede8da0716b13ea7822c`。
未解压；配置内容在远端通过 credential-shape 检查后才解析。四份配置、四个配置父路径、四个 journal 文件头条目及四个环境文件头条目；没有打开 journal、环境或程序正文。
四份配置均记录 `git_commit_id=61459c0a1248900079dafed7c505afa87e476b40`、`num_children=2`。
四个配置目录不等于四个合格 physical runs，更不等于新增独立训练样本或 scaling 证据。

全根索引相对旧清单仍有一处非日期目录“同 ID、不同名称”，不是新日期包不稳定。没有擅自重置旧索引、更新 LATEST、混入当前 42–45 seed 对照或打开保护 cohort。
新日期子目录的独立隔离，不等于该全根问题已经解决。
学长分支最后核验 head 仍为 `be9335348b569086ef9b0af36a15b13e61fec45c`；未改动其分支。
