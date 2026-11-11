# 实施与验证记录

日期：2026-11-11。分支 `codex/host-survival-contract`，基线 main `fa27cbd346f1a745ffc1b5bfd57b4239c094327f`。本记录是首个实现切片，不是全局故障恢复验收。

## TV 协作

已创建 [VidAll_TV #372](https://github.com/yaoshining/vidall-tv/issues/372)，承接单视频兼容记忆、重启后的选择、提示、故障归属处理和 API 19 TV 正式入口回归。

## TDD

1. `node native/tests/host-survival/compatible.test.cjs`：实现前失败，compatible 仍传 auto，缺少第五个原生播放模式参数；实现后通过。执行真实 createPlayer / PlayerSession / bridge，仅替换平台 NAPI。
2. `python3 native/tests/ohcodec-fence/initialize.test.py`：实现前新增五参数调用无法编译；实现后编译真实 Initialize，验证 GPU 存在时兼容模式仍选择 software、无硬解名额、hwdec=no/interop=no、非法模式和关键选项失败。原硬解/两名额上限仍通过。
3. 真实 NAPI CreateSession 提取测试增加 compatible、旧四参调用及非法模式用例，验证新参数确实转发到 Initialize，非法模式不创建会话。
4. `python3 native/tests/surface-resize/sw.test.py packages/vidall-player/src/main/cpp/napi_init.cpp`：修复前 fence-ready/fence-timeout/fence-request-failed/fence-invalid 四项失败，其余原用例通过；修复后通过，并补充持续 EINTR、POLLHUP 用例，共 14 场景。用真实 pipe/poll/fd 关闭及提取的生产 SwRenderLoop；NativeWindow 为平台替身，不是真实 GPU fence。

## 验证结果

- `python3 scripts/test/normal-core/run.py --out <新目录>`：51/51 通过，包括上述兼容模式及 SW fence、原生入口、隔离名额、回调清理、旧终局保护和破坏性变异检查。既有退出契约仍保留，因此旧 deadline 测试通过不代表“不退出”要求已实现。
- GL 渲染/尺寸回归：12 场景通过。
- `native/tests/completion-event.test.py`：通过，覆盖 EOF 唯一性、非 EOF、媒体身份、晚到及线程交错。
- 音频中断生产函数测试：从 Phase30 A 的只读封存源选取所需文件，在临时目录应用本仓原有 `0001-ohaudio-legacy-interrupt.patch`，执行 `native/tests/audio-interrupt/interrupt.test.py <临时源目录>`，通过。本次未改 FFmpeg 或其仓库，未重建 libmpv/FFmpeg，不把此宿主结果称为新设备验收。
- `devecocli build --product default --modules vidall_player@deveco26`：本机 MacBook Pro / arm64 编译通过，HAR 为 ARM64 目标，仅本地预验证，非 CI 交付。首次误用不存在的 product deveco26 已更正为 default product + deveco26 module target。
- 构建有 HAR applyToProducts 不生效、既有原生库类型声明、clang unused gcc-toolchain 参数告警；无编译错误。未修改这些无关配置以消除告警。
- Spec Kit prerequisites 与 `git diff --check` 通过；宪章/一致性人工检查见 checklists/constitution-and-consistency.md，未完成门禁仍保留未勾选。

## 当前明确未完成

1. 全局 owner_tag 是不透明 hw 对象标签，当前 API 没有稳定的 session/load 映射；不能把它转换为媒体 ID，也不能猜测标记当前页面。T013 未完成。
2. 当前 mpv 终局回调契约明确不能在 handler 内查询/停止/释放 mpv。OHAudio 写回调与旧焦点尚无通过验证的终局隔离入口；不能假设发 pause/stop 就能穿越已挂起的 core/VO 锁。T009 待完成原生音频隔离及独立兼容会话实测。
3. 原两个隔离名额不覆盖全部软件会话/线程，需 T004 总预算设计；未改变 deadline、全局硬解禁令或强行释放策略。
4. `devecocli device list` 当前无连接设备；未执行本轮模拟器/真机音画测试。无 API 19 TV 验收。
5. 未推送本次分支、未创建 PR、无新 CI HAR；TV 不应接入本地包作为最终交付。

## 第二个实现切片：终局等待与会话预算

T015 的 queue.test.cjs 实现前因队列无上限等待超时失败；实现后覆盖 64 项上限、终局立即拒绝、禁止启动排队旧操作、晚到完成、普通错误后继续和名额复用。PlayerSession 在终局传递 PLAYER_TERMINAL，正常 release 仍为 RELEASED。测试中原先刻意悬挂的 attach 请求现在可拒绝，因此测试明确消费并检查该拒绝。

T016 的真实 NAPI session-budget 用例实现前失败；实现后标准 6 + 兼容 2 上限、保留独立兼容额度、后台析构未结束时不归还和真正结束后复用均通过。SessionBudget 对象置于 NativeSession 首个成员，在原生成员释放后才销毁。未改原有两个 OHCodec 名额。

新增队列首次 ArkTS 编译发现构造器参数属性不被支持，已改为显式字段与赋值；没有使用 any 或关闭检查。原生工作队列预算、mpv 内音频停用和故障归属尚待完成；这些基础不构成全局恢复验收。

第二轮统一门禁运行了 52 项，其中 diagnostics-session 因新队列及时拒绝改变了旧诊断请求的错误码而失败。保持原测试断言，在 PlayerSession 映射生命周期已变化的诊断为 DIAGNOSTICS_STALE，进程终局仍优先 PLAYER_TERMINAL；定向复验 diagnostics-session 和队列测试均通过。完整门禁需在后续原生恢复改动后再次运行，不把这轮标为 52/52。

## mpv 音频隔离进行中

新增 native/mpv/host_recovery.c 与头文件，以及 0004-host-audio-generation.patch 草案。登记表/代管理真实 C 测试覆盖旧代禁入、初始化在途、Stop 阻塞时新代及快照不阻塞、Stop/Release 失败不归还、16 槽上限、过期 token 和首次终局后不再次推进代。先缺失实现红测，再实现通过。

在独立临时 mpv 源副本应用本仓原有补丁，再接入新机制。audio-control.test.py 提取真实 stop_for_recovery/start/set_pause/reset 编译执行，先缺失 stop_for_recovery 失败，后通过正常暂停恢复、旧代禁启动、准备态及 Stop 失败测试。使用 OHOS SDK 对完整 ao_ohaudio.c、ohcodec_terminal.c 和新模块做语法编译通过；未做完整 mpv 链接。main.c 的独立语法检查因旧编译数据库 libplacebo include 路径失效而未完成，后续正式重建解决依赖路径。

草案尚未加入正式生产来源锁，也未接入公共恢复 ABI 和 native runtime；已有 HAR 中的 libmpv 没有改变。原音频中断完整回归需适配提取测试以涵盖新资源控制，不能声称本轮 mpv 已交付。待完成项包括回调音频数据与初始化/释放并发测试、复现来源构建、runtime 音频静止安全门与设备焦点验收。未修改 FFmpeg。


## 代际准入、队列与核心重建预验证

2026-11-11：gate-6 为 59 项通过，gate-7 为 61 项通过，gate-8 为 62 项通过，gate-9 为 64 项通过；这些是宿主门禁，不是目标设备证据。原 diagnostics-session 失败已修正，完整门禁后续通过。新增 native runtime 测试真实等待 3100 ms（旧期限 1000 ms）且 Stop 保持阻塞，进程仍存活、旧代始终拒绝；释放 Stop 后只允许新兼容代，核心代推进但 terminal record 尚未发布的窗口仍拒绝创建。旧/缺失恢复 ABI 被拒绝。

NAPI 与 ArkTS 的 preserve-host 已贯通：真实入口切片覆盖旧/新配置签名、参数截断边界、pending/ready/timeout 状态；真实 ArkTS 会话覆盖旧代失败、新代兼容播放状态及释放。原生 Callback 测试用 ASan/UBSan 验证旧代已排队事件不进入 JS，新兼容代仍可投递。真实 NAPI 清理入口能够保留旧代且析构新兼容代。底层 mpv 和平台仍用替身，不能据此声称实际音画已通过。

常规软件执行池 6、兼容执行池 2 与硬解池 2 分开；5 秒关闭超时不归还旧任务/会话预算，新兼容实例可处理命令。工作入口常规 32、关闭 8、恢复 8；预算同时由后台操作持有。恢复预留用例先因常规队列已满失败，接入独立池后复验。创建时 mpv_create/配置仍需专用执行审查，跨 NAPI 环境清理归属仍待实现，因此 T004 保持未完成。

独立临时输入逐文件校验 Phase30 A 的 mpv/依赖及已交付 FFmpeg SDK（217 项），应用既有与本轮 mpv 补丁并加入恢复模块；没有修改或重建 FFmpeg。OHOS SDK 完成 libplacebo + mpv ARM64 编译和链接，得到本地 libmpv SHA-256 `6f60048b51b814fbf8f0958966345dd818964d20a64d084c549d6b676db2d06e`。生产者旧静态门禁因只允许 4 个旧扩展接口拒绝新接口；在独立工具副本明确加入 4 个恢复接口、继续禁止内部 mp_host_* 导出后，62 个公开接口、原桥接 ABI 与 FFmpeg 闭包静态检查通过。没有把失败日志改成成功，也没有修改 ohos_ijkplayer 工程。该工具副本与重建输入尚待纳入本工程正式来源流程；库尚未替换交付目录。

以重建源码执行原 #89 音频中断测试：保留全部既有断言，接入真实恢复登记模块和新的释放返回值，再增加退休音频忽略中断断言，通过。#84 真实 Load/Stop/完成事件测试通过。本轮 HAR 已完成本地 ArkTS/native 编译；首次因匿名对象类型不符合 ArkTS 规范失败，改为命名 PlayerRecoveryStatus 后通过。此 HAR 仍含旧 libmpv，所以 preserve-host 会明确返回 RUNTIME_RECOVERY_UNAVAILABLE，不能交给 TV 当作新恢复产物。

仍缺：可靠故障会话/媒体归属、创建执行与跨环境生命周期、音频回调/释放更完整竞争验证、正式核心来源锁和交付更新、iMac CI HAR、目标设备恢复音画。没有 PR、没有新 CI HAR、没有 API 19 TV 通过结论。


## 跨环境、创建竞争与恢复容量

2026-11-11：gate-10 至 gate-14 的完整宿主门禁均通过；最新 gate-14 为 66 项，包含真实 NAPI 配置/创建/释放入口、父级保护与负向变异检查。本轮 MacBook Pro / arm64 本地 ArkTS/native 构建通过，未产生 CI 交付。

T020：环境 A/B 归属、同地址新环境、旧清理不得删除新登记、跨环境句柄拒绝、初始化中清理及迟到创建不发布通过。回调清理使用 ASan/UBSan，旧环境排队事件不得进入 JS，其他环境仍可投递。异步 complete 的早退曾漏掉 napi_delete_async_work，新增计数断言复现后修复；现在只归还 native work，不访问关闭环境的 Promise。

T021：create-timeout 红测曾阻塞超过 10 秒；mpv_create/Initialize 改为独立有界执行，5 秒返回且迟到对象不发布。已发布但未交付的创建被取消时收回 handle。ArkTS 捕获的运行代作为第六参数传到 NAPI，排队期间和跨桥调用期间退休均不得创建不匹配的新代。configure-timeout 红测超过 8 秒；使用全进程单配置执行器后 5 秒返回，其他请求保持可处理，真正完成后可重试。旧五参数创建调用仍兼容。

T022：occupied-compatible-pool 红测失败；此前两个旧兼容会话占满新代恢复名额。改为标准 6、旧兼容 2、新恢复 2，恢复额度只由终局后固定代的新兼容会话申请。旧兼容两个均保留时仍能新建两个恢复会话，第三个明确 SESSION_RESOURCE_LIMIT；新代正常释放后额度可复用，旧代没有被强制释放。

设备查询当前无连接设备；本地列有已停止的 API 19 TV 模拟器，尚未运行本轮验证。上述宿主替身测试不证明设备音画或系统焦点，也不证明新核心已随 HAR 交付。

## 音频数据回调竞争补测

以独立 mpv 源副本应用实际补丁，audio-data.test.py 在 ASan/UBSan 下运行真实 audio_on_write_callback。新增 during-query 先因时间戳 IPC 返回后仍调用旧 ao_read_data 失败；补退休检查后，normal、retired、retired-u8、during-read、during-query、fresh 六例通过。audio-control.test.py 对实际停止/暂停/恢复函数复验通过。该补丁变化尚未重新完整链接 mpv；前述本地 libmpv 哈希对应较早草案，不能代表此次变化。仍需初始化与释放更完整竞争验证、正式来源绑定、可靠故障归属、CI 和设备验收。


## 故障归属、加载回执及终局发布竞争

mpv 的加载命令、playlist entry 和解码帧携带 sessionId/loadGeneration；OHCodec 故障只取已持有 last_src。创建回滚、候选帧、不同实例身份均不猜测归属。故障快照以 ABI 0x00020000 独立扩展，不改旧终局记录 ABI。运行期保留最多 16 条故障，关闭 TSFN 后仍可记录；订阅重放、去重、取消和监听者异常隔离通过。gate-17 为 73 项通过；实际入口 fault-context/fault-snapshot、NAPI JSON 序列化及十个 mpv 修改单元语法编译通过。本地 HAR 编译通过；当时并未包含新核心。

T024 已按红绿流程补齐真实 PlayerSession/bridge 和 NAPI 入口测试：快速切集且旧会话关闭后仍能定位旧视频、原生队列拒绝后正确递增、身份回调抛错时取消加载、回调中发生终局时拒绝提交、无效来源以及旧一参数用法。真实 NativeSession Load/EOF 回归覆盖重复、倒退、空洞和安全整数边界。红测分别因缺回执、缺显式代、缺第六 NAPI 参数失败；实现后均通过。MacBook Pro / arm64 本地 HAR 构建通过，仍非 CI 交付。

完整 gate-18 的 80 项中，父级计时和汇总两项失败，不能记为通过：另一个观察者取得首写权时，当前快照的 firstObservedMs 可暂为 0。进一步确定性测试阻塞归属快照，复现旧状态仍被读为 ready 的窗口。T025 增加终局已观察标志，立即拒绝旧会话而不等待写者；完整元数据仍由 firstAt release 发布，音频恢复线程等待完整记录。父级测试只在有限 200 ms 内等首次时间，原有退出期限和负向变异断言保留。该确定性红绿测试已通过，完整 gate-19 结果另列。

修正文档整理时 evidence.md 被 data-model 内容覆盖的问题，恢复此前真实验证记录。当前仍缺完整新核心来源绑定、iMac CI HAR、实际设备音画与 API 19 TV 验收；没有以宿主替身或本地构建替代。

gate-19 完整 80 项通过（`/tmp/vidall-host-survival-host-gate-19/work/summary.json`），保留所有父级保护与三组负向变异校验。Spec Kit prerequisites 通过；宪章复查仍不勾选 CI/设备/整体资源验收。


## 锁定恢复核心与完整本地 HAR

2026-11-11：全量目标编译首次发现 vo_gpu_next 无 mapper 关闭路径遗漏 owner 故障入口（undeclared ohcodec_owner_fault）；保留入口并使用 unknown 归属，先补红测再实现。全新输入重建后完成 mpv/libplacebo ARM64 编译、链接、静态审计和构建后源树检查。输入 manifest SHA-256 `7699508b628c536b92685a6b561fba780b9f1b57c1793c0304aaa186bcbe9916`，libmpv SHA-256 `814e4f02ced52a15a213fd9a0c54f37ffbbe6ca466df758bd04ab0a9fa901beb`；64 个公开符号（包含六个恢复接口）、253 个链接输入、56 个 libplacebo 成员。实际机器 MacBook Pro / Darwin arm64，非 iMac CI 或云端 Mac。

Player 工程现维护输入准备脚本及导入的 mpv 构建/审计工具；补丁与新增源码逐项锁定，预编译 FFmpeg SDK 原始 217 项先全部校验，目标输入只覆盖 SDK，不构建 FFmpeg。七个准备脚本用例覆盖 SDK 符号链接转普通文件、正常替换、新源码、摘要篡改、路径越界和失败不留半成品。静态来源/ABI 审计通过；新增输入契约三例先红后绿，全部 31 个来源正负例通过。

同一派生源执行原 #89 中断回归，以及实际 OHAudio 数据回调/控制/生命周期函数。生命周期的 normal、create-fail、callback-fail、generate-fail、generate-block、release-block、release-fail、destroy-fail 八例在 ASan/UBSan 下通过：迟到初始化仍被计入 pending，失败释放保留回调宿主与预算，平台调用阻塞不持全局登记锁。仍不能因此认定真实焦点释放或平台 Stop 一定返回。

包含上述新核心的本地 HAR 已通过 `devecocli build --product default --modules vidall_player@deveco26`。该产物现真正含恢复 ABI，仍只是本地预验证，未交付 TV。主机八十项、真实入口测试、目标编译三层证据均不替代设备音画。当前无连接设备；已列出 API 19 TV 模拟器但本轮尚未执行。


## API 19 模拟器暴露的接口加载问题

API 19 TV 模拟器 `VidAll_Issue89_TV_API19` 安装本地九库 HAR，实际 HAP 的 libmpv 哈希匹配新核心，初始化却返回 RUNTIME_RECOVERY_UNAVAILABLE。不是旧库缓存：新库确有六导出及 ABI 0x00020000。首轮局部加载宿主测试在 macOS 下仍可通过 RTLD_DEFAULT；补全“全局符号不可见、同一依赖句柄可见”的平台边界后复现失败。T026 改为 dladdr 定位已链接 terminal ABI 的映像，RTLD_NOLOAD 获取同一库句柄，恢复 ABI 与 Load 扩展共用解析，不加载另一份核心。回归先红后绿；重新构建/安装后，模拟器同进程 PID 4282 已完成 runtime ready → 坏片 error → release → 新正常视频 firstFrame → 暂停/手动恢复。未退出、无崩溃记录。

完整 gate-20 共 81 项中只有 native-entry 未通过：测试在析构函数体刚进入时就认为预算已归还。已增加最后析构的完成标记，等待成员和预算实际销毁，再验证名额复用；未放宽生产预算。gate-21 全部 81 项通过。T026 后 gate-22 另行记录。

设备基础探针尚未整体通过：首次缺少媒体资源；补资源后定位接口加载问题；修复加载后长 GOP 合成素材在 seek 时落到 16.67 s，而旧探针预期 20 s 附近，得到 SEEK_NOT_ADVANCING。下一轮使用明确定义每秒关键帧的 30 秒合成素材匹配原 seek 用例前提，不把该失败删去。上述初步结果不含全局终局注入、不证明真机零拷贝，也没有对外宣称声音已验收。

gate-22 完整 82 项通过，包含新恢复输入及局部符号加载回归、父级保护和负向变异。完整本地 HAR 再构建通过；CI 与设备整体验收仍不升级。

API 19 TV 模拟器基础兼容探针最终在同一 PID 6143 完成坏片报错/释放、正常首帧、暂停/手动恢复、seek、释放重开及两个首帧，正常阶段 errors=0；实际 decoder=no / renderBackend=software。事件、HAP/HAR/素材/九库哈希保存在 `/tmp/vidall-host-recovery-api19-basic-evidence.json`。只验证该测试页及纯软件基础流程，不代表真实全局 GPU 故障、可听音频、系统打断或 TV 正式文件入口。


## 全局终局注入探针与 iMac CI

独立诊断 mpv/HAR 由 Player 的临时源码副本编译，正常目录和 CI 输入未替换。注入宏仅在该副本启用：首次加载 global-probe.mp4 后三秒进入真实进程终局管理器，不伪造真实 GPU/fence 故障。首次页面误将旧实例 release 的预期 PLAYER_TERMINAL 当成测试失败；修正页面接管，保留旧 Surface、创建新 XComponent/Surface 后复验。

API 19 TV 模拟器同一 PID 10749：首个视频首帧 → 已知身份 (1,1) 的 process-terminal → 旧音频停止后 recovery.ready/generation=2 → 拒绝旧实例操作 → 新 Surface 第二部素材首帧/进度增长 → 释放后第三会话首帧；最终 firstFrames=3、正常恢复阶段 errors=0。结束时距终局超过原 3000 ms 退出期限，主进程未退出，terminal 锁保持。当前诊断只覆盖软件旧会话及软件恢复路径；无可听音频、真实焦点、硬件零拷贝失败或正式 TV 文件入口的通过结论。证据见 device-evidence/api19-injected-global.json。

iMac 自托管运行器 yaoshiningdeiMac（macOS/X64/deveco）完成 Actions 43012213322，源提交 622ce07d3da274ebb9b55558590201412d859571。完整 HAR 构建/审计、独立消费者九库、缺失公共 API 负向编译及 Hypium 编译均通过；Hypium 未执行。原始 HAR SHA-256 `c092e1050c7c68b00a7fd4cee0033fae7c4b51ac2562274982fc9316df7f8274`，九库和运行器记录见 device-evidence/imac-delivery-622ce07.json。这是分支候选产物，仍非目标 TV 完整验收。

云真机访问尝试：T3 新页面可打开，但两次 snapshot 均在 15000 ms 超时；桌面浏览器 host unavailable，Dia 返回 cgWindowNotFound。已请求用户恢复前台可操作窗口，同时继续 CI 包模拟器验证；不能把此访问缺口写成真机通过。


## CI 原包模拟器复验及 T027 订阅回收

622ce07 的 iMac CI 原始 HAR 在独立消费 HAP 中九库逐项匹配，同一 PID 11889 完成坏片返回、正常首帧、暂停/手动恢复、seek 20 s、释放重开；firstFrames=2/errors=0。见 device-evidence/api19-ci-compatible-622ce07.json。仅为 API 19 TV 模拟器软件路径，尚未测试可听声音和真实系统中断。

T027 红测分别发现终局后仍保留 3 个闭包，以及连续创建失败/释放拒绝后仍保留 Player 的订阅。终局通知改为投递前移走本批，释放 Promise 结算后取消订阅；不改原生隔离、错误或成功释放状态。新测试覆盖重入、监听者抛错、100 次终局后订阅、100 次创建失败、未完成释放期间终局。完整 gate-23 共 85 项通过，本地 HAR 编译通过；没有把取消 JS 引用当作资源安全回收。

更新诊断页后严格核对旧 play/release 的 PLAYER_TERMINAL，修复 ArkTS 对任意类型 throw 的编译拒绝；只记录必要诊断字段，避免整份 JSON 被 hilog 截断。更新 ArkTS 源的独立诊断包在同一 PID 15071 完成三个首帧及新代进度增长，终局锁仍保持。见 device-evidence/api19-injected-global-listeners.json，其中明确列出 622ce07 基线之外的源文件摘要。诊断核心没有更换；旧静态 test 导出限制仍存在，不算正式 CI 产物。


## ccd253a CI 原包与打包目标复核

Actions [43014565922](https://github.com/yaoshining/VidAll_Player/actions/runs/43014565922) 已通过；源提交 ccd253a033fd891b8daaf6725dd1ac44c8da1242，实际运行器 yaoshiningdeiMac/self-hosted/macOS/X64/deveco。原始 HAR SHA-256 `b395e67f8ba0b77ee63d22f5c02c37cbe805bb35d0e8474c22b98a7649ebbec9`，完整 ARM64 九库及附件地址见 device-evidence/imac-delivery-ccd253a.json。核心仍由前述 MacBook Pro 构建，CI 负责完整 HAR 与消费者。该原包的独立 HAP 九库逐项匹配，同一 PID 24277 完成基础探针，firstFrames=2/errors=0，见 api19-ci-compatible-ccd253a.json。Hypium 是编译通过，不是设备执行。

核对本地诊断包时发现 PID 15071 的 default 目标还附带两个 x86_64 探针；原 JSON 保留实际十一库并补充说明，不宣称支持 x86_64 播放。改为 deveco26 目标后，PID 20503 的独立诊断 HAP 确认为 ARM64 九库，终局后的新代续播/释放重开仍通过，见 api19-injected-global-deveco26.json。正式 CI 一直使用 deveco26，未受该本地诊断目标误选影响。

后续提交只补充这些证据与构建说明，不改变 ccd253a 的产品代码、测试或原生输入。目标 OHCodec/Vulkan 真机、可听音频、系统打断/焦点、硬件连续隔离上限及 TV 正式文件入口仍未验收。平台 Stop 永久卡住时不能安全开放恢复代的问题仍是明确限制，未将 R3 改成“只保活、不续播”。


## PR 工作流预跑与 T031 静态合同修正

本地预跑主 PR 工作流的 27 组合同测试，26 组通过；har-native-packaging.test.py 的静态门禁失败，仍硬编码旧四参数 createSession 声明。先保留该红测，并扩展负向变异，随后修正为当前可选 playbackMode/runtimeGeneration 合同。8 个归档/ELF/静态测试全部通过，仍拒绝同步返回、删除恢复参数及将可选扩展改成必填。证据在 /tmp/vidall-host-survival-pre-pr-contracts/summary.json 与 /tmp/vidall-host-survival-har-contract-red.log；这是本地工作流预检，不是 GitHub 已执行该 job。

同轮实际 Vulkan 尺寸测试 20 例和 GL 重绘平台替身测试通过。旧 14 项 CTest + 2 项 JS 的封装脚本因正在修改的 tracked 工作区不干净而主动拒绝，尚未运行；没有跳过源树一致性门禁，待本轮代码提交后复验。


可用设备能力复核：使用 ccd253a CI 原始 HAR，仅把独立探针的播放模式改为 standard，API 19 TV 模拟器同一 PID 25923 完成坏片返回、正常首帧、暂停恢复、seek 和释放重开，firstFrames=2/errors=0。实际 diagnostics 仍为 software/no，符合模拟器缺少 vendor GPU 栈时的选择；不能证明 OHCodec/Vulkan，也不代表尚在修改的 T029/T030 新包。哈希与日志见 device-evidence/api19-ci-standard-ccd253a.json。


## T030–T032 本地收尾（2026-11-11）

T030 实际回调 ASan/UBSan 19 例、队列溢出后的实际 NAPI 准入/释放、跨媒体 epoch 失败及监听者异常隔离通过；独立只读复核未发现新增明确缺陷，见 resource-audit.md。目标 ArkTS 首轮因 PlayerFailure 传入 Error 参数触发结构类型限制，改为显式 Error | PlayerFailure 联合后，原队列/事件回归和 deveco26 HAR 编译通过；没有添加强制转换或降低编译检查。

首次完整宿主门禁共 90 项，85 项通过，父级链和三组负向变异及其汇总因旧夹具未声明 callbackMailbox_ 编译失败。已用真实 EventMailbox 补齐夹具，保留原销毁保护、86 退出期限及负向断言；随后完整复跑结果另列。

T032 新增 0006-isolate-legacy-audio-callbacks.patch（SHA-256 d35a126644500e410e79b81fcea80e5f5536ec524e07083ade489f99ebe1893e），只改变 Player mpv 的旧音频回调登记。从封存基线完整派生输入，清洁目录重建 mpv/libplacebo，FFmpeg 使用原预编译 SDK且六库不变。输入清单 SHA-256 0ccb801d27b802ea05b97cfff114d01768562b18b2fe2cfe97cfc675f477fb80；新 libmpv SHA-256 46cd4112ac963a935773d70fe8fec4254753c9ceade6f546c6433c40318815e7，64 个导出及恢复 ABI 不变；libplacebo 静态库哈希不变。机器仍为 MacBook Pro / Darwin arm64，这不是最终 iMac CI HAR。

完整构建的输入不变、实际编译命令、链接输入、静态验证和来源锁已更新，normal-core-verify --verify-external 与 31 个输入正负例通过；本地 deveco26 HAR 编译通过。producer 输入门禁先拒绝新哈希，核对上述完整目标构建及冻结补丁后才更新精确锁，继续保留“未来输入变化拒绝”与“未验证最新完整云端重建”的标记，未放宽规则。

T032 最终本地统一门禁：`/tmp/vidall-host-survival-host-gate-t032/work/summary.json` 共 90 项全部通过，含父级真实关闭链、三组负向变异及公开日志检查；当前完整 HAR 含 ARM64 九库，libmpv 为上述新哈希。旧 14 项 CTest/2 项 JS 要求干净提交快照，将在提交后执行，尚未将其写为通过。

提交 bed3bdb 的旧门禁实际 14 项 CTest 均 Passed，但汇总脚本只认旧格式而拒绝，后两项 JS 尚未运行。T033 新增解析红绿测试后兼容本机 `100% tests passed out of 14`，同时拒绝跳过、禁用、失败及错误计数；4 项包装器测试通过。完整门禁随后用新干净提交复跑，不把首次汇总失败记作整体通过。


## 8ca9bef CI 与 API 19 软件复验（2026-11-11）

- 干净提交 8ca9bef 的旧宿主包装器完整通过：14 项 CTest 和 2 项诊断 JS，记录在 `/tmp/vidall-host-survival-legacy-8ca9bef/work/legacy-native-result.json`。
- Ubuntu 工作流 43021149158 全部通过：锁定交付音频源码、原中断、新 legacy 生命周期、audio-data/control/lifecycle、尺寸/旋转/软件绘制/播完及完整旧宿主回归。
- iMac 自托管工作流 43021111873 全部通过，实际 runner 为 yaoshiningdeiMac / macOS X64；包含完整 HAR、独立消费者九库、缺失 API 负例和 Hypium 编译。Hypium 未在设备执行。原始 HAR SHA-256 为 d9ecad900726510c56f72dd2f4496b6827851a4736d7577ee51e172e721d4937，详见 device-evidence/imac-delivery-8ca9bef.json。
- 原始 CI HAR standard 探针：API 19 TV 模拟器 PID 29677，坏片失败返回、正常首帧、暂停/手动恢复、20 秒跳转、释放重开，2 次首帧、0 探针错误。模拟器实际 backend=software、hwdec=no。
- 同一原始 HAR compatible 探针：PID 3526，上述路径再次通过，2 次首帧、0 探针错误；签名 HAP 九库逐一匹配原始 CI HAR。
- 当前桥和 T032 核心的独立本地诊断包：PID 2479，定时进入真实全局终局管理器，旧操作拒绝、约 150 ms 后恢复代 ready、新 Surface 连续两次软件播放，合计 3 次首帧、0 探针错误；超过原 3 秒退出期限后仍为同一 PID。硬解锁持续 terminal。诊断 HAR/库哈希与正常 CI 原包分开保存，且原诊断静态验证器仍因历史测试导出断言失败；不称其为正式门禁通过。

以上没有证明实际可听音频、系统焦点抢占/手动恢复、GPU/fence 故障或 API 19 TV 正式文件入口通过。T3 浏览器打开及登录请求均返回 parent_not_active（The calling provider no longer owns an active thread run），Dia 原云调试登录页已关闭；当前无法继续云真机操作。未提交 PR，T007/T009/T013/T017/T018 保持未完成。

## T034 诊断静态 ABI 门禁修正（2026-11-11）

旧诊断构建确实在 `validate_one.py` 的公开符号数量断言失败：编译宏使验证器额外要求已移除的 `mpv_ohcodec_handoff_test_waiting`，当前注入仅使用内部函数。新增 4 组契约测试覆盖完整 ABI、逐一缺失的 64 个符号、废弃/额外/内部导出及错误基线清单；先失败后通过。正式包故障宏禁令保持不变。

用新验证器只读重验原 T032 两份 ELF：正常核心 46cd4112… 与诊断核心 68dd9ede… 均通过，64 个公开 mpv 符号、247 个 FFmpeg 导入及原 OHCodec/Vulkan 注册和调用检查完整保留。诊断内部 `host_probe_enter` 的真实终局调用地址已验证；正常核心不存在该注入函数。输出分别在 `/tmp/vidall-t034-normal-validation` 与 `/tmp/vidall-t034-diagnostic-validation`，旧失败日志与二进制未改写。这是新的静态证据，不补称旧完整构建已通过，也不产生新的设备验收结论。


## T035 音频清理与恢复准入分离（2026-11-11）

真实音频生命周期红测复现“renderer 已释放而 builder 清理失败仍永久 pending”；旧控制锁竞争红测复现扫描阻塞。10 项生命周期 ASan/UBSan、音频域 ASan/UBSan、实际数据/控制/中断与 legacy 回归通过，独立只读审查未发现新增明确缺陷。补充普通控制锁忙→扫描返回→解锁→下一轮真正 Stop 的回归，旧实现失败、新实现通过。原始日志在 `/tmp/vidall-audio-t035-red-{destroy-fail,control-busy,domain}.log` 和 `/tmp/vidall-audio-t035-green-{lifecycle,domain}.log`。

锁定输入 60e24caba7b2bbd5cfc72dd572fcd5f5c747ac09343d6e75bf345e3a6413a650 在 MacBook Pro / Darwin arm64 完整构建 mpv/libplacebo，所有编译、静态检查及输入不变检查通过。mpv SHA-256 为 5aa3d663b13289a7d6ab7ede6a0ac40dbd42b37642c9a93d0da11dc71f445b79，公开符号仍为 64，libplacebo 哈希不变；FFmpeg 预编译六库未修改或重建。完整宿主、HAR 与 CI 结果在后续完成后补记，不预先沿用 8ca9bef 的通过结论。

T035 本地完整统一门禁共 91 项全部通过，外部来源审计、31 项来源正负例、2 项交付锁测试通过。完整本地 HAR 构建通过并核对 ARM64 九库；mpv 为 5aa3d663…，本地 HAR 哈希 873d7c776cdd24a15241bec4773bab96dbeea521be72986b21392a97b5bc9d5e，仅供预验证。CI 原包与设备结果仍须补齐。


## 01b2ad3 CI 与 API 19 软件复验（2026-11-11）

- iMac 工作流 43024630552 完整通过；实际 runner yaoshiningdeiMac / self-hosted / macOS / X64。原始 HAR 为 fddf4216751e9899594cc439fd304edf64c428f58b59b5d12055198237d350b3，附件 13856632429，九库逐一核对。Ubuntu 工作流 43024633104 的新旧音频、尺寸/旋转/播完和完整宿主回归通过；本地干净提交 14 CTest/2 JS 也通过。
- CI 原包 standard / compatible 在 API 19 TV 模拟器分别保持 PID 23135 / 20202，坏片返回、首帧、暂停/手动恢复、20 秒跳转、释放重开均通过，各 2 首帧、0 后续探针错误；实际 software/no，不代表系统音频打断。签名 HAP 九库完全匹配 CI HAR。
- 新独立诊断核心 bb4e8760… 已通过完整构建、静态及来源检查；诊断 HAR d78e84b7… 在 PID 5131 注入终局后保持宿主、新 Surface 两次续播、总 3 首帧。正常/诊断包分别记录，不修改 CI 原包。
- T035 的 builder 失败/阻塞只在宿主真实函数回归注入；这次模拟器注入的是全局终局管理器，不能把二者混为同一次设备验证。仍缺真实 OHCodec/Vulkan、可听音频/系统焦点、连续硬件隔离上限和 API 19 TV 正式入口。平台 Stop/Release 永久不返回时的恢复限制仍未消除，未提 PR。

T034 最终边界复查另补版本别名负例：先复现额外 mpv_initialize@UNEXPECTED 被去重隐藏，再保留原始导出条目计数，5 组契约测试通过；当前正常 ELF 完整静态重验通过且输出与原结果逐字节相同。此项只收紧检查和更新检查器来源锁，不改 01b2ad3 的播放器源码、核心或 CI HAR；没有将后续验证记录提交冒称为 HAR 源提交。


## T036/T037 硬件验收探针准备（2026-11-11）

先补 S14/spec、plan、tasks，再实施三项真实流程/页面回归。T036 首次红测复现首片仍固定 compatible；后续红测覆盖清理失败仍写 summary、终局后新兼容会话漏释放、旧首帧串到新会话、B/C 复用 Surface。修正后首片默认 standard 且必须实际 OHCodec/Vulkan，三个实例分别使用独立 Surface；离页取消异步创建，旧回调按实例代拒绝，新兼容会话即使全局 terminal 仍释放。公开 API 和生产实现不变。

T037 使用真实 mapper close/wait 接缝，保留 owner 隔离，不用关闭生产保护制造 global 故障。独立 fault 历史核对 A/C 不可变身份；B 晚关闭要在本轮同 PID 原始日志确认完成后才允许 C，并由 C 实际硬解再次证明名额归还；两个隔离名额用尽后 D 请求 standard、实际必须 hwdec=no。页面返回、独立 Surface、UI 心跳、离页交错和成功摘要边界已有红绿回归。`release()` 完成始终不是安全回收证明。

- 三项新自动化和完整统一门禁 94/94 通过，见 device-evidence/host-gate-t037.json。独立只读审查指出的五项探针缺陷均已回归修正。目标 ArkTS 初轮分别指出接口方法对象字面量和任意类型 throw 不允许；改为明确函数属性及 Error 后编译通过，没有跳过类型检查。
- T036 最终 hardware-first 在 API 19 模拟器 PID 17950 实际 software/no，正确报告 HARDWARE_PATH_REQUIRED，无成功摘要。显式 software-control 在 PID 20091 收到全局终局后保持进程，旧操作拒绝，恢复代 2，B/C 两个独立新 Surface 续播，共 3 首帧、复播错误 0。两份 HAP 九库逐一匹配原独立定时诊断 HAR d78e84b7…，见 api19-t036-hardware.json / api19-t036-software.json。
- T037 输入副本仅改变 mapper 注入与 Hilog 链接依赖；package SHA-256 8ce987d3f6119b8052a52c98e6a9fd0d1da89ace47f233c3c499dddd455f03b9。MacBook Pro / Darwin arm64 完整重建 mpv/libplacebo、精确 64 导出和静态检查通过；mpv 为 b0ae948109746913e55bfbd5eacf0f5108b9651a66f761a9f22b0d84d047087e，FFmpeg 六库未改。Player 工程完整诊断 HAR SHA-256 26453c1f25e93862b312ef65e22d1b80b464a6d078983a7ffed79b61c4579e3e，非 CI 交付。独立消费者原包接入后，PID 16510 在 software/no 正确拒绝硬件门槛，未触发 mapper 注入，见 api19-t037-fence-negative.json。
- 6b4dfe5 的 iMac 工作流 43026349300 已完成成功；正式交付记录仍明确绑定原候选 01b2ad3。本轮只新增验收准备、测试和记录，不改变正常核心或 FFmpeg，也不把本地诊断 HAR 当作 iMac CI 原包。

T036/T037 作为“验收准备”完成，不关闭 T007/T009/T013/T017/T018。当前可连接设备仍只有 API 19 TV 模拟器；没有真实 OHCodec/Vulkan 正向、可听音频、系统焦点/打断、真实硬件隔离上限或 VidAll_TV 正式入口结论，尚未提交验收通过 PR。已有平台 Stop/Release 永久不返回的明确限制未被本轮探针掩盖。


## T038 宿主测试的 Linux C11 兼容性（2026-11-11）

1e074cf 的 iMac 工作流 43030767166 全部通过。手动 Ubuntu 全量宿主工作流 43030937319 首轮失败：93 个已执行步骤中仅 audio-domain-compile 失败（随后 audio-domain 未执行），原因是严格 C11 下 usleep 未声明；三项新探针回归全部通过。原 CI 失败保留，不把本地 94 项通过改写为该次 CI 通过。

仅将 audio-domain.test.c 的毫秒等待改为显式 POSIX.1-2008 nanosleep 并重试 EINTR；原控制锁、旧代音频、资源上限和过期 token 断言全部保留。相同 C11/-Wall/-Wextra/-Werror 命令在本地编译及运行通过；完整 Ubuntu 复验待后续工作流结果。此修改不涉及生产 mpv、FFmpeg、公开 ABI 或硬件验收结论。


## T039 精确宿主检查清单（2026-11-11）

656f602 的 Ubuntu 工作流 43031817245 中 94 项测试全部成功，最终 assess 仍因 ci-evidence.py 硬编码49项而失败；iMac 工作流 43031742457 全部成功。新增精确 host-checks.json（名称→expectedExit），完整匹配94项，不能用同数替换或新成功项抵消缺失项。

先以94项成功fixture复现旧汇总拒绝，再保留10种完整性负例：缺失、额外、重复、同数替换、跳过、禁用、改预期退出码、失败项、摘要失败、缺日志，以及原源码变化拒绝。29项 CI 合同测试通过；真实 Ubuntu 94项摘要在新检查器下只读核验通过，原工作流失败状态未改写。完整 CI 复验仍单独记录；未改变生产/平台行为。

T039 首轮远端复验 43032827813 attempt 1 在依赖安装阶段失败：Azure Ubuntu 镜像 DNS 解析失败（Temporary failure resolving azure.archive.ubuntu.com），退出100，合同和宿主测试均未执行。没有修改依赖来源或跳过门禁；仅重跑该失败 job 并保留原尝试日志。对应 f0bf68b 的 iMac 工作流 43032804843 已成功。


## T041 Stop 返回后的停止状态确认（2026-11-11）

按 S15 先扩展真实 `stop_for_recovery` 提取测试及音频生命周期测试。使用 T035 锁定源运行新用例，两项均红：Stop 返回 `AUDIOSTREAM_ERROR_ILLEGAL_STATE` 后直接返回，未执行第二次状态查询；即使平台替身已进入 STOPPED，旧槽仍为 pending。原始红测分别保存在本机 `/tmp/vidall-audio-t041-control-red.log`、`/tmp/vidall-audio-t041-lifecycle-red.log`，这不是实际设备上发生同一错误的证据。

新增 Player mpv 补丁 `native/patches/phase30/0008-confirm-returned-audio-stop.patch`，SHA-256 `dc7a638a2a7bcbe0fac0ed57a7f3aaff7173e67648075ecf702d031e14723bc7`。最小修改是在 Stop 已返回后继续原有状态查询，仅明确 STOPPED 才确认静止；不重试 Stop、不调用 Release，不改变旧代控制锁、quiescence 发布、资源预算或硬解终局锁。派生 `audio/out/ao_ohaudio.c` 的 SHA-256 从 `2f786bc3d4745e2dcf14ea127719a678d5faddf34f6c70951387a40d2c4f51ae` 变为 `69d5e06197000ebbf709e2a66f45438100701be092df49051cb888f2c082fa2e`。

本地主机真实函数提取回归结果：

- 6 个控制场景在 ASan/UBSan 下通过：原正常控制、Stop 返错但后查 STOPPED、返错仍 RUNNING、后查失败、后查仅 PREPARED、Stop 阻塞。阻塞用例确认 Stop 未返回期间只有第一次状态查询、pending 保持且扫描未结束；返回后才执行第二次查询。重复扫描不再次调用 Stop。
- 11 个生命周期场景在 ASan/UBSan 下通过，保留原初始化、Release/Builder 失败与阻塞、并发清理断言；新增 Stop 返错但确认 STOPPED 后可按原顺序释放、预算正常归还的场景。
- 8 项输入派生检查通过。新增用例通过 `prepare-host-recovery-input.py` 的真实 `prepare()` 入口按来源锁应用实际 0008 补丁，确认源输入不变、派生清单记录补丁，以及补丁篡改时拒绝发布目录；未增加跳过来源锁的入口。

对应命令为 `python3 -B native/tests/host-survival/audio-control.test.py /tmp/vidall-audio-t041-source`、`python3 -B native/tests/host-survival/audio-lifecycle.test.py /tmp/vidall-audio-t041-source`、`python3 -B native/tests/host-survival/prepare-input.test.py`。绿测日志为本机 `/tmp/vidall-audio-t041-{control,lifecycle,prepare}-green.log`；本机索引 `/tmp/vidall-audio-t041-evidence.json` 记录全部日志及修改文件哈希。这些 `/tmp` 文件是本地临时证据，不是仓库已提交附件，不能据其存在宣称 CI 或设备验收通过。

0008 已纳入正式来源锁并成功派生完整输入，`package.json` SHA-256 为 `5d223ee219cc9ebdffb00101ece9cdc1112835dd24b04bfa6d929bf8d1236dbb`；派生源摘要已与上述实际测试源核对一致。完整 mpv/libplacebo 构建、来源审计、HAR 与 CI 结果由后续记录补齐，本段不提前宣称通过。FFmpeg 仍消费原预编译 SDK，未修改或构建。

本修复只消除“Stop 已返回错误，但随后已能明确确认停止”的误拒绝。Stop 永久不返回、返回后仍活动或状态查询失败时，不能仅据观察超时伪造 ready；Renderer Release 未确认且没有其他已确认的静止事实时，同样保持拒绝。T035 已确认 Renderer Release 后的 Builder 失败处理，以及已确认静止不因后续清理失败而撤销的规则保持不变。真实系统声音、旧新音频不重叠、焦点释放/打断与手动恢复、OHCodec/Vulkan 故障及 API 19 TV 正式文件入口仍未验收，T007/T009/T013/T017/T018 保持开放。

### T040 工具选择与 T041 核心重建预验证

- T040 11 项真实进程选择器测试、手动工作流 14 个及自动工作流 35 个变异均通过。三个工具完成可执行性、成功退出及明确 LLVM18 版本检查后才写入 GITHUB_PATH；失败仍安装并复检。未跳过 npm、LLVM_NM、94 项宿主或最终收证。远端完整结果待追加。
- T041 从锁定输入重新交叉构建 mpv/libplacebo，实际机器为 MacBook Pro / Darwin arm64。输入包 SHA-256 `5d223ee219cc9ebdffb00101ece9cdc1112835dd24b04bfa6d929bf8d1236dbb`，libmpv `ee78bf290d9697ff825eb3f4590d09120474834eec9edb11eb53ea83fbcb5267`，64 项公开导出。仅启用 handoffTrace，所有故障注入/实验宏关闭；非 mpv 运行库逐字节不变，FFmpeg 未改动或重建。
- 正式源码派生、静态外部依赖审计、31 项正常核心来源测试、2 项生产输入测试及 8 项恢复输入测试通过。本次构建源码的音频中断、旧回调、数据、控制及生命周期回归通过，后两项包含 ASan/UBSan。
- 完整本地 HAR 编译通过，九个 ARM64 库；本地 HAR SHA-256 `59e97d0a126160ed2771747cb79ded3bbbb4c890e685e5ff2481f5b22ff2ab35`，只作预验证，最终交付仍须使用 iMac Actions 原始 HAR。
- 只读独立审核未发现阻塞问题。Spec Kit 前置检查通过；对照宪章第四/六/八/十条复核：主线程不新增阻塞、资源预算与静止事实不放宽、先红测再实现、源/构建/设备分层。R3、T007/T009/T017 的真实硬件和音频验收仍未完成，不用本地或 CI 结果替代。

T041 最终本地统一门禁 94/94 通过（`/tmp/vidall-host-survival-host-gate-t041/work/summary.json`），含真实 NativeSession 入口、进程终局和父链变异拒绝。远端 CI 仍独立记录。

### T039–T041 远端 CI 与当前诊断复验

源提交 `d4a059b3117a23d70aa0832d00ed7161fd8c6d5a`：

- [完整 Ubuntu 门禁](https://github.com/yaoshining/VidAll_Player/actions/runs/43038250441) 成功，包括94项宿主及最终收证。实际工具路径 `/usr/lib/llvm-18/bin`，clang/clang++/llvm-nm 均18.1.3；先前两次 apt DNS 失败保留为失败历史。
- [音频及既有功能回归](https://github.com/yaoshining/VidAll_Player/actions/runs/43038251489) 成功，包含当前锁定音频源、音频中断/恢复、尺寸/旋转/播完、14项CTest和2项JS。下载音频身份记录确认 mpv `ee78bf…5267` 与 ao_ohaudio.c `69d5e0…fa2e`，与交付输入完全一致。本地干净提交的旧宿主套件也通过。
- [iMac HAR 流程](https://github.com/yaoshining/VidAll_Player/actions/runs/43038228044) 成功，包含完整HAR、缺失公共API负例、独立消费者九库及Hypium编译。实际运行器 `yaoshiningdeiMac`，非云端Mac；原始包下载核验记录另见最新交付文档。
- [当前诊断包的API19模拟器复验](device-evidence/api19-injected-global-d4a059b.json)：同一PID21377，终局退休旧代，ready generation2，独立新Surface连开两会话，共三次首帧，恢复后错误为0。诊断HAR为本地完整构建，SHA `6d79c863a73be3f852186be90710ae49e3038ef8fe7851a28813e6a6693bfedf`；仅software-control/定时注入，未替代真实硬解、可听音频及TV正式文件入口验收。

当前 iMac 原始 HAR（SHA `a8ce9ee5d73a47ed4a4eed0f9fdb22664cc4db7b43a34fbf0aecc625ab3da1d3`）已分别以 standard/compatible 整包接入独立消费工程，在 API19 TV 模拟器通过坏片失败、后续首帧、暂停恢复、seek、释放重开；每组两次首帧且后续错误0。HAP九库与原HAR逐库完全一致。具体PID/包/素材/fixture哈希见 `device-evidence/api19-ci-{standard,compatible}-d4a059b.json`，仍为软件路径和探针入口。
