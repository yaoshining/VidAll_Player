# G1--G3 门禁审查汇总

- 更新日期：2026-08-07T02:30:00+08:00
- 当前候选：003-libmpv-player-har；`deliveryStatus: ready`
- 建议：**Go**（负责人 yaoshining 于 2026-08-07 书面确认）

| 门禁 | 所需材料 | 当前结果 | 缺口 | 建议 |
| --- | --- | --- | --- | --- |
| G1：TV/API/复现 | 具名 ARM64 TV、API、样本、跨设备规则、真机运行记录 | ✅ Go：华为智慧屏 MateTV Pro EDIS-790A ARM64 + API 24/OH 6.1.1.130；4K HEVC + H.264 SD 双样本真机播放；全屏/退出全屏/元数据弹层/GL 渲染/ohcodec 硬解全部验证通过 | 跨设备复现基线（首期仅单设备验证，待后续补充） | **Go** |
| G2：libmpv 联合审计 | 来源、源码、GPL、NOTICE、构建、SBOM、ABI/ELF、加载边界 | ✅ Go：SBOM/NOTICE/来源锁已生成；libmpv.so ELF/ABI passed；SHA-256 可复现（`75d7240e…`）；HAR 真实携带 libmpv.so+native bridge；加载边界已固化至 build-profile.json5/CMakeLists.txt/oh-package.json5/release/manifests/ | 受控源码树与构建 manifest（首期使用预构建二进制，待后续归档） | **Go** |
| G3：画面/线程/输入 | Surface 生命周期、线程、NativeWindow/EGL/GLES、样本闭集和 spike | ✅ Go：SW→GL 渲染改造完成；EGL context + mpv OpenGL render context 真机链路打通；ohcodec 硬解激活；颜色/方向修正；generation 管理验证；元数据完整上报（videoParams 14字段 + audioParams 5字段 + video-bitrate/audio-bitrate 实时更新）；hardwareDecoding API 暴露 | 跨设备复现（首期仅单设备验证，待后续补充） | **Go** |

三门禁已由项目负责人 yaoshining 于 2026-08-07 书面确认 Go。真机证据归档于 `evidence/g1-device-run-template.md` 和 `evidence/g3-surface-spike-record.md`。候选从 `blocked` 升级为 `ready`。已知限制：首期仅单设备验证，跨设备复现待后续补充；受控源码树/构建 manifest 待后续归档。