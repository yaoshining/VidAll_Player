# G1--G3 负责人确认归档

| 门禁 | 当前状态 | 书面确认引用 | 已确认范围 | 未确认能力 |
| --- | --- | --- | --- | --- |
| G1：TV/API/复现 | **Go** | yaoshining, 2026-08-07 | 华为智慧屏 MateTV Pro EDIS-790A ARM64，API 24/OH 6.1.1.130；4K HEVC + H.264 SD 双样本真机播放验证；全屏/退出全屏/元数据弹层/GL 硬件渲染/ohcodec 硬解全部验证通过 | 跨设备复现基线（首期仅单设备验证） |
| G2：libmpv 联合审计 | **Go** | yaoshining, 2026-08-07 | SBOM（SPDX-2.3 25 包 + CycloneDX）、NOTICE/license-audit、libmpv.so ELF/ABI 审计（12 NEEDED 全 allowlist、denylist 未出现）、libmpv.so SHA-256 跨 HAR/HAP/独立构建可复现（`75d7240e…`）；重建 HAR 真实携带 libmpv.so(53MB)+native bridge(176KB, NEEDED libmpv.so, UND mpv_*14个)；加载边界已固化至 build-profile.json5/CMakeLists.txt/oh-package.json5/release/manifests/ | 受控源码树/构建 manifest（首期使用预构建二进制） |
| G3：画面/线程/输入 | **Go** | yaoshining, 2026-08-07 | XComponent 生命周期与参数边界回归通过；SW→GL 渲染架构改造完成：EGL context + mpv OpenGL render context + eglSwapBuffers 真机链路打通；ohcodec 硬件解码激活；颜色/方向修正；generation 管理验证；元数据完整上报（videoParams 14字段 + audioParams 5字段）；hardwareDecoding API 暴露；video-bitrate/audio-bitrate 实时更新 | 跨设备复现（首期仅单设备验证） |

结论：三门禁已由项目所有者 yaoshining 于 2026-08-07 书面确认 Go。真机播放/渲染/元数据上报/硬解/API 暴露已全部验证，G2 材料（SBOM/ELF/ABI/加载边界）齐备且已固化。候选从 `blocked` 升级为 `ready`。已知限制：首期仅单设备（华为智慧屏 MateTV Pro）验证，跨设备复现待后续补充；受控源码树/构建 manifest 待后续归档。
