# 故障归属链审查与终局元数据发布回归

2026-11-11。审查基线为 `466630e156e8559a903858283194d7239b168a3d`，派生源码为已绑定交付输入的 mpv 源树；本记录不把平台替身或软件路径注入提升为 OHCodec/Vulkan 真机整链验收。

## 已确认并修复的缓存竞争（T029）

原生 `Observe()` 在完整记录首写者完成前先设置 `terminalObserved`，这是立即禁止旧代命令所必需的。此时 `Snapshot()` 可以返回 state=terminal、firstObservedMs=0。NAPI 如实序列化暂态；旧 ArkTS `runtime.ets` 却把第一次 terminal 永久缓存。完整记录稍后到达后，stage、platformError、ownerTag 与 attribution 仍被旧缓存替换；controlled 策略甚至立即停掉轮询并短路原生读取。

先以真实 `runtime.ets` 注入“暂态零值 → 完整 known(17,4)”复现，断言得到 `firstObservedMs: 0 !== 123`；独立 `faults` 历史中的 known 归属仍正确。因此该缺陷是终局公开快照永久陈旧，不是已证明将 A 错标为 B。

修复保留即时终局通知及旧挂起 Promise 的立即拒绝：`firstObservedMs=0` 表示元数据尚在发布，后续首份完整记录可更新缓存，但同一终局监听者不再次通知。晚订阅者同步收到完整缓存；已交付给早期监听者的对象不被原地修改。controlled 策略只在完整记录到达后停止轮询/启用缓存短路；preserve-host 继续查询恢复状态。消费方需要最终统计或媒体归属时，应读取完整状态或独立 `onPlayerFault`，不能把暂态 unknown 当成最终归属。

新增 `terminal-publication-preserve`、`terminal-publication-controlled` 及两种策略的 `reentrant` 用例，覆盖早/晚订阅、监听者异常、通知中重入/订阅、完整记录更新、零残留监听器，以及元数据未发布时旧 attachSurface Promise 仍被 PLAYER_TERMINAL 及时拒绝。红测分别因陈旧元数据及过早 clearInterval 失败；修复后四例通过。

## 各段实现与证据边界

| 链路 | 核对结果 | 当前证据 |
|---|---|---|
| ArkTS 调用 → 原生提交 | bridge 对每次 load 使用固定 generation；身份回调发生在 native load 前，回调抛错取消提交，失败允许代号空洞 | load-identity 宿主用例覆盖 A/B 排队、关闭后 A 故障、队列拒绝、回调拒绝与终局重入 |
| 原生 Load → mpv 命令 | BeginCompletion 拒绝倒退/重复/不安全整数；扩展函数将 session 固定到该 mpv global，将 generation 附于该次 mp_cmd | completion-event 编译真实 Load/Stop/回复/EOF 分支；fault-context 编译实际扩展入口 |
| 命令 → playlist → decoder | cmd_loadfile 写入 entry；play_current_file 发布所选 entry 的代；vd_lavc create 捕获不可变 session/load，decode_frame 将其写入输出帧 | 源码追踪及既有目标编译。当前故障上下文测试没有真正运行 demux/decoder/playlist 全链 |
| 帧 → 引用/属性复制 | mp_image_new_dummy_ref 复制结构；mp_image_copy_attributes 显式复制两项身份。未知转换路径不能借当前页面补猜 | 源码检查；实际过滤器/硬件输出整链仍需目标验证 |
| 帧 → OHCodec retained | 仅 interop map 成功后才把 mapper->src 移入 last_src；replacement 失败保留旧 last_src。fault 仅接受与 hw global session 匹配且两值非零的 last_src | fault-context 用当前 B/保留 A、无 last_src、跨实例帧和 owner-only 路径验证。真实 GPU/fence 未注入 |
| retained → 隔离或进程终局 | 隔离消息携带五字段；无 mapper 的 owner 故障明确 unknown；进程终局以一次性发布记录保存身份，不借 owner 地址反查 | 实际入口测试；零拷贝真机故障归属仍待验证 |
| 隔离 → 独立历史 | 事件线程先 RecordSessionFault，再关闭实例/发送实例错误；历史最大 16 项；JS 轮询按 sequence 去重 | fault-close 提取实际分支，证明实例回调关闭后仍保存 known；不等于完整平台关闭生命周期 |
| 全局记录 → 宿主快照 | T025 立即关闭准入；T029 允许完整元数据替换暂态缓存，保持一次性通知 | 四项新增真实 ArkTS 运行期红绿回归 |

同 URI 重载不参与归属键，归属只使用 session/load 组合；completion-event 的真实 Load 测试已有重载、晚到和失效覆盖。仍建议真机整链同时记录“同 URI 两次 load 的不同 generation、A 旧帧关闭失败、B 新请求已建立”的证据，不能仅以字符串相同/不同推断媒体身份。

## 本次执行

- `normal-runtime.test.cjs` 全部 25 个用例通过，包含新增四项。
- `fault-context.test.py` 对当前完整派生 mpv 源通过，涵盖命令身份与故障上下文。
- `fault-close.test.py` 通过，关闭中的故障归属不依赖旧 TSFN。
- `completion-event.test.py` 通过，保留实际 Load/Stop/COMMAND_REPLY/END_FILE 回归。
- `git diff --check` 通过。

尚待主任务统一执行 ArkTS HAR 构建与完整宿主门禁。没有修改 FFmpeg 或原生核心，本次修复无需改变已锁定的 mpv ABI/源码输入；最终 HAR 仍需由 iMac CI 生成。
