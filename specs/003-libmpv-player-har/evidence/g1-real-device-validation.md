# G1 真机开发期验证记录

## 运行标识

- `candidateId`：003-libmpv-player-har
- `sourceCommit`：c31494b
- `recordedAt`：2026-08-03T22:30:00+08:00
- 执行人：yaoshining（项目所有者）
- 设备：华为智慧屏 MateTV Pro，型号 EDIS-790A，ARM64，API 24 (HarmonyOS 5.0)，serial 192.168.3.85:5555
- 媒体：WebDAV 协议视频流（用户自备内容）

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

## 结论

能力状态：`开发期验证通过`（真机播放、全屏、退出全屏均已验证；仍需负责人书面确认方可关闭 G1 门禁）。

本记录仅为开发期真机验证，不构成 G1 门禁关闭依据。G1 关闭需要：
1. 负责人指定真机型号和批准样本
2. 跨设备复现基线
3. 首帧时间记录
4. 负责人书面确认