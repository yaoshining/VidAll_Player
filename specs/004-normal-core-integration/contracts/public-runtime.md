# 公共运行时与终局契约（待审查）

## 进程配置

`initializePlayerRuntime(context, options): Promise<PlayerRuntimeStatus>` 从 `@vidall/player` 导出。`options` 必须显式提供 `terminalPolicy`，`terminalPolicy` 必须为 `controlled-app-exit`，`deadlineMs` 必须显式提供且为 1000–10000 的整数；独立消费者使用 3000。没有默认退出策略。期限从 native 首次锁存的单调时间计算，重复通知不得延后。未配置或初始化失败时，创建/播放返回可理解的配置错误；不允许先创建硬解再补配置。相同规范化配置幂等，差异拒绝；配置包含路径、资源版本、策略及 deadline，凭据不属于进程初始化参数。

状态为 `unconfigured → configuring → ready` 或 `failed`；`ready → terminal` 不可逆。同进程不能 reset/unregister；重新打开应用方可恢复。

## 公共终局记录

`PlayerTerminalInfo`：版本、阶段、平台错误、单调时间、受控退出 deadline、稳定非敏感 owner 标识。`onPlayerTerminal(listener)` 提供全进程通知，迟订阅读取已锁存记录；每个订阅者最多收到一次同一记录，迟订阅者回放同记录；事件只表示进程不能安全继续，不承诺资源已经回收。每个 Player 转入 error 并保持 terminal 标识。`getDiagnostics()` 保留已有返回契约，terminal 后仅提供缓存并明确缓存状态。

## 宿主职责与截止策略

宿主显式 opt-in 后，应显示故障提示、撤销本应用窗口保屏并通过平台应用退出 API 结束进程。native 独立 deadline 是宿主已同意的最后措施，期限到达后直接结束整个进程，不调用普通 release/join/mpv 或等待 UI 线程。退出码/原因可识别；正常播放、权限拒绝及普通错误不触发此策略。

## 快速失败

公开异步命令在 queue 入队前检查全进程 terminal，native 接口也在任何 lifecycleMutex 和 mpv 调用前检查。fatal 后禁止创建新 Player、播放/seek/暂停、正常 release；只允许 cached snapshot、错误返回和宿主受控退出。既有等待中的任务不要求被 GPU 解阻，但其存在不得阻止其他接口识别 terminal 或 native deadline 退出。

## 包与 API 支持

ARM64 绑定正常 8 库，新 bridge 构成包内 9 库。x86 probe 保留不支持真实播放的明确结果。兼容 API 级别必须由符号审计和加载方式证明，不由安装 compatible 字段推断。新签名/HAP仅独立消费者，`formalArtifactAllowed=false`。

现有 Player 方法签名保持，但初始化是新的必需启动前置条件，旧宿主必须显式迁移。诊断快照保留旧字段，新增缓存/不可用标记，不伪造 fresh。故障注入仅在独立测试接缝，生产 SDK 不导出故障开关。
