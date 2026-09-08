# ForeTS 实际请求与逻辑调用成本边界（2026-09-08）

## 最终验收状态

源码2920b14ddc471942ba19972f687458d339adff62：Linux 3.11.15/pytest7.4.3/Jinja23.1.6，
69项通过（14新+55旧），8.896084904001327秒；Windows同矩阵通过，不重复计成独立科学试验。
独立新进程核69唯一case、0失败/错误/跳过、11源码等于Git blob及12输入前后hash不变。
远端/research/d7/spc/yzyang4/forets-request-r2-20260908-Uah5sBkn。
receipt SHA256 6f031733de0e2a5074c9ced68f35bcb4bb80e1a65261324172649bdcc6a6d7b3；
XML SHA256 0e72d38e1f8c08de6d0ab73c8ded42036ff4a419f125ba0ec3b10ec8a0fe26de，下载后相同。
见linux_r2.json、linux_r2_tests.xml、independent_verification_r2.json、transport_r2.json。
初轮8失败保留，没有覆盖原目录；只改测试缓存读取，不改guard或科学配置。

未部署的0004补丁，接在已有0002/0003之后；不修改学长分支，不宣称模型效果。
权威upstream仍为8b621851a87d20382feefe8c8458a7db2a1fabea。目标：防止同批次输入混杂及提取重试费用漏计。

## 已核对并修补

- 原draft/improve原地shuffle共享available_packages；在guarded批次内改为使用配置中的固定顺序、不改配置。
  非guarded路径保留upstream行为。**改变了guarded生成提示的包顺序规则，今后的对照必须两臂同样启用该契约**，
  不可把本实现与原始未guarded MCTS直接称作“只有selector不同”的公平对照。
- 在实际GenericLLM→client.query边界核对完整messages、生成kwargs及client类；首个请求作为锚，
  后续任何漂移在对应调用发送前停止。第一个请求可能已发出，不是“所有请求预渲染后才开始计费”。
- 固定请求副本保存在私有ledger，首次派发前留持久化意图；每次逻辑调用的返回用量单独留存，
  不再只依靠async_execute_op_plan_code最终返回的那份metrics。原函数返回格式未变。
- 模板/transport修改输入不能回写保存副本；credential形状命中在保存或发送前停止。
- 中断/异常成本为unknown/null，保留error类名、不回显原始异常文本，不把unknown记作0。
  以候选数×原max_llm_call_retries设置逻辑调用上限；SDK/provider内部重试未覆盖，不是美元预算证明。
- schema升至2，拒绝旧台账自动混用；生成全部结束前不执行任何候选。

## 验证

Windows实际14项新增测试通过，结合旧55项共69通过。使用真实GenericLLM、draft/improve、异步提取、
JinjaPrompt.format及ForeTS批次函数体；Jinja2引擎真实，模板/任务/后端输出人工构造，
humanize、Black格式化和部分框架初始化stub。不是实际生产模板或Dojo全栈测试。

独立Git index在tree e2c7bcd42c69b6dac00602758bf6dda4c0c93a4c上实际应用0004，
得到34424d6a137729df6f9d6e0e0fcd5b63bce57262；6文件120新增10删除。同14项从实际tree读取并通过。
测试含真实批次接线和执行前复用：3个完成请求恢复后不重发；含原输入shuffle混杂的可控复现。
人工11/17等token数字仅检查保存逻辑，不能当成本测量。

Linux首轮486ff8f7为61 passed/8 failed，12.306021220996627秒。8项均在测试helper读取Jinja源文件时
错误使用git show（独立目录不是Git repo），未走已校验source cache；并非请求guard被这些case验证通过。
失败XML linux_initial_failure.xml SHA0417f9bc84e8efae98e750a80e7945b8f00c2e1473e7804478fc03db86e3f155。
后续显式按环境读取固定缓存，不再依赖在测试收集前替换某个测试模块对象；guard/0004内容不变。
修改后的Linux复测已完成，见顶部最终回执；最多300秒CPU子进程，0 GPU/API/fit，不安装库，不改活动环境。
只传固定源文件和人工测试，源文件打包用命令级core.autocrlf=false并核对Git blob字节。

## 不支持的结论与下一步

完整search/interpreter恢复、critic HTTP费用/同步阻塞/截断、执行与analysis成本、SDK内部重试及真实资源绑定仍未解决。
client类名不认证模型权重或实际provider路由；私有请求留存也不是同UID对手防篡改或完整网络访问审计。
只能称“生成逻辑请求的输入一致性与已知返回用量留存”，不能称完整计费、完整恢复、生产就绪或正模型收益。
正式四fit仍等待独立开发原记录；本轮不读保护数据，不用新guard代替来源事实。
下一步应把这套固定输入契约写入同候选批次random/critic对照，并解决真实执行状态和资源预算，不反复重跑本轮测试。
