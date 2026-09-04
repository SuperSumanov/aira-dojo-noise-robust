# G-reuse task-CI异方差Monte Carlo校准

结果前commit为`adeb668dbb80a4d0addc133220b7e2e92f27df11`；协议在正式读数前固定。唯一输入是
既有公开结构回执中28个匿名任务的`local_pairs`计数，输入SHA-256为
`c9f17ba4e7354aea19288f3ef58f2a8f25f979f962e0872bbda5e01ce1312bfe`。没有读取label、prediction、
accuracy、utility、任务身份或任何保护cohort内容。

远端正式根为`/research/d7/spc/yzyang4/g-reuse-power-mc/formal-adeb668-v1`；git archive SHA-256为
`98a9f66299d700951e229c6225c21c703fed8948d75203dc05ede14926b98a8e`。Linux测试为6 passed，stderr空。
producer A/B逐字节相同，SHA-256为
`668c1e5a36c73ad3c7ca057d7690470c014557a02534190ca0184d5a4a1a9c1b`；两个独立验证回执也逐字节相同，
SHA-256为`e0044b8ff8b646941ed7f770f64e8a5c79a997d1d294b24a11499ceae4866463`。
Windows工作副本会被Git配置转换为CRLF，不能拿其物理字节冒充协议输入；从上述exact-commit archive导出的LF字节
在Windows再次独立复验，回执仍为同一`e0044...6463`，因此该差异被定位为checkout换行而非结果漂移。

每场景两次各250,000 trials。Monte Carlo的optimistic/reference/stress功效均值分别为
`0.989412/0.636072/0.27466`。两次重复差与Wilson精度门全部通过；但reference/stress相对0L30解析值的
绝对差为`0.022049063114336187/0.023708686008313717`，超过冻结1个百分点门，故总状态必须为
`all_gates_pass=false`。方向是解析近似低估功效，而不是高估：reference由61.40%校准为约63.61%，stress由
25.10%校准为约27.47%。optimistic差0.66个百分点，通过该门。

因此0L30的三个解析数字降级为近似，设计判断不变：在reference情景下，+2pp只让**CI下界>0**约有64%功效，
仍明显低于80%。而主效果协议还包括观测点差≥+2pp、三seed同向及其他比较门，本模拟没有给overall core power，
也不是critic效果、accuracy或scaling结果。GPU jobs/API/model fit/protected read均为0。
