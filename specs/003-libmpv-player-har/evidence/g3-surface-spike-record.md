# G3 Surface 真机 Spike 记录

- candidateId：003-libmpv-player-har
- sourceCommit：c40876c89a439f2eebad728bebec89d1de5ee094
- recordedAt：2026-08-06T15:40:00+08:00
- executor：yaoshining（项目所有者）
- environment：DevEco Studio hvigor + devecocli；华为智慧屏 MateTV Pro EDIS-790A ARM64 TV，API 24，OpenHarmony-6.1.1.130 Release，3840×2160；serial 192.168.3.85:5555
- sampleRef：4K HEVC WebDAV 视频流 + test_video.mp4（480×270 H.264，仓库内置 fixture）
- deliveryStatus：draft
- approvalRef：待负责人书面确认

## 执行背景

本记录覆盖三轮真机验证：
1. SW→GL 渲染架构改造与 ohcodec 硬件解码激活验证
2. 元数据弹层与 video-params/audio-params 完整字段验证
3. hardwareDecoding API 上报至 ArkTS 验证

此前 G3 因"未取得 NativeWindow/EGL/GLES 真路径证据"标记为 No-Go；通过 EGL context + mpv OpenGL render context + eglSwapBuffers 的真机链路补齐该缺口，并进一步验证了完整元数据上报和音视频码率实时更新。

## NativeWindow/EGL/GLES 真实渲染路径

### 初始化（attach / 首次渲染）

1. 创建 session，记录 sessionId、eventEpoch、渲染线程。
2. attach：XComponent 提供 NativeWindow（`OHNativeWindow`），`NativeWindow SET_BUFFER_GEOMETRY` 设置宽高。
3. EGL 初始化（`napi_init.cpp:515-585`）：
   - `eglGetDisplay(EGL_DEFAULT_DISPLAY)` → `eglInitialize`
   - `eglChooseConfig`（RGBA8888 + `EGL_WINDOW_BIT`）
   - `eglCreateContext(EGL_NO_CONTEXT, [EGL_CONTEXT_CLIENT_VERSION, 3, EGL_NONE])`
   - `eglCreateWindowSurface(eglDisplay_, eglConfig_, NativeWindow, nullptr)`
   - `eglMakeCurrent(eglDisplay_, eglSurface_, eglSurface_, eglContext_)`
4. mpv GL render context 创建：
   - `MPV_RENDER_API_TYPE_OPENGL` + `mpv_opengl_init_params{&MpvGlGetProcAddress, nullptr}`（`MpvGlGetProcAddress` 调用 `eglGetProcAddress`）
   - `mpv_render_context_create` → 真机 hilog：`GL renderer created`

### 渲染循环（load / play / 首帧）

- 渲染线程循环（`napi_init.cpp:590-620`）：
  - `mpv_opengl_fbo{fbo=0, w, h, internal_format=0}` 指定默认 FBO（EGL window surface）
  - `MPV_RENDER_PARAM_FLIP_Y = 1` 翻转 Y 轴（修正 mpv 左下原点 vs EGL 左上原点）
  - `mpv_render_context_render(renderer_, frame)` 渲染到 FBO 0
  - `eglSwapBuffers(eglDisplay_, eglSurface_)` 上屏
- mpv 事件线程：`mpv_observe_property(player, 0, "hwdec-current", MPV_FORMAT_STRING)`，属性变更时 `OH_LOG_Print` 输出 → 真机 hilog：`hwdec-current: ohcodec`（ohcodec 硬件解码后端激活）

### resize

- `NativeWindow SET_BUFFER_GEOMETRY` 后 EGL surface 不自动跟随（`napi_init.cpp:593-603`）：
  - `eglMakeCurrent(EGL_NO_SURFACE)` 解绑
  - `eglDestroySurface` → `eglCreateWindowSurface` 重建
  - `eglMakeCurrent` 重新绑定

### destroy / release（detach）

- `DestroyRenderer`（`napi_init.cpp:641-685`）按顺序释放：
  1. `eglMakeCurrent(EGL_NO_SURFACE)` 解绑当前上下文
  2. `eglDestroySurface(eglDisplay_, eglSurface_)`
  3. `eglDestroyContext(eglDisplay_, eglContext_)`
  4. `eglTerminate(eglDisplay_)`
  5. `mpv_render_context_free(renderer_)`
- 快速重复调用 `DestroyRenderer` 已验证幂等（EGL 资源为 `EGL_NO_*` 时跳过）。

## 线程边界

- 渲染线程：独立 `std::thread`，持 EGL context + mpv render context，循环 `mpv_render_context_render` + `eglSwapBuffers`。
- mpv 事件线程：`mpv_wait_event` 阻塞循环，处理 `MPV_EVENT_PROPERTY_CHANGE`（hwdec-current 等）并 `OH_LOG_Print`。
- ArkTS/UI 线程：通过 NAPI 调用 `createSession`/`load`/`play`/`resize`/`destroy`，不直接接触 EGL/GL。

## 真机观察与证据引用

| 场景 | 预期 | 实测 | 证据引用 | 限制 |
| --- | --- | --- | --- | --- |
| EGL + GL render context 初始化 | `GL renderer created` | ✅ hilog 输出 | `release/audits/g3-gl-render-audit.json` hilogFragments | 开发期验证 |
| ohcodec 硬件解码激活 | `hwdec-current: ohcodec` | ✅ hilog 输出 | 同上 | 开发期验证 |
| 颜色正确（红色为红色，不偏黄白） | 正常色彩 | ✅ 用户口头确认 | 同上 | 开发期验证 |
| 画面方向正确（无上下颠倒） | 正常方向 | ✅ 用户口头确认（`MPV_RENDER_PARAM_FLIP_Y=1`） | 同上 | 开发期验证 |
| resize 后 EGL surface 重建 | 画面尺寸更新 | ✅ 重建逻辑就绪 | `napi_init.cpp:593-603` | 开发期验证 |
| destroy/release 幂等 | 无残留、无崩溃 | ✅ DestroyRenderer 幂等 | `napi_init.cpp:641-685` | 开发期验证 |
| attach/detach generation 递增 | 旧 generation 不接管 | ✅ surfaceAdapter generation 计数 + EventLoop 校验 | `surfaceAdapter.ets` | 开发期验证 |
| videoParams 完整上报 | 宽高/hwdec/pixfmt/bitDepth/色彩/fps/aspect/bitrate 全字段 | ✅ 4K HEVC: `3840x2160\|ohcodec\|nv12\|8\|bt.709\|bt.1886\|bt.709\|SDR\|23.976025\|0\|1.778\|0\|limited\|223576` | 真机 hilog videoParams dispatch | 开发期验证 |
| audioParams 完整上报 | samplerate/channels/channelCount/format/audioBitrate | ✅ 7.1: `48000\|7.1\|8\|s32\|1373603` | 真机 hilog audioParams dispatch | 开发期验证 |
| hardwareDecoding 三态上报 | active/fallback/unavailable | ✅ ohcodec → active | `napi_init.cpp` hwdec-current + playerSession.ets 映射 | 开发期验证 |
| video-bitrate/audio-bitrate 实时更新 | 码率动态变化 | ✅ 视频 ~170kbps-24Mbps、音频 ~90kbps-1.37Mbps | 真机 hilog 5%阈值 dispatch | 开发期验证 |
| 元数据弹层 UI | 按钮点击打开、返回键关闭、展示完整参数 | ✅ 用户验证 | `entry/src/main/ets/pages/Index.ets` MetadataSheet | 开发期验证 |

## 未完整覆盖

- 失败路径（无效画面、未批准输入）未在本轮真机运行（已有自动化契约测试覆盖）。
- 跨设备复现矩阵（G1 target-matrix）未完成。
- `EglWrapperHookLayer init Failed` 警告根因未查（非致命，不影响渲染）。

## 结论

能力状态：`已构建待验证`（NativeWindow/EGL/GLES 真渲染路径已打通，ohcodec 硬解已激活，颜色与方向已修正，元数据完整上报已验证，hardwareDecoding API 已暴露；仍缺跨设备复现与负责人书面签收）。

本记录补齐了 G3 NativeWindow/EGL/GLES 真路径 + 完整元数据上报证据，但 G3 门禁尚未关闭——仍需跨设备复现与负责人书面确认。
