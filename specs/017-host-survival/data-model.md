# 数据与状态边界

- 播放策略：standard / compatible，会话创建时固定；不在仍拥有 GPU 资源的原实例上直接改成软件模式。
- 运行期状态：现有 ready / terminal 保持；preserve-host 下新增 recovery.state=pending/ready/timeout，与旧会话终局分开；generation 在创建时捕获且不可变。不得将所有旧会话一起恢复为 ready。
- 故障归属：sessionId + loadGeneration；不能用 Surface generation 或当前页面索引代替媒体加载代。mpv 加载命令/entry/解码帧传递身份；OHCodec 故障使用 last_src，候选新帧和创建回滚不可补猜。PlayerFaultAttribution 的两个身份字段使用十进制字符串，unknown 时省略。宿主加载前身份回执尚待完成。
- 兼容记忆：属于 TV，稳定媒体 ID -> 故障类型/版本及兼容选择；Player 只接收选择和回传故障事实。不存在 Player 侧跨重启全局软解开关。
- 资源预算：现有两个硬解名额保留。新恢复路径必须另外统计正在初始化、运行、关闭和隔离的会话及工作队列；隔离资源不能因调用方返回就扣减。标准会话 6、故障前兼容 2、故障后恢复 2；常规工作 32、关闭预留 8、恢复预留 8。配置独立执行器全进程 1 个。创建票据的代和模式固定，撤销及 handle 发布共用会话表锁；超时不归还仍运行的实际任务预算。每个 NAPI 环境有独立存活身份，地址复用不能接管旧句柄或回调。宿主用例已覆盖这些边界，设备反复释放仍未验收。

- 故障历史：全进程最多 16 条 PlayerFaultInfo，包含单调 sequence、session-quarantined/process-terminal、stage/platformError 和 attribution。故障事实先记录，之后才尝试实例事件投递；不依赖已关闭的 TSFN，不持媒体 URL，不持有 Player/GPU/Surface 引用。订阅与单个 Player 生命周期分开，用户应取消不再需要的订阅。
