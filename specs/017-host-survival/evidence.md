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
