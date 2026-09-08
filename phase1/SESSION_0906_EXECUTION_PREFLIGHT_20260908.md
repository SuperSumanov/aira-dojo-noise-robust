# 本次续行：0906前瞻摄取与开发来源分离

用户已批准先汇报再执行。汇报已在 `SENIOR_STRATEGY_AND_EXECUTION_20260908.md`；以下只启动原协议的有界摄取，不提交模型或候选执行。

1. 目标：让已复制的0906归档依原协议经过稳定门和独立delta核验；不是产生模型正结果。
2. 真实输入：11归档，118981762bytes，private manifest SHA `c960d1e4c59cffcb5c571f08a7d87792e89c178758bff6982bad719e9088a48b`。私有归档名/成员不回显。
3. 时龄不修改：UTC09-08T03:40:45.566210后才全部满6h；3次观测、300秒间隔、600秒稳定跨度保持。
4. 新会话调用窗口：UTC03:40:46至05:40:46。不是延长旧0905 lease；无需后台或自动任务。
5. 原科学入口不改：control `b20dd2682d609c0236c138c08797678cf31a2fc0`，原scientific runner、registry、scorer与closure规则保持。
6. 原base driver SHA `d0769998335115694302d50b39799e91d39fb2aabb77ddd9d59f7d7f1bf70c43`，run-once shell SHA `f7af6bbbd3d253f3b8608a38293c7e750487f2ae72571db0b2ef07b3d1d3e599`。新wrapper只绑定窗口/源/输出；先固定Git commit并做本地/实际Linux测试。
7. 起点LATEST `6db37288ac0fe2ca1b833ff63c3b10318cd13610c023a9d2412c194a67dfd116`；独立delta state必须相同，旧monitor PID不存活、锁可得、原日志和工作树不变。
8. 每次至多一归档事务，最多8次调用，每调用连同独立核验2700秒上限。必须留足窗口；不承诺本次摄取完11包。
9. 原snapshot-delta链先A/B、独立grounded A/B、完整hash、trace/security、只读门，再写本次post-audit；任何未完成/失败阻止下一调用。
10. 原始压缩包只做不透明hash，源文件0400、mtime/size/owner/nlink绑定，跨调用记录完整stat指纹承诺。未知新归档或config-v2 sidecar即停，不自动扩大范围。
11. 所有保护label/outcome/prediction/accuracy/utility与私有候选身份不读/不回显。新前瞻包不转训练，ADMITTED_RELEASES不修改。
12. GPU/API/model fit/agent更新均0，不释放12535、不重跑12664。成本仅单进程CPU/IO；无随机模型，seed统计不适用。
13. 原失败/原lease保留；仅在exact source、测试和秘密扫描通过后执行，运行退出码/实际时间/安全counts与SHA保存。用户可通过Git查看报告，学长分支不改。

并行主任务：明确开发数据路径及预算阻塞；只有可真实消费、独立且资格清楚的输入才进入既定4-fit。未知历史evaluator不能通过本摄取解锁。
