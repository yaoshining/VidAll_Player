# SMB localhost HTTP 代理策略

本文档描述 VidAll_Player 播放 SMB 媒体文件的策略、职责划分、安全约束与验收用例。
对应任务：US4 T055/T056/T057（`specs/001-harmonyos-mpv-sdk/tasks.md`）与 Issue #5。

## 背景与范围

首期**不实现** mpv 原生 `smb://` 协议（libsmb2 未纳入受控构建，且真机验证成本高）。
业务应用（VidAll_TV）通过内置 HTTP 服务器把 SMB 文件暴露为本地环回 HTTP URL，
播放器只消费 `http://localhost:PORT/smb/...` 形式的地址。这样 SMB 认证、
连接池与文件访问全部由业务层控制，播放器不接触 SMB 凭据。

## 职责划分

| 层 | 职责 |
|---|---|
| 业务应用（VidAll_TV） | 维护 SMB 会话与凭据；内置 HTTP 服务器暴露文件；支持 Range 请求与认证透传；为每次播放分配 `proxyLeaseId` 并在租约释放时关闭代理连接、回收端口 |
| SDK（`@vidall/player`） | 校验 `localhostProxy` 媒体类型（仅明文 HTTP + 环回主机）；在会话内关联 `proxyLeaseId`；切源/停止/释放/网络失败时清理租约并以脱敏 `log` 事件通知；网络失败分类（可重试/不可恢复） |
| 原生层（`entry/src/main/cpp/napi_bridge.cpp`） | `loadMedia(kind, url, authorization, proxyLeaseId)` 按类型加载；`localhostProxy` 尽量设置 `force-seekable=yes`（失败不阻断）；记录租约关联并在切源/停止/释放时输出脱敏日志 |

## 安全约束

- `localhostProxy` 仅接受 `http://` + 环回主机（`localhost`、`127.0.0.1`、`[::1]`），
  端口可选。HTTPS 或非环回主机在输入校验直接拒绝（`URI_KIND_MISMATCH` /
  `INVALID_LOCALHOST_PROXY`）。
- 凭据只能走 `headers.authorization`，禁止进入 URL；URL 中的 userinfo 一律拒绝
  （`URL_USERINFO_FORBIDDEN`）。
- 租约释放日志只包含 `lease=<id> host=<host:port> reason=<原因>`，
  绝不包含路径、查询参数或凭据；日志文本再经脱敏过滤（Authorization/token 等）。

## 租约生命周期

1. `load({ kind: 'localhostProxy', uri, proxyLeaseId })` 校验通过后关联租约。
2. 以下时机释放全部活跃租约，并投递 `log` 事件（`SMB 代理租约已释放 …`）：
   - 切换媒体源（`reason=source-switch`）
   - `stop()`（`reason=stop`）
   - `release()`（`reason=release`，关闭前投递，监听器仍可收到）
   - 网络失败上报（`reason=network-failure`）
3. 业务层订阅 `log` 事件即可据此关闭代理连接、回收端口，避免旧租约泄漏。

## 缓冲与恢复

- 原生层 `getBufferingState` 读取 mpv `paused-for-cache` 与 `demuxer-cache-state`
  （mpv 0.40 已移除 `cache-buffering-state`，改读该节点的 `buffering`/`cache-end`）。
- SDK `reportBuffering(paused, percent?)` 把缓存等待映射为 `buffering` 事件：
  进入时记住原状态（playing/paused），恢复时回到原状态。
- 网络失败经 `classifyNetworkFailure` 分类：`NETWORK_TIMEOUT`/`NETWORK_DISCONNECTED`/
  `CONNECTION_REFUSED`/`PROXY_UNAVAILABLE` 可重试；`TLS_CERTIFICATE_INVALID`/
  `HTTP_AUTH_REQUIRED`/`HTTP_NOT_FOUND`/`FORMAT_UNSUPPORTED` 不可恢复；未知码默认
  可重试。恢复方式为消费者重新 `load()` 同一来源（`error → preparing` 合法）。

## 验收用例

> 结论状态遵循三态原则（FR-037）。下列用例的 SDK/原生逻辑已由 Hypium 端侧测试
> （`StreamingSession.test.ets`、`StreamingInternals.test.ets`）与构建覆盖；
> 涉及真实播放、跳转与断网的行为需要在 ARM64 TV 真机上执行，当前结论为
> **已构建待验证**。

### AC-1 大文件 seek（Range）

- 前置：业务层 HTTP 服务器支持 Range；代理一个 >2GB 的 SMB 文件。
- 步骤：`loadMedia('localhostProxy', url, '', leaseId)` → 播放 → 多次快进/快退。
- 预期：seek 后从目标位置恢复播放，不卡顿、不崩溃；`force-seekable` 不可用时
  跳转能力取决于代理 Range 支持，日志给出警告。
- 结论：已构建待验证（ARM64 真机）。

### AC-2 认证透传

- 前置：SMB 共享需要用户名/密码；业务层 HTTP 服务器要求 Authorization 头。
- 步骤：`loadMedia(..., 'Authorization: Basic <base64>', leaseId)`。
- 预期：播放成功；凭据只出现在请求头，不出现在 URL、事件或日志；
  认证失败时上报 `HTTP_AUTH_REQUIRED`（不可恢复），提示重新认证。
- 结论：SDK 脱敏与错误分类已通过 Hypium 测试；真机认证链路已构建待验证。

### AC-3 连接断开恢复

- 前置：播放 SMB 代理媒体中。
- 步骤：停止业务层 HTTP 服务器或断开 SMB 链路 → 观察事件 → 恢复链路后重新 `load()`。
- 预期：上报 `error` 事件（`retryable=true`，如 `PROXY_UNAVAILABLE`/`NETWORK_DISCONNECTED`），
  旧轨道清空、租约释放（`reason=network-failure`）；进程不崩溃；
  重新 `load()` 同一来源进入 `preparing` 并恢复播放。
- 结论：SDK 清理事件顺序已通过 Hypium 测试；真机断网已构建待验证。

### AC-4 多文件切换不冲突

- 前置：两个 SMB 代理文件，各自持有不同 `proxyLeaseId`。
- 步骤：加载文件 A → 播放 → 加载文件 B → 停止 → 加载文件 A。
- 预期：每次切源先释放旧租约（`log` 事件 `reason=source-switch`），
  旧代理连接可被业务层回收；新旧媒体状态不交叉；停止时释放当前租约。
- 结论：租约生命周期已通过 Hypium 测试；真机并发连接已构建待验证。

### AC-5 租约清理完整性

- 步骤：分别以切源、`stop()`、`release()`、网络失败四种路径结束会话。
- 预期：四条路径都产生且仅产生一次对应 `reason` 的释放日志；
  `release()` 的日志在 `closed` 事件前投递；释放后不再有活跃租约。
- 结论：已通过 Hypium 测试（`StreamingSessionTest`/`StreamingInternalsTest`）。

## 后续（不在本期范围）

- mpv 原生 `smb://`（libsmb2 受控构建与真机验证）。
- 代理服务器 TLS（当前明文 HTTP 环回，不出本机，风险可控）。
- 业务层代理服务器的独立验收（属于 VidAll_TV 仓库职责）。
