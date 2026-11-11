# 数据与状态边界

- 播放策略：standard / compatible，会话创建时固定；不在仍拥有 GPU 资源的原实例上直接改成软件模式。
- 运行期状态：现有 ready / terminal 保持；preserve-host 下新增 recovery.state=pending/ready/timeout，与旧会话终局分开；generation 在创建时捕获且不可变。不得将所有旧会话一起恢复为 ready。
- 故障归属：sessionId + loadGeneration；不能用 Surface generation 或当前页面索引代替媒体加载代。底层 owner_tag 未完成注册映射时归属为 unknown。
- 兼容记忆：属于 TV，稳定媒体 ID -> 故障类型/版本及兼容选择；Player 只接收选择和回传故障事实。不存在 Player 侧跨重启全局软解开关。
- 资源预算：现有两个硬解名额保留。新恢复路径必须另外统计正在初始化、运行、关闭和隔离的会话及工作队列；隔离资源不能因调用方返回就扣减。标准会话 6、兼容会话 2；常规工作 32、关闭预留 8、恢复预留 8。创建在途任务和跨 NAPI 环境归属仍待审查，设备反复释放仍未验收。
