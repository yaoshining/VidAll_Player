# 正常核心与宿主存活接入

Spec 017 候选增加 `preserve-host`。默认播放仍为 OHCodec/Vulkan 零拷贝硬解；全局终局后保持主应用和列表存活，安全条件满足后可新建软件兼容实例。当前实现、主机和本地构建已验证，CI/设备结果见 [Spec 017 证据](../specs/017-host-survival/evidence.md)，未完成项不能视为交付通过。

## 初始化与恢复

所有 Player 创建前先初始化：

```typescript
import { initializePlayerRuntime, getPlayerRuntimeStatus, createPlayer } from '@vidall/player';

await initializePlayerRuntime(context, {
  terminalPolicy: 'preserve-host',
  deadlineMs: 3000
});
const player = createPlayer();
```

`deadlineMs` 是 1000–10000 ms 的整数。preserve-host 下它只决定等待状态是否显示为 timeout，不调用 `_Exit`，也不解除全局硬解安全锁。必须使用包含恢复 ABI `0x00020000` 的完整 HAR；旧核心或缺失接口会返回 `RUNTIME_RECOVERY_UNAVAILABLE`，不会偷偷切回退出策略。初始化同配置幂等、不同配置拒绝。

`onPlayerTerminal` 是进程内一次性通知，投递后自动移除；终局后的订阅同步重放且不长期持有闭包。刚观察到终局时，完整记录可能尚未发布（firstObservedMs 为 0），该通知立即关闭旧操作；后续状态查询会更新为完整记录，但不重复通知原订阅者。媒体标记应使用 onPlayerFault 的可靠归属，而不是用暂态通知猜测。普通 `onPlayerFault` 仍须由宿主显式取消订阅。`onPlayerTerminal` 用于更新失败状态和导航，**不要调用 killAllProcesses**。终局后旧实例不可再用；释放/放弃旧实例不等待尚未确认安全的 GPU 资源。`getPlayerRuntimeStatus()` 的 state 保持 terminal，recovery.state 独立表示：pending 等待旧音频停止；timeout 超过观察期限但继续保留资源；ready 已确认旧音频停止。ready 后用 `createPlayer({ playbackMode: 'compatible' })` 创建新实例并附加新 Surface。普通模式在本次进程中始终拒绝新建；重启进程后未标记视频重新优先硬解。

compatible 强制软件解码与软件渲染，绕过 Vulkan/EGL/OHCodec interop。原 `hardwareDecoding: 'disabled'` 只控制解码器，不等于兼容恢复。新实例仍按既有事件合同加载、等待准备、播放及释放；恢复成功须以实际首帧与音频确认，不能仅凭 create/load Promise 成功显示“已切换兼容模式”。若旧音频平台 Stop 永久不返回或不能确认停止，保持 pending/timeout，不强行释放或假称续播成功；这是当前安全恢复的实际限制，R3 设备验收仍未完成。

已确认 renderer 释放后，后续 builder 清理失败或阻塞不再阻止恢复 ready；builder、AO 与登记槽仍被保留并占用预算。ready 只证明旧音频已静止，不代表旧资源全部归还，宿主仍须使用新实例与新 Surface。

原 `controlled-app-exit` 仅为既有消费者保留，其期限仍触发退出；VidAll_TV 新接入须显式选择 preserve-host。旧 `fixtures/normal-core-consumer/terminal` 是该旧合同的回归夹具，不是 TV 新接入示例。

## 故障归属与单视频记忆

`player.load(source, onIdentity?)` 的可选回调在原生提交前同步收到只读 `{ sessionId, loadGeneration }`，两个值为十进制字符串。TV 在该次调用的闭包中登记到稳定媒体 ID；回调抛错取消加载，返回 `LOAD_IDENTITY_REJECTED`。回执只表示分配身份，不表示播放成功。队列拒绝允许留下代号空洞，不复用或倒退。

用 `onPlayerFault` 接收独立于 Player 生命周期的故障历史：最多 16 条，按 sequence 去重，可取消订阅；关闭后的失败仍可报告。known 归属才可写入该视频的兼容标记，unknown 不得按当前页面猜测。Player 不保存 URL 黑名单；TV 负责有界身份映射、持久化、提示、导航和用户重试，见 [TV #372](https://github.com/yaoshining/vidall-tv/issues/372)。其他视频仅因本次进程临时使用兼容模式，不能被记成失败。消费端 #371 的手动选集暂停标记独立处理。

每次打开至多自动切换一次；兼容失败仍可返回列表，不自动无限重试。自动切换和连播不能解除用户暂停或未结束的音频打断。

## 资源与迟到操作

可归属的硬解会话故障保留原 Surface、解码器和 Vulkan 对象，最多两个硬解隔离名额；有名额的新实例仍可硬解。名额耗尽后的普通软件解码不应被当作全局终局后的纯软件渲染恢复。

全部会话创建前申请预算：标准 6、故障前兼容 2、故障后恢复 2；正常释放可归还，超时/隔离保留不归还。常规/关闭/恢复工作预算分别为 32/8/8，ArkTS 队列最多 64。每会话独立有界执行器使创建/命令/关闭的前台等待最多 5 秒；全局配置独立单执行器。超时不等于平台操作取消，禁止盲目重试相对 seek 等操作。上限到达明确失败，不增加无界线程或强行释放未知状态资源。

原生事件邮箱每个回调代最多排队 64 条、256 KiB 有效字符串负载，单条最多 64 KiB；高频进度、字幕和参数快照合并，关键状态与播完事件保持顺序。JS 正在处理的批次与下一个批次可同时存在，因此每代上界为 128 条、512 KiB 有效负载。普通回调代最多 32 个，故障后恢复代另保留 8 个；旧票据和 finalize 未结束前不归还额度。这里限定事件有效负载，不是进程 RSS 或系统播放器内存。

不能继续可靠交付时，当前桥会话进入 `PLAYER_EVENT_QUEUE_FULL`，普通命令和读帧停止，安全释放仍可执行。宿主应释放该会话后创建新实例，不应在原会话反复 load。该错误不是媒体硬解故障，不得据此把视频记成需兼容模式。回调代预算耗尽返回 `CALLBACK_RESOURCE_LIMIT`；用户仍能返回列表，待旧回调回收后重开，不自动无限重试。

旧代的排队回调不得进入新会话；NAPI 环境关闭和同地址复用也不能接管旧句柄。旧音频数据回调退休后静音，停止确认与释放有独立登记。API 19 旧回调只在取得/归还在途引用时持登记锁；注销先撤销入口，再等待自身在途回调，不阻止其他实例登记。平台阻塞不占全局登记锁。仍需设备验证真实音频焦点及系统服务行为。

## 架构、产物与迁移

本候选完整播放核心仅支持 `arm64-v8a`，HAR 含 Player 桥与八个依赖，共九库。x86_64 的旧探针不具备播放能力，不能混入旧 Player 桥来宣称兼容。VidAll_TV 如仍发布 x86_64，当前完整 HAR 尚不能覆盖该架构，需另行取得匹配的上游 FFmpeg x86_64 SDK 并由 Player 构建；不得静默删掉消费端声明。

迁移时核对 CI 原始 HAR 与源提交/九库哈希，一次性替换旧 HAR 和重复六库；不要在 TV 重打包 Player。完成初始化、加载身份登记、独立故障订阅和兼容新实例流程后，分别验证正常播放、音频打断与手动恢复、切集、退出重开、故障后返回并再播另一部、连续故障上限。API 24 或宿主替身不替代 API 19 TV 正式文件入口验收。

普通分支最终 HAR 来自 iMac 自托管 GitHub Actions；本轮 mpv/libplacebo 交叉构建在 MacBook Pro / Darwin arm64 完成，FFmpeg 使用上游预编译恢复 SDK。最终交付须同时记录这两层来源，不能把 iMac 或本地构建称作云端 Mac。
