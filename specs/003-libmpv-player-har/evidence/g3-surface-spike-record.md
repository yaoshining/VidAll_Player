# G3 Surface 真机 Spike 记录

- candidateId：003-libmpv-player-har
- sourceCommit：63222bd0f103c035e06c055abe9df3f47438a52c
- recordedAt：2026-08-05T17:30:00+08:00
- executor：yaoshining（项目所有者）
- environment：DevEco Studio hvigor + devecocli；EDIS-790A ARM64 TV，API 24，OpenHarmony-6.1.1.130 Release，3840×2160；serial 192.168.3.85:5555
- sampleRef：test_video.mp4（480×270 H.264，3206594 字节，仓库内置 fixture）
- deliveryStatus：draft
- approvalRef：待负责人书面确认

## 执行背景

本轮在已连通真机上完成 SW→GL 渲染架构改造与 ohcodec 硬件解码激活验证。此前 G3 因"未取得 NativeWindow/EGL/GLES 真路径证据"标记为 No-Go；本轮通过 EGL context + mpv OpenGL render context + eglSwapBuffers 的真机链路补齐该缺口。

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
| resize 后 EGL surface 重建 | 画面尺寸更新 | ✅ 重建逻辑就绪 | `napi_init.cpp:593-603` | 未在本轮真机截屏留证 |
| destroy/release 幂等 | 无残留、无崩溃 | ✅ DestroyRenderer 幂等 | `napi_init.cpp:641-685` | 未在本轮真机截屏留证 |

## 未完整覆盖

- attach/resize/detach/rebuild/stop/release 的完整 generation 链路记录（本轮仅记录关键路径）。
- 失败路径（无效画面、未批准输入）未在本轮真机运行。
- 跨设备复现矩阵（G1 target-matrix）未完成。
- `VideoParams.hardwareDecoding` 字段尚未从 native 上报至 ArkTS（当前 hwdec-current 仅 hilog 输出）。
- `EglWrapperHookLayer init Failed` 警告根因未查（非致命）。

## 结论

能力状态：`已构建待验证`（NativeWindow/EGL/GLES 真渲染路径已打通，ohcodec 硬解已激活，颜色与方向已修正；仍缺完整 generation 链路记录与负责人书面签收）。

本记录补齐了此前 G3 "无 NativeWindow/EGL/GLES 真路径" 的缺口，但 G3 门禁尚未关闭——仍需完整 Surface spike（attach/resize/detach/rebuild/stop/release 全链路 + 失败路径）与负责人书面确认。
