# Issue #79 真机与自动化验证记录

验证日期：2026-09-23。设备：华为智慧屏 MateTV Pro，HarmonyOS API 24 Release。SDK 0.1.0 未发布候选，schemaVersion=1。

## 结论

2026-09-23 原版运行库候选原始报告为 **19/19 检查通过**（其中表面场景只做重新绑定，不构成真实组件重建验收；直播断言存在下述覆盖缺口），9 次原生首帧事件，0 个播放器错误事件。使用 SDK demo 的独立诊断页，未安装、改写或清理 VidAll_TV 包与配置。

- 本地 H.264 640×360、25 fps、AAC 48 kHz 双音轨的参数与 ffprobe 一致。
- 区分输入 floatp 与音频 API 输出 float，立体声切换到第二条单声道轨道后 channels 更新。
- 暂停位置稳定、恢复、seek 至 20%、HTTP 网络、关闭缓存、stop 在途请求拒绝及停止后旧值不可用通过。
- 无音轨、无视频轨、无长度 MPEG-TS 流、连续重开、surface generation 1→2 重新绑定、release 后拒绝读取通过；旧直播断言未拒绝所有错误状态，也未检查 progressPercent 的估算标记。
- 原版运行库快照为 `hardwareDecoder=no`、`renderBackend=vulkan`，准确反映软件解码 + Vulkan 输出。
- 独立 OHCodec 对照使用 `76d3bd5c84a3431a7873daeb3fcba940942804c6` 的 libmpv 与六个 FFmpeg runtime：真实快照为 `hardwareDecoder=ohcodec`，与 [原生日志](evidence/diagnostics79/ohcodec-native.txt) 一致；暂停、seek、切轨、切源等也通过。此轮直播断言发现下述估算标记问题，不能称为该轮全部通过。修复后由最终原版运行库 19/19 复验覆盖。临时替换的七个库已按原始 SHA-256 逐一还原，没有合入独立 OHCodec 变更。

## 真机发现并修复

1. 三项缓存字节原先以斜杠属性读取，全为 error/read-failed。锁定版本只支持整张 `demuxer-cache-state` NODE_MAP；改为一次读取再提取成员，保留 int64 精度。未开启磁盘缓存时缺少成员，返回 unavailable/not-present。修复先加入失败的 map 成员回归测试，再实现通过。
2. 无长度直播流实际返回动态估算 duration，旧快照误标 `estimated=false`。对照锁定版本文档，duration 和 percent-pos 都可能估算，现均标为 true；不伪造 unavailable，也不把它解释为已知总时长。回归测试先因旧标记失败，再实现通过。

初次素材放错 app base/cache 导致探针 timeout，随后改为 entry 模块缓存；切源时出现预期的 DIAGNOSTICS_STALE，探针按契约重试。这两项属于验收工具修正，不计为播放器缺陷。

## 性能样本

受控 640×360 H.264 素材，三个窗口各 15 秒，开启时约 1 Hz。每个窗口边界各读取一次快照以测量位置/丢帧，因此关闭窗口表示“无周期采样”，并非完全零调用。

| 窗口 | 周期采样次数 | App CPU 均值 | PSS（KiB）范围 | 调用耗时中位数 / P95（ms） | 输出丢帧 |
|---|---:|---:|---:|---:|---|
| sampling-off-before | 0 | 1.154% | 93807–94375 | 0 / 0 | 0 → 0 |
| sampling-on | 15 | 1.018% | 94341–95312 | 2 / 3 | 0 → 0 |
| sampling-off-after | 0 | 1.029% | 95658–95926 | 0 / 0 | 0 → 0 |

原生采集耗时中位数 1 ms、P95 2 ms。CPU 使用 HiDebug getCpuUsage 原始比值乘 100；PSS 来自 getAppNativeMemInfo。内存数据同时包含探针保留的快照/报告，三个短窗口不能证明长期无泄漏，低负载结果也不能外推到 4K/DV。没有观测到该样本上的输出丢帧增长。

## 可复核材料

- [最终真实快照及逐项断言](evidence/diagnostics79/final.json)
- [修复前缓存失败快照](evidence/diagnostics79/before-fix.json)
- [OHCodec 对照及直播估算发现](evidence/diagnostics79/ohcodec-before-duration-fix.json)
- [ffprobe 源参数和素材 SHA-256](evidence/diagnostics79/fixtures.json)
- [原版运行库指纹](evidence/diagnostics79/original-runtime.json)、[OHCodec 对照运行库指纹](evidence/diagnostics79/ohcodec-runtime.json)
- [TV 实际播放截图](evidence/diagnostics79/playback.jpeg)
- [探针与复现流程](../scripts/test/diagnostics79/README.md)

网络为本机 HTTP 服务经 HDC reverse TCP，仅提供合成素材，不含私有媒体、来源 URL 或认证信息。它验证 HTTP 播放/缓存路径，不代表 SMB、WebDAV、公网或真实 Wi-Fi 带宽测试。所有报告保留固定技术字段，文件名和标题为 unavailable/redacted。结束后已停止 SDK demo 和本次两个本机媒体服务，移除两条 reverse TCP 规则与六份测试缓存，fport ls 确认 Empty；未重启全局 hdc。

## 自动化与产物

- CTest 13/13 通过；含新增缓存 map 成员缺失/类型错误/有效零值及估算标记回归。
- 主机会话测试与探针断言测试通过；主机 NAPI 使用替身，与上面的实际 TV 报告分开。
- CodeLinter 使用实际 SDK 24 / 6.1.1 检查 20 个文件，0 defects，无检查错误；未改动项目 target/compatible 配置。
- `devecocli build --modules entry@default vidall_player@default` 成功，最终 HAR 单独重打包成功。
- `git diff --check` 通过。

当时的 HAR 输出位置：`packages/vidall-player/build/default/outputs/default/vidall_player.har`（后续构建会覆盖，此摘要仅对应本轮历史产物）。

SHA-256：`3dc5f8b4641b2ec93d62869858fc3b0b673e34069042a8debea62735ca9fe698`。

## 保留边界

未验证 Dolby Vision/HDR 素材、4K 长时压力；该电视策略固定选择 Vulkan，没有通过改动后端策略强制测试 OpenGLES/SW 渲染路径。硬解对照依赖独立 OHCodec 修复，不将原版 HAR 宣称为已具备该修复。PR 保留草稿、不自动合并；上述边界应在消费端/渲染发布验收时补充。

## 2026-09-24 同步 main

当前分支已合入 PR #81 的合并提交 `54e4b17`。诊断 API、缓存读取与估算标记修复以及 OHCodec 恢复现已进入 main；本 PR 剩余变更主要为探针、测试接入与上述历史验收证据。

同步后 CTest 14/14、诊断会话测试与探针断言测试通过，`devecocli build --modules entry@default vidall_player@default` 成功。本次同步未重新部署真机，上述 19/19 结果仍只对应记录中的运行库指纹。#81 配套运行库的独立 H.264 真机证据见 [OHCodec 真机验收](ohcodec-device-validation-20260923.md)；构建成功不能替代新组合的真机验收。

## PR 审查后修正

旧探针重复使用同一个 XComponent 和 NativeWindow，历史 `surface-rebuild` 记录仅证明重新绑定，撤回真实表面重建通过的结论。新探针等待 XComponent 的 onDestroy，再创建新控制器和组件，等待 onLoad，检查不同表面 ID、generation=2 的首帧和诊断快照。该新场景尚待真机重新执行，不能沿用旧 19/19 作为通过证据。

直播断言现在只接受 fileSizeBytes=unavailable；durationMs 与 progressPercent 各自必须 unavailable 或 available 且 estimated=true，error/unsupported 均不通过。尺寸验证要求 available，偶数样本中位数改为中间两项平均值（历史 15 样本窗口不受影响）。回归测试覆盖失败状态、旧值、估算回归、奇偶样本和表面证据缺失；CI 同时覆盖入口与页面清单路径。

## 2026-09-24 审查修复后真机复验

在 MateTV Pro / API 24 上部署本分支探针与 #81 配套六库。第一轮 18/19：XComponent 已真实销毁并重新创建，但公开 firstFrame 事件漏传 surfaceGeneration，探针正确拒绝通过。保留 [失败报告](evidence/diagnostics79/retest-before-firstframe-fix.json)。先增加可复现的会话测试，再在原生事件转译处传递已校验的 surfaceGeneration；过期表面事件仍被拒绝。

修复后完整重跑 **19/19 通过，9 次首帧，0 个播放器错误**。新表面 ID 从 `5132485918822` 变为 `5132485918823`，onDestroy/onLoad 完成，收到 generation=2 的首帧及诊断快照。直播 durationMs 与 progressPercent 均 available 且 estimated=true，fileSizeBytes 为 unavailable/not-ready。此次结果替代旧探针在这两项上的验收缺口。

- [最终报告](evidence/diagnostics79/retest-final.json)
- [实际安装 HAP、库和素材 SHA-256](evidence/diagnostics79/retest-runtime.json)
- 15 次采样耗时中位数 3 ms、P95 17 ms；这是受控低负载窗口，不外推 4K/DV 或长期表现。
- CTest 14/14、会话与探针回归测试通过；修复后 HAP/HAR 构建与安装成功。
- 结束后停止 SDK demo、两个本机服务并移除本轮反向转发，清理三份测试缓存；本地六库按备份 SHA-256 恢复。未改动 VidAll_TV 包或数据。

HEVC/HDR/DV、4K 长时及其它渲染后端仍不在本轮范围。
