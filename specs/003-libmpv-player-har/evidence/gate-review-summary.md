# G1--G3 门禁审查汇总

- 更新日期：2026-08-05T17:30:00+08:00
- 当前候选：未分配；`deliveryStatus: blocked`
- 建议：No-Go

| 门禁 | 所需材料 | 当前结果 | 缺口 | 建议 |
| --- | --- | --- | --- | --- |
| G1：TV/API/复现 | 具名 ARM64 TV、API、样本、跨设备规则、真机运行记录 | 未关闭；仅有模拟器开发期 6 项 Hypium 回归 | 负责人确认和全部真机记录 | No-Go |
| G2：libmpv 联合审计 | 来源、源码、GPL、NOTICE、构建、SBOM、ABI/ELF、加载边界 | 部分关闭：SBOM/NOTICE/来源锁已生成；libmpv.so ELF/ABI passed；libmpv.so SHA-256 跨 HAR/HAP/独立构建可复现（`75d7240e…`）；**过时 PackageHar 缓存已修复，重建 HAR 真实携带 libmpv.so+native bridge** | 受控源码树与构建 manifest、真机加载/播放证据（G1/G3）、NOTICE 法务复核、负责人签收 | No-Go |
| G3：画面/线程/输入 | Surface 生命周期、线程、NativeWindow/EGL/GLES、样本闭集和 spike | 未关闭；**SW→GL 渲染架构改造完成**：EGL context + mpv OpenGL render context 真机链路打通，hilog `GL renderer created`；ohcodec 硬解激活（`hwdec-current: ohcodec`）；颜色/方向修正；`hardwareDecoding` API 暴露（见 `release/audits/g3-gl-render-audit.json`） | 完整 Surface spike（attach/resize/detach/rebuild/stop/release 全链路 + 失败路径）、跨设备复现、`VideoParams.hardwareDecoding` 上报至 ArkTS、负责人书面确认 | No-Go |

三个门禁未同时获得书面 Go。已实现的 HAR、原生产物、SBOM/ELF 审计、NAPI bridge、播放器、fixture、真机 GL 渲染与 ohcodec 硬解激活证据仅供受控开发验证；此前"当前 HAR 无 libmpv.so（无真实播放内核）"的结论已被推翻——过时 PackageHar 缓存已修复，重建 HAR 真实携带 libmpv.so 且可复现。本轮进一步把渲染路径从 SW 软件渲染升级为 GL 硬件加速（ohcodec 硬解 + EGL/GL），补齐 G3 NativeWindow/EGL/GLES 真路径缺口。仍需完整 Surface spike、跨设备复现（G1）与三门禁书面 Go。不得交付、上传 OHPM 或将任意能力标为已支持。
