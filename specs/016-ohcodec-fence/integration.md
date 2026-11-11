# FFmpeg PR #11 接入记录

2026-11-11，消费已合并上游 SDK，未修改或构建 ohos_ijkplayer。

## 来源与兼容核验

- 合并提交 `32887363cb103163fe6557ca64c05539ad6d73f2`，独立浅克隆读取该提交的 32 项交付文件，与上游合并绑定摘要一致。
- SDK 归档 `eb069effc2ce51233186e5e033a2f8bf33f5317a27e4626ba50184807422aea0`，原始 manifest `7fd9cc6e5916b0b0b864e0c522e4134795774c1bb8c45e4f331d4788c17f4bbf`。SDK 目录和归档各 217 项逐项校验，包括符号链接目标内容。
- 六库导出集合逐项一致；142 个 mpv 原构建使用的 FFmpeg 头文件逐字节相同。为可靠故障通知补丁重建 mpv 并保留真实编译输入，当前 FFmpeg 运行库独立锁定。
- libavcodec 新增导入仅 NativeObjectReference/NativeObjectUnreference。官方 native SDK `native_window/external_window.h` 声明两者 introduced=8.0.0，Surface ID 查询 introduced=12.0.0，覆盖 API 19；未新增 Player API。
- Samba 两张 131072 字节字符表完整内容分别唯一匹配新 libavformat，偏移变为 4127144、4258216。公共 SMB 头内容不变。
- 正常 FFmpeg 六库来自上游无 TRACE/TEST/DIAGNOSTIC/EXPERIMENT 的构建；mpv 保持原 TRACE。编译宏按组件区分，旧 mpv 编译记录内的 FFmpeg 信息不冒充本轮 SDK 来源。

## TDD 和本地检查

先增加当前恢复 SDK 必须绑定、缺失/错误绑定三项回归，旧清单全部失败。接入及校验器更新后，28 项实际输入和篡改回归通过，包含旧库冒充恢复、伪造 SDK/merge、混用宏范围等负例。

49 项宿主门禁、9 项实际 mpv fence 函数、音频中断实际生产函数回归、5 项归档输入测试及外部来源审计通过。Spec Kit prerequisite 通过。

## 宪章与一致性

R6 → T016/T017 → 来源清单/独立绑定校验 → 实际输入正负例及 iMac CI。R7 → T018/T019/T020 → 设备同 PID 音画证据。R8 → T021 → API 19 与 API 20+ 音频中断回归。当前无新增 UI/权限/媒体协议或解码模式；正常保持 OHCodec/Vulkan 零拷贝。

此轮执行进展与当前结论以文末联合验收及任务表为准。上一轮 PID 32928 的平板记录对应旧六库和早于延迟回收修复的代码，不计作本轮通过。云真机访问现已恢复；API 19 TV 与 API 20 模拟器音频回归已执行。

## 旧审查补齐

- 事件队列满时丢失 owner 故障：先用实际源函数测试复现缺少可靠通知，再增加由 client 锁保护的独立故障槽，保留首个故障参数并在普通队列前消费。payload 归 client 持有，销毁 client 自动释放。测试覆盖满队列、重复故障、参数副本、其他 owner 不受影响和消费一次；ASan/UBSan 通过。没有新增公共 mpv 导出。
- 环境清理期间 TSFN 生命周期：实际 CleanupSessions 回归在原实现失败；现在清理钩子返回前同步封闭投递并释放 TSFN，耗时资源仍后台销毁。真实终局对象仍保留，回调通道先关闭。
- 真实 Initialize 回归覆盖 Vulkan 硬解获取隔离器、设置隔离选项、软件模式、非 Vulkan、名额耗尽及选项失败；纳入 native-entry 门禁。slow-release 用例增加 4.8–6.5 秒预算断言，旧任务仍阻塞时验证第二会话可执行。
- 测试线程按值捕获 gate，确保共享等待状态的生命周期。历史单次注入补丁指向原提交；解码模式计划明确正常硬解与上限降级范围。
- 命令/诊断超时永久隔离的两条旧评论已不适用于 1ae34e1 后实现：普通超时不会 Quarantine，关闭保持排队，成功完成才回收名额。明确 owner 故障仍发送所属会话错误。
- Surface ID 非复用已由当前联合设备日志补证，见下述证据目录。

最终本地门禁在补齐 parent-chain 的真实回调关闭函数后重新执行，49 项全部通过；输入审计 28 项、CI 合同 29 项通过。初次重跑的 parent-chain 因测试壳缺少新生产方法而编译失败，补齐实际函数提取后通过，未跳过断言。新的 mpv 两次独立构建均为 `c1997eee1f1190aca663e49ef86e98b96a1403cf5e2f99b16158cd217ef7d56a`，导出仍为原有 58 项。
## PR 第二轮清理审查（2026-11-11）

两条 CodeRabbit 文档意见已在 a67e504 修正：历史单次注入明确指向 39f62ad，解码策略约束明确允许隔离名额耗尽后的软件回退。Cursor 的旧审查状态通知不表示新增缺陷。

新增两条清理意见均有可复现行为。`callback-cleanup.test.py` 逐字编译 `SetEventCallback`、`Dispatch`、`CallCallback`、两种关闭方法与 owner 故障分支，使用 NAPI 排队替身。修复前 queued、owner、replace 三种情况均断言失败；修复后它们与正常投递、空环境回收、隔离后只允许错误事件共 6 项通过 ASan/UBSan。每个事件共享对应回调代的关闭标记，队列释放时只销毁数据，不调用 JS，也不依赖 Session 存活。关闭 JS 通道不再置 `stopEvents_`，原生监听持续到 `Release` 安全停止，仍可观察迟到故障。

完整宿主门禁 49 项及真实 completion 生产函数回归通过；新测试已接入 native-entry 门禁。Spec Kit 前置检查与宪章一致性检查通过：未增加平台 API、权限或 FFmpeg 改动，R10 → T023 → 生产回调/故障分支 → 回归可追踪。平台和 NAPI 为替身，不能据此宣称设备环境销毁或 GPU 恢复已验收。

a67e504 的 iMac CI [42912627864](https://github.com/yaoshining/VidAll_Player/actions/runs/42912627864) 已通过，实际构建 PR 合并预览 122648249ec59f81b3641f9488533c21477bc1f7；本次桥接库修改仍需新的 CI HAR，不能沿用该包作为最新修改验收。

## d287e45 联合验收更新

[iMac 自托管 CI 42914926664](https://github.com/yaoshining/VidAll_Player/actions/runs/42914926664) 构建合并预览 af91823a4ce97d4bb52e4332a4b4ed6be291dc32，HAR SHA-256 adf5b194b63605666590fe5dd9891fe7fada471bab6cbf0053fa1853d7e75c46。当前 49 项宿主及 fence/来源测试保持原已通过结果；本轮新增证据不改生产代码。现有 PR 检查无失败（云端分支专属检查为 skipped，CodeRabbit 为 neutral），不是云端 Mac 构建。

MatePad Mini 完成 Vulkan 关闭错误隔离、同 PID 新硬解音画、不同 Surface、延迟释放名额回收、上限软件降级，以及上游 Stop/Destroy 分别注入后的新会话恢复。完整绑定、日志、配对画面和范围见 [联合验收](joint-evidence/README.md)。API 20 消费端中断后选集仍失败，定位其用户操作状态未重置；API 19 TV 真机尚未验收。任务不因 CI 或诊断包通过而提前全部完成。未合并 PR #92。

本轮另核实 CodeRabbit 的两条超时文档意见：5 秒仅适用于持有 SessionIsolation 的会话；超时不取消已提交操作，宿主应避免盲目重试。已据实际 NativeWork 分支与队列语义修正文档，无生产代码改变。Spec Kit 前置检查、文档差异检查通过；R7 对应当前绑定的平板原始证据，R8/T021 仍明确失败，满足宪章的分层验收和职责边界要求。

## 非隔离会话清理补充（T024/T025）

CodeRabbit 的两项 major 均成立：未启用隔离的软件解码会话会在清理入口同步析构；被诊断工作持有或已进入终局的会话又可能留下回调。本次在清理入口对所有会话关闭 JS 通道，统一把最后引用的析构交给后台；终局或已隔离实例继续保留。后台线程无法启动时记录错误并保留资源，不同步回退，不改解码模式。

真实 CleanupSessions/DeleteSession 的三项新增回归在修改前失败，分别报告阻塞析构与两次残留回调；修改后通过。测试保留后台引用直到清理返回，再验证仅析构一次。父级测试补充等待后台析构完成，并明确终局清理必须恰好关闭一次 TSFN、随后返回；GPU、窗口、播放器的终局析构仍禁止，其他用例的禁止规则不变。回调 ASan/UBSan 编译增加 120 秒超时。

本次修改涉及 NAPI 桥接库，d287e45 的设备记录仅作为历史版本证据。修复提交时 T025 尚未通过；后续复验结果见文末。API 20 消费端选集失败仍按 T021 保留。未修改 FFmpeg 或真实 VidAll_TV，未合并 PR。

最终 49 项宿主门禁通过，包含 13 项真实入口、6 项回调 ASan/UBSan、10 项父级场景与反例变异检查；[红绿绑定记录](cleanup-regression.json) 保留具体失败和通过结果。初次完整门禁仅父级的旧终局回调断言失败，按上述明确契约补正后完整重跑通过。Spec Kit 前置检查通过；宪章核对无新增平台 API、权限或跨项目改动，R9/R10 → T024 → 入口回归可追踪。

## 2ad7fdd 当前桥接库复验通过

T025 已完成：[iMac 自托管 CI 42927679634](https://github.com/yaoshining/VidAll_Player/actions/runs/42927679634) 的 HAR 和新桥接库在 API 24 MatePad Mini 实测。正常包九库完全匹配 CI；诊断包仅替换各自明确标记的探针库。普通坏片失败后同 PID 返回并播放 B；活动软件解码 Worker 直接终止后，退出回调 13 ms、UI 心跳继续，返回列表后同 PID 再播 B 硬解音画正常。Vulkan 关闭错误、新 Surface、延迟成功名额回收、上限软解，以及上游 Stop/Destroy 的两种关闭错误均使用新桥接库复验通过。

完整哈希、时间、PID、Surface、设备音频、配对画面和限制见 [当前设备证据](final-device-evidence/README.md)。云调试设备已释放；未使用云测试自动任务，未开启付费。该设备实验不模拟永久 GPU 挂起或确定性 TSFN 竞态；对应阻塞及回调回归以生产函数宿主测试为准。API 19 TV 真机及正式文件入口未验收；API 20 选集状态问题独立跟踪 [VidAll_TV #371](https://github.com/yaoshining/vidall-tv/issues/371)，T021 不改为通过。本轮未修改生产代码，未合并 PR #92。
