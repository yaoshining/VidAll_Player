# G1--G3 负责人确认归档

| 门禁 | 当前状态 | 书面确认引用 | 已确认范围 | 未确认能力 |
| --- | --- | --- | --- | --- |
| G1：TV/API/复现 | No-Go | 未提供 | 仅有 Huawei_TV ARM64 模拟器开发期构建、安装和 6 项 Hypium 回归 | 具名真机、API、样本、复现规则与正式支持声明 |
| G2：libmpv 联合审计 | No-Go | 未提供 | SBOM（SPDX-2.3 25 包 + CycloneDX）、NOTICE/license-audit、libmpv.so ELF/ABI 审计（12 NEEDED 全 allowlist、denylist 未出现）、libmpv.so SHA-256 跨 HAR/HAP/独立构建可复现（`75d7240e…`）；**修复过时 PackageHar 缓存后重建 HAR 已真实携带 libmpv.so(53MB)+native bridge(176KB,N EEDED libmpv.so, UND mpv_*14个)** | 受控源码树/构建 manifest、真机加载/播放证据（G1/G3）、NOTICE 法务复核、负责人确认 |
| G3：画面/线程/输入 | No-Go | 未提供 | XComponent 生命周期与参数边界回归通过；**SW→GL 渲染架构改造完成**：EGL context + mpv OpenGL render context + eglSwapBuffers 真机链路打通（`napi_init.cpp:515-620`），hilog `GL renderer created`；ohcodec 硬件解码激活（`hwdec-current: ohcodec`）；颜色与方向修正（`MPV_RENDER_PARAM_FLIP_Y=1`）；`hardwareDecoding` API 已暴露（`PlayerOptions.hardwareDecoding: 'auto'\|'disabled'`）；见 `release/audits/g3-gl-render-audit.json` 与 `evidence/g3-surface-spike-record.md` | 完整 Surface spike（attach/resize/detach/rebuild/stop/release 全链路 generation + 失败路径）、跨设备复现、`VideoParams.hardwareDecoding` 上报至 ArkTS、负责人书面确认 |

结论：没有任何门禁为 Go。已完成的 HAR、自动化测试、SBOM/ELF 审计、模拟器开发期回归、真机 GL 渲染与 ohcodec 硬解激活证据不能替代同一 candidateId 的完整真机证据或书面确认。此前"当前 HAR 未包含 libmpv.so、无真实播放内核"的判断源于 8 月 2 日过时缓存，已通过 clean 重建修复——重建 HAR 现真实携带 libmpv.so 并由 native bridge 驱动，libmpv.so SHA-256 可复现。本轮进一步将渲染路径从 SW 软件渲染升级为 GL 硬件加速渲染（ohcodec 硬解 + EGL/GL），补齐 G3 NativeWindow/EGL/GLES 真路径缺口。候选继续 `blocked`，不得分发、上传 OHPM 或声明播放、首帧、TV 支持，直至完整 Surface spike、跨设备复现与三门禁书面 Go 到位。
