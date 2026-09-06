# 六小时会话内0905结果盲摄取

用户当前授权截止UTC2026-09-07T03:53:36（香港11:53:36）。每次会话内主动调用一次，不启动后台守护。
只复用原control b20dd2682d609c0236c138c08797678cf31a2fc0及scientific5ed1988045a3fd8c365d001c87977314572383d9。
registry、scorer、first960顺序、closure要求及保护数据的不可见性均不变。

## 输入事实已核

0905十二归档/138941950bytes：与固定Drive对象流式SHA全部一致，25请求、84.66913139899998秒。
没有保存新副本/解压，不能追认原始下载时刻。原mtime的6小时时龄于UTC20:11:12满足。
原12文件可写，已仅对验证过的原inode改为owner-readonly0400；内容/大小/mtime/inode不变，原权限留在私有回执，可逆。
冻结后私有manifest SHA6b84ee91f1c0652842db57635942f8ebc85ff15c039e4041883302ef7b3582be。
不会据此开放训练或将前瞻run换成历史开发；每次重新核对这12文件及总343归档范围。

## 执行预检与停止条件

1. 新入口只改会话lease/起点/已核来源绑定；原base d0769998335115694302d50b39799e91d39fb2aabb77ddd9d59f7d7f1bf70c43，
   派生shell f7af6bbbd3d253f3b8608a38293c7e750487f2ae72571db0b2ef07b3d1d3e599，科学body与原版本相等。
2. 本地18项相关测试通过，包括过期前无文件打开、未完成调用拒重入、作用域恢复与科学body漂移；远端固定代码CPU复测再调用。
3. 起点LATEST与独立审计state均cdae57a622cfa8e83b40e93f60dbd90045b4670c4e9050bf552ef689745a25f2。
4. source文件必须保持固定hash/inode/mtime/ctime/0400；不调时间或伪造观测。发现新未知归档/sidecar/重复或漂移即停止。
5. 原6h时龄+3次观测/300秒间隔/600秒稳定跨度保持；一次最多一归档事务。
6. 每次调用后使用原snapshot-delta链单次模式：primary A/B、独立grounded A/B、hash/trace/security/readonly验收，再推进审计state。
   生产LATEST先由原runner事务校验提升；这不同于事后独立审计state，不伪称两者同一个promotion。
7. 初始监控PID必须不存活、锁可获得、原日志/干净worktree一致；不修改或重启旧monitor。
8. wrapper至多16次，命令上限2700秒；仅在剩余会话≥2700秒时允许新调用，失败/未完成输出阻止再调用。
   16次是上限而非承诺完成数，不能为赶截止跳稳定间隔或开并发事务。
9. 真正空ready观察+事务日期归因后才能说0905处理完；不能用调用次数代替归档归因。
10. 不打开保护labels/outcomes/prediction values/accuracy/utility或candidate identities；仅导出结构counts/SHA。
11. 无模型/随机抽签/效果统计，训练功效与评估配平不适用；不把结构样本增长写成方法收益。
12. 退出码第一时间保存，所有失败保留；发布前凭据扫描；私有原始输出不回显。
13. GPU/API/base更新=0；不影响12641或旧held12535，FA2/模型工程在另一条链上独立核验。
