# 实施计划：正常核心组合最小接入

状态：方案已审查，实施与本地验证完成；精确提交审查及远端 CI 待完成。对应 [spec.md](spec.md)。

## 技术方案

1. 以 951343 的完整 tree 为起点，新增 `specs/004-normal-core-integration`，不改原主 checkout。旧候选与历史 release 记录原样保留；新输入存入新目录，CMake 明确选择完整正常组合。
2. 新建公共进程初始化模块，经 `Index.ets` 导出。异步准备私有 state/cache/resource 目录与必要 Samba 配置；不写系统目录、不修改环境变量、不读取或提交密码。资源内容从 producer 已验证闭包取得，逐文件哈希锁定。
3. native 进程服务负责配置一次性 SMB runtime 与 terminal API。固定存活期回调/opaque；注册、独立监听线程、deadline 建立成功后才 enable。所有失败都锁存初始化失败，禁止半配置创建。
4. 公开宿主配置必须显式选择 controlled-app-exit，并接受 native 最后截止退出；公开 fatal 事件用于 UI 提示与正常宿主退出调用。SDK 不擅自默认终止应用。native deadline 使用单调时钟和独立线程，禁止锁、日志或 ArkTS 回调作为退出前提。
5. native 全实例共享进程 fatal 原子状态；terminal 快照直接使用公开 bounded snapshot API。桥接入口先检查 fatal，才允许 lifecycleMutex、mpv 或队列。正常调用的 native 工作移出 UI 线程；已有异步结果晚到不得重置 fatal。
6. ArkTS session 在 commandQueue 之前快速检查进程状态；fatal 缓存诊断/状态，并通知所有实例。普通 release 保留现有结果；fatal release 不进入清理链，只返回明确终局状态，由宿主进程策略负责终止。
7. 独立消费者位于独立测试目录，通过打包 HAR 依赖 `@vidall/player`。仅新测试 bundle 使用本机签名（私有），不改 TV；应用保屏只随本应用窗口生命周期，正常退出回读关闭，终局退出保留系统窗口/进程退出证据。

## 构建与兼容性

语言为 ArkTS/C++17；保持 target API22 / compatible API15。本轮 native producer 输入以 API24 工具链生成，先从 ELF undefined symbols 与 SDK 头文件版本标注建立支持表，若发现低版本硬 DT_NEEDED/undefined 符号依赖必须先报告再确定方案：加载后能力探测无法兜底已经发生的加载失败，不能默默改版本。现有 x86_64 仅 probe，不冒充真实播放；ARM64 全组合验证。

新 HAR 应携带其运行所需的完整动态库；libplacebo 静态绑定保留编译输入身份。所有 native 头文件与相应二进制绑定，公开 ABI 新增不得删除旧导出。包内 9 库是 8 个核心动态库加新 Player native bridge。

## TDD 与门禁

- 先加入实际模块/真实 NAPI 桥接可编译测试或逐字函数提取，记录旧源码 SHA、编译命令、语义 RED；不以自行模拟实现替代桥接。
- 正常/失败：同配置、异配置、不可写目录、资源缺失、ABI不符、SMB配置失败、terminal注册/enable失败、重复实例。
- 终局：队列已有挂起命令、生命周期锁被占用、callback阻塞、日志阻塞、晚到异步完成；所有新命令/诊断/release bounded 返回且零 mpv/join；native deadline 真正进程退出，验证错误退出/timeout不能冒充成功。
- 兼容：真实 public root 导出编译，既有 diagnostics/firstFrame/字幕音轨测试继续运行。
- 集成：实际 HAR consumer 构建、库身份/依赖闭包扫描、两次 clean 输出比较、短真机场景；故障注入与真实终局明确区分。
- 证据：本地重放→审查→精确提交预览→用户该SHA批准→CI。无批准不 push。

## 宪章检查

已满足范围、中文文档、用户授权的 terminal 例外与基线核对。API声明审计、TDD、目标构建与短真机验证已有本轮证据，低 API 真机和真实 GPU 故障仍待验收。保留未验收列表；不重做60分钟长播，不覆盖旧失败记录。

## TV 后续接入要求（本轮不实施）

TV 后续须启动时异步配置私有 runtime 和显式终局策略，订阅致命事件后显示提示、撤销应用保屏并请求结束整个应用；终局不得调用普通 Player.release 或等待被阻塞命令。新 HAR 自带全套运行库，TV 未来必须原子移除或替换其旧六库，不能新旧混装；替换 HAR/配套库、正式签名和发布需单独批准。本轮独立消费者证明该契约。

## 审查决定

2026-10-23 root 审查通过范围与 FR→任务覆盖，并固定公共 API 名称、显式策略、1000–10000ms deadline（fixture 3000）、一次事件及迟订阅回放。异步 worker 只使用入口解析的普通 C++ 参数，不能访问 napi_value；complete 回 UI 生成结果。对象持有到工作完成；CleanupSessions、异步 create 尚未注册和 release 移出 registry 后终局都需真实父级链回归，不能通过最后 shared_ptr 析构绕开终局隔离。
