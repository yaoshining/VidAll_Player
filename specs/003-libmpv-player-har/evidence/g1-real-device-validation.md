# G1 真机开发期验证记录

## 运行标识

- `candidateId`：003-libmpv-player-har
- `sourceCommit`：63222bd0f103c035e06c055abe9df3f47438a52c
- `recordedAt`：2026-08-05T17:30:00+08:00
- 执行人：yaoshining（项目所有者）
- 设备：华为智慧屏 MateTV Pro，型号 EDIS-790A，ARM64，API 24 (HarmonyOS 5.0)，serial 192.168.3.85:5555
- 媒体：WebDAV 协议视频流（用户自备内容）；test_video.mp4（480×270 H.264，仓库内置 fixture）

## 前置与步骤

1. 通过 `devecocli run --uninstall --module entry --device 192.168.3.85:5555` 部署 HAR + fixture
2. 用户手动启动 WebDAV 播放
3. 验证全屏播放：用户手动点击全屏按钮
4. 验证返回键退出全屏
5. 每步通过 `snapshot_display` 截图留证

## 观察与附件

| 场景 | 预期 | 实测 | 证据引用 | 限制 |
| --- | --- | --- | --- | --- |
| WebDAV 视频播放 | 正常出帧、有声音 | ✅ 正常出帧、AudioLogUtils RendererInClient active | hilog 输出 | 开发期验证 |
| 全屏播放 | 画面占满智慧屏 | ✅ 3840×2160 全屏渲染 | `real-device-fullscreen.jpeg` | 开发期验证 |
| 返回键退出全屏 | 恢复正常视图 | ✅ 正常恢复，视频继续播放 | `real-device-exit-fullscreen.jpeg` | 开发期验证 |
| 视频持续播放 | 无卡顿、崩溃 | ✅ 全程稳定 | 连续截图观察 | 开发期验证 |
| 字幕渲染 | ASS/SRT 渲染到画面 | ⏳ 待验证（模拟器已验证） | 模拟器证据见 `emulator-development-validation.md` | 需真机确认 |
| SW→GL 渲染架构改造 | EGL + mpv OpenGL render context 初始化 | ✅ hilog `GL renderer created` | `release/audits/g3-gl-render-audit.json` | 开发期验证 |
| ohcodec 硬件解码激活 | `hwdec-current: ohcodec` | ✅ hilog 输出 | 同上 | 开发期验证 |
| 颜色正确（红色不偏黄白） | 正常色彩 | ✅ 用户口头确认 | 同上 | 开发期验证 |
| 画面方向正确（无上下颠倒） | 正常方向 | ✅ 用户口头确认（`MPV_RENDER_PARAM_FLIP_Y=1`） | 同上 | 开发期验证 |
| `hardwareDecoding` API 暴露 | 客户端可控制硬解开关 | ✅ `PlayerOptions.hardwareDecoding: 'auto'\|'disabled'` | `packages/vidall-player/src/public/types.ets` + 契约测试 | 开发期验证 |

## 结论

能力状态：`开发期验证通过`（真机播放、全屏、退出全屏、GL 硬件加速渲染、ohcodec 硬解激活、颜色/方向修正、`hardwareDecoding` API 均已验证；仍需负责人书面确认方可关闭 G1 门禁）。

本记录仅为开发期真机验证，不构成 G1 门禁关闭依据。G1 关闭需要：
1. 负责人指定真机型号和批准样本
2. 跨设备复现基线
3. 首帧时间记录
4. 负责人书面确认