# G-reuse cycle information：数值A/B失败与工程重试声明

日期：2026-09-05。首个正式根：
`/research/d7/spc/yzyang4/g-reuse-cycle-information-6976358-20260905-A`。

首轮四个子进程均rc=0、stderr=0，producer A/B均产生结果，inverse-Laplacian verifier A/B也均通过各自对
producer receipt的冻结close门；但外层runner额外要求verifier两个JSON逐字节相同，故最终以RuntimeError失败关闭，
没有context或COMPLETE回执。

只看顶层状态/异常类型的诊断已暴露四次运行的顶层PASS状态，未打印metrics。随后固定诊断只比较差异形态：145个
浮点字段中10个有差异，最大绝对差`1.8189894035458565e-12`、最大相对差
`5.033757779443083e-16`；所有非浮点字段完全相同。这在结果前预检已经固定的`rel_tol=1e-8`、
`abs_tol=1e-7`之内。

允许的唯一修复是：外层runner对verifier A/B完整JSON使用同一个递归close函数；producer A/B仍须逐字节一致，
每个verifier仍须独立对producer receipt做close，producer/verifier总比较不变。输入、population、basis、图、谱/逆公式、
四个科学阈值、容差和240秒上限均不得改变。首个失败根永久保留，不计正式成功；全新源码commit和全新结果根重跑。

这是看到顶层状态后的工程重试，后续即使通过也必须在结果中披露，不能称完全盲的首次正式运行。
