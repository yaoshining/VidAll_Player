# 实施计划与安全边界

用户已确定 R3：全局故障后仍需播放；本次运行可暂用兼容路径，跨重启仅保留问题视频的选择，其他视频重新优先硬解。不得把“删除 _Exit”或“停止 MPV 等重启”作为完整修复。现有终局仅直接拦截 OHCodec interop，不能未经验证将其解释为整个 mpv 软件路径均不可恢复。

1. 原样编译当前 process_runtime 与既有测试，复现 deadline 的退出码和时间；核对原始 HAR 的九库与架构。
2. 区分三类生产入口：未启用 owner 隔离或 client_api 不存在的 owner_fault；与全局关闸并发的 Vulkan 创建收尾；正常受保护实例的局部故障。检查派生源码与生产编译输入一致，不把诊断宏分支算作发布路径。
3. 先验证恢复路径可行性，再补完整红测：非退出策略在多倍旧期限后仍有 UI/调用方心跳；终局事件只报告一次，旧代排队及迟到回调关闭；所有在途/排队请求有界返回；终局后硬解创建仍拒绝，只有通过恢复能力校验的新代软件会话可启动；重复失败/上限/安全降级。
4. 增加显式策略的 ArkTS→NAPI→native 传递及配置冲突检测。为主 UI 提供确定的错误/不可用状态。隔离未归还的资源，不重置进程锁存。关闭安全门与线程/队列/实例总上限共同实现，不能仅增大 deadline。
5. 回归尺寸、旋转、完成通知与音频合同；独立消费者覆盖正常、打断/手动恢复、切集、退出重开、坏片返回、新片播放与连续故障。错误注入与真实平台故障分别标明。
6. 先本地验证，再 iMac CI 构建完整 HAR；准确说明 ARM64 支持边界及 x86_64 的缺失能力。交给 VidAll_TV 从 API 19 TV 正式入口验收，未获得记录前保持待验。

软件恢复的可行性门槛：新 mpv 实例固定 hwdec=no、gpu-hwdec-interop=no、vo=libmpv、MPV_RENDER_API_TYPE_SW，不探测或升级 EGL/Vulkan；使用新 Surface/回调代，旧代永久保留规则不变。必须证实旧音频停止且不与新片重叠、旧代不再控制音频焦点、旧代不会卡住共享工作池、新代能够正常释放并反复重建。不能仅凭源码调用图通过此门槛，也不能把当前“软解 + Vulkan”的上限回退当作该路径证据。

若上述门槛失败，再评估独立后端；AVPlayer 的格式/轨道/字幕/网络能力差异须显式记录，不能用其支持的单个 MP4 替代完整 MPV 兼容性。API 19 TV 的普通应用子进程受官方设备类型限制，不以平板成功作为 TV 支持结论。

宪章初步检查：不新增宿主退出权限、不绕过原生所有权安全门、不在 UI 执行同步等待、不混入 FFmpeg 项目改动。平台进程隔离能力尚未验证，本方案不承诺以 API 19 不支持的应用子进程解决问题。资源上限数值及跨 NAPI 环境的归属/计数设计须在实现前明确，不能把当前两个 OHCodec 名额当成所有软件会话和 FFmpeg 残留的总上限。

## 恢复策略与记录范围

先以测试表达：新视频默认硬解；局部可隔离失败不影响其他视频硬解；真正全局终局后本进程保持硬解禁令并安全启用兼容路径；重启后问题视频走兼容，其他视频仍硬解；另一个视频独立失败时按相同流程处理。会话临时回退不得写成所有后续视频各自的失败记录，只有实际发生相关故障的视频才记录。关闭时故障使用旧会话媒体标识，不能误记为正在打开的新视频。

持久化记录采用有界容量和稳定媒体身份；内容更新及用户手动重试的清除规则须在实现前明确。不得保存含凭证的原始媒体 URL。记录是避开已失败路径的策略，不是文件损坏的归因结论。兼容成功、兼容失败、重启、连续故障和记录上限均应覆盖，提示“已切换”必须与实际切换成功一致。

## 实现切片与审查记录

先完成 T012 显式 compatible 模式作为独立可验证基础：ArkTS PlayerOptions → bridge → NAPI CreateSession → Initialize；在选择渲染器前固定 CPU 路径，配置失败返回错误。第二阶段 T013 建立可靠会话关联；T009/T004 先证明音频与工作线程安全后才开放非退出策略。架构见 contracts/player-recovery.md，状态见 data-model.md，宪章与需求一致性见 checklists/constitution-and-consistency.md。T012 不是全局恢复的替代验收。

## 软件兼容路径的 fence 前置修复

源码审查发现 SwRenderLoop 未等待 RequestBuffer 返回的 release fence 就 CPU 写入，并把同一 fence 交给 FlushBuffer。依据 [官方 NativeWindow API](https://developer.huawei.com/consumer/en/doc/harmonyos-references/capi-external-window-h/) 与 [OpenHarmony NativeWindow 指南](https://github.com/openharmony/docs/blob/master/en/application-dev/graphics/native-window-guidelines.md)，生产者须先等待 release fence，并在不再使用时关闭；CPU 同步写完后提交 -1，不能复用 release fence。

T014 先测试真实 SwRenderLoop：已就绪 fence、未就绪超时、错误 fd、RequestBuffer 失败及原暂停 resize/Flush 重试。实现固定总计 50 ms 的 poll 等待（EINTR/EAGAIN 不重置期限），失败时不读取/映射/写入缓冲区，归还已申请的 buffer 并上报失败；正常路径关闭 release fd 后 CPU 写入，再以 -1 提交。无新平台 API，NativeWindow 相关接口自 API 8 可用。此等待仅在渲染线程，不占 UI；不证明 NativeWindow 自身调用永不阻塞，整体预算仍由 T004/T009 负责。
