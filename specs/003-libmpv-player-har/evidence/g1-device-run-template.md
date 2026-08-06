# G1 真机可重放记录

## 运行标识

- `candidateId`：003-libmpv-player-har
- `sourceCommit`：c40876c89a439f2eebad728bebec89d1de5ee094
- `recordedAt`：2026-08-06T15:40:00+08:00
- 执行人：yaoshining（项目所有者）
- 设备：华为智慧屏 MateTV Pro，型号 EDIS-790A，ARM64，API 24 (HarmonyOS 5.0)，OpenHarmony-6.1.1.130 Release，serial 192.168.3.85:5555，分辨率 3840×2160
- 媒体：WebDAV 协议 4K HEVC 视频（HDR bt.709/SDR）；test_video.mp4（480×270 H.264 SD，仓库内置 fixture）

## 前置与步骤

1. 工具链：DevEco Studio hvigor + devecocli；hdc（`/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/toolchains/hdc`）
2. 部署：`devecocli run --module entry --device 192.168.3.85:5555`
3. 画面附着：XComponent onLoad → attachSurface → OH_NativeWindow_CreateNativeWindowFromSurfaceId 成功
4. 加载/播放：WebDAV 视频流 load → play → mpv 初始化 → ohcodec 硬解激活 → GL 渲染首帧
5. 全屏/退出：全屏播放 3840×2160，返回键退出全屏恢复正常视图
6. 元数据验证：元数据弹层显示完整 videoParams + audioParams
7. 释放：DestroyRenderer 幂等，EGL 资源按序释放

## 观察与附件

| 场景 | 预期 | 实测 | 证据引用 | 限制 |
| --- | --- | --- | --- | --- |
| 有效画面与批准输入（4K HEVC） | 正常出帧、有声音、硬解激活 | ✅ ohcodec 硬解 + GL 渲染首帧正常 | hilog `hwdec-current: ohcodec`；元数据弹层 3840x2160/nv12/8bit/bt.709/SDR/23.976fps/7.1音频 | 开发期验证 |
| 有效画面与批准输入（H.264 SD） | 正常出帧、有声音 | ✅ ohcodec 硬解 + GL 渲染首帧正常 | 元数据弹层 480x270/nv12/8bit/bt.709/SDR/25fps | 开发期验证 |
| 全屏播放 | 画面占满智慧屏 | ✅ 3840×2160 全屏渲染 | `real-device-fullscreen.jpeg` | 开发期验证 |
| 返回键退出全屏 | 恢复正常视图、视频继续 | ✅ 正常恢复 | `real-device-exit-fullscreen.jpeg` | 开发期验证 |
| 无有效画面 | 稳定拒绝或等待 | ✅ load/play 无有效画面返回 SURFACE_UNAVAILABLE | 契约测试 T023 | 自动化测试覆盖 |
| 无效或未批准输入 | 脱敏结构化失败 | ✅ FEATURE_UNSUPPORTED / INPUT_INVALID | 契约测试 T002 | 自动化测试覆盖 |
| destroy/rebuild | 陈旧画面不接管 | ✅ generation 递增、旧 generation 事件被过滤 | surfaceAdapter generation 管理 + EventLoop 校验 | 开发期验证 |
| stop/release 重复调用 | 无崩溃、死锁、残留回调 | ✅ DestroyRenderer 幂等；release 后控制返回 RELEASED | `napi_init.cpp:641-685` + 契约测试 T017 | 开发期验证 |
| EGL/GL 渲染管线初始化 | GL renderer created | ✅ hilog 输出 | `release/audits/g3-gl-render-audit.json` | 开发期验证 |
| 颜色正确 | 正常色彩 | ✅ 用户口头确认 | 同上 | 开发期验证 |
| 画面方向正确 | 无上下颠倒 | ✅ MPV_RENDER_PARAM_FLIP_Y=1 | 同上 | 开发期验证 |
| 元数据上报完整 | videoParams + audioParams 全字段 | ✅ 4K: 3840x2160/nv12/8/bt.709/bt.1886/bt.709/SDR/23.976fps/1.778/limited/223576kbps；Audio: 48000/7.1/8/s32/1373603kbps | 真机 hilog videoParams/audioParams dispatch | 开发期验证 |
| hardwareDecoding API 暴露 | 客户端可控制硬解开关 | ✅ PlayerOptions.hardwareDecoding: 'auto'|'disabled' | types.ets + 契约测试 | 开发期验证 |

## 结论

能力状态：`已构建待验证`（真机播放、全屏、GL 渲染、ohcodec 硬解、元数据弹层、hardwareDecoding API 均已验证；仍需跨设备复现与负责人书面确认方可升级为 `已通过真机样本`）。
