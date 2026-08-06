# 最终就绪记录

- 复核日期：2026-08-07T02:30:00+08:00
- 复核依据：`quickstart.md`、`gate-review-summary.md`、`gate-approvals.md`、G2 完整性审查与跨工件一致性审查、`release/audits/g3-gl-render-audit.json`、`evidence/g1-device-run-template.md`、`evidence/g3-surface-spike-record.md`。
- 当前候选：003-libmpv-player-har；`deliveryStatus: ready`
- 最终状态：**Go**

## 复核结果

1. G1 **Go**：华为智慧屏 MateTV Pro EDIS-790A ARM64 + API 24/OH 6.1.1.130，4K HEVC + H.264 SD 双样本真机播放验证完成（全屏/退出全屏/元数据弹层/GL 渲染/ohcodec 硬解/hardwareDecoding API 全部验证通过）；负责人 yaoshining 于 2026-08-07 书面确认 Go。已知限制：首期仅单设备验证。
2. G2 **Go**：SBOM/NOTICE/来源锁/ELF/ABI 审计已通过，libmpv.so SHA-256 可复现（`75d7240e…`），HAR 真实携带 libmpv.so+native bridge，加载边界已固化至 build-profile.json5/CMakeLists.txt/oh-package.json5/release/manifests/；负责人 yaoshining 于 2026-08-07 书面确认 Go。已知限制：首期使用预构建二进制，受控源码树/构建 manifest 待后续归档。
3. G3 **Go**：SW→GL 渲染架构改造完成，NativeWindow/EGL/GLES 真路径打通，ohcodec 硬解激活，颜色/方向修正，generation 管理验证，元数据完整上报（videoParams 14字段 + audioParams 5字段 + video-bitrate/audio-bitrate 实时更新），hardwareDecoding API 暴露；负责人 yaoshining 于 2026-08-07 书面确认 Go。已知限制：首期仅单设备验证。
4. 已完成本地 HAR、原生 bridge、ArkTS 生命周期接口和独立 fixture；自动化 CTest 11/11 通过，Hypium 测试通过；真机 GL 渲染/ohcodec 硬解/元数据上报证据已纳入 `release/audits/g3-gl-render-audit.json` 和 `evidence/g3-surface-spike-record.md`。
5. 候选 `003-libmpv-player-har` 从 `blocked` 升级为 `ready`，可进行受控分发。

## 已知限制

- 首期仅单设备（华为智慧屏 MateTV Pro EDIS-790A）验证，跨设备复现待后续补充
- 受控源码树/构建 manifest 待后续归档（首期使用预构建二进制）
- 不得上传 OHPM 或公开发布，直至跨设备复现基线建立