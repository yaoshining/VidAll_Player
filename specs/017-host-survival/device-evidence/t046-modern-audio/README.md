# T046 现代音频打断修复

## 问题与实现

API24平板连续出现SYSTEM_PAUSE_MISSING；当前核心API>=20只注册WriteData回调，系统PAUSE不能进入mpv状态机。新增0009补丁，保留现代WriteData接口并注册现代Interrupt；两种API共用不可复用token、在途引用及退休恢复代检查。PAUSE/STOP转成原有暂停请求，RESUME不自动播放；现代路径也按文件释放AO，避免旧音频回调影响下一条视频。

Interrupt注册自API20提供，因此只在版本>=20时动态查找；符号缺失或任一注册失败即初始化失败，由既有uninit清理登记。新ELF无OH_AudioStreamBuilder_SetRendererInterruptCallback强导入，旧API15–19沿用原回调注册。没有修改FFmpeg、消费者TV或零拷贝解码配置。

独立内录页原本用拒绝estimated的读数函数检查durationMs；生产契约明确该字段是估算。现在仅时长允许estimated，保留30秒素材一致性门槛；位置依然拒绝估算，所有数字拒绝非有限值。未把估算字段允许扩大到硬件资格。

## 已完成证据

- duration-red.log：真实页面run在estimated时长上失败；完整run及位置估算、不可用、NaN、错误时长负例变绿。
- modern-red.log：实际注册函数在API20未注册中断/未按文件隔离；symbol-red.log覆盖现代符号缺失。
- API20/24实际注册函数的PAUSE、RESUME不自动播、手动恢复、迟到token、新实例、两种注册失败、现代符号缺失及退休代拒绝通过；原旧回调并发生命周期回归通过。
- 五组音频生产函数回归、六套验收工具回归和94项完整宿主门禁通过，分别见三个summary。宿主替身不是实机焦点证据。
- 从封存基线重新核验并生成完整输入，重建mpv与libplacebo、静态门禁通过。新mpv SHA256为b81a0f2d54cc01defcc26849cb0e65404936528fc16f57ddf08b847591627086。FFmpeg六库及固定libc++均未改变。
- 本地MacBook Pro构建固定ARM64九库HAR通过，哈希见local-har.json；这是本地预验证，尚不作为最终CI交付。默认目标首次构建带SDK运行库，不用于这份交付；随后按deveco26模块目标重建并核验固定库。

## 未完成

本轮启动了既有API19 TV模拟器，当前本地HAR的独立消费九库一致；PID2390完成坏片失败后正常播放、暂停/手动恢复、seek、关闭重开，两个首帧且后续零错误，见api19-local-software.json及事件日志。这是software/no路径，不是硬解或听声验收。iMac CI完整HAR已完成并核验，见../imac-delivery-62e4e3f.json。现代系统焦点复验、实际系统内录音轨导出与分析仍待完成。T045旧包的失败和T044旧包行为证据不覆盖新核心。API24不替代API19 TV正式文件入口；不创建PR、不标音频通过。

## CI 交付与上传阻塞

源提交62e4e3f8d9648f60713e03d182b2e0f45d923118的iMac构建43237406546及Ubuntu回归43237652695均成功。实际HAR运行器为yaoshiningdeiMac，非云端Mac；原始HAR SHA256为a419c1545680d48ab22983472a8c8ca3311a58bf5904cebdabfde2394e40b704。九库与绑定输入核对，FFmpeg六库和固定libc++不变。

使用该原始HAR重新构建本地平板消费包1.0.48，逐库与CI原HAR一致。11月12日启动内置浏览器上传，文件选择接口长时间未完成并最终报“No node found for given backend id”。11月13日09:13重新检查：登录有效，免费余额360分钟，设备/预约列表为空，应用列表最新仍1.0.45。因此1.0.48未确认上传、未执行，未分配设备消耗额度；保留页面等待手动上传。详见upload-blocked.jpg及tablet-preparation.json。

## CI 原包 API19 模拟器复验

11月13日09:15，CI原HAR消费包九库逐一一致，PID2334完成坏片错误后返回、正常首帧、暂停稳定/手动恢复、seek至20秒并继续前进、释放重开第二会话，最终两个首帧/后续零错误，见api19-ci-software.json及事件日志。实际backend=software、decoder=no；不代表系统音频焦点、真实声音、硬解或API19 TV正式文件入口通过。此前11月12日仅取得安装启动成功，未取得完整日志；本次才补齐CI原包软件回归证据。
