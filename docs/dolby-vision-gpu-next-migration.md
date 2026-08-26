# Dolby Vision Profile 5 渲染层迁移设计（vo_gpu_next）

> 关联：issue #69（产物已具备 libdovi）、issue #71（本设计所在的架构级改造）。
> 结论先行：libmpv render API 无法启用 `vo_gpu_next`，DV Profile 5 还原需**脱离 `mpv_render_context`**。
> 本文件是迁移设计/可行性评估，非最终代码。两处方案的取舍取决于 libmpv-ohos-build fork 对 OHOS `vo_gpu_next` 窗口/上下文的支持程度。

## 1. 背景与根因（已源码级 + 真机证实）

- 片源：Dolby Vision **Profile 5（IPTPQc2，`dvBlSignalCompatibilityId=0`，无 HDR10/SDR 基层）**。
- 产物：`libmpv.so` 已编入 `libdovi`（`dovi_convert_rpu_with_mode`/`dovi_parse_rpu`/`dovi_rpu_*`）、`vo_gpu_next`、libplacebo Vulkan（`pl_vulkan_create/swapchain/...`）。
- 渲染路径：SDK `packages/vidall-player/src/main/cpp/napi_init.cpp` 用 `vo=libmpv` + `mpv_render_context` + `MPV_RENDER_API_TYPE_OPENGL`。
- 真机日志：`SW renderer created as baseline` → `Upgraded to GL renderer` → 确认走 **vo_gpu（GL）**；DV Profile 5 发灰（饱和度 0.277）。

**根因（mpv v0.40.0 源码）**：
1. `include/mpv/render.h` 只定义 `MPV_RENDER_API_TYPE_OPENGL`/`_SW`，**无任何 Vulkan/gpu-next 类型**；`vo_gpu_next`+`pl_vulkan_*` 虽然编译进 `.so`，但经 libmpv render API **不可达**。
2. OPENGL 渲染后端 = **`vo_gpu`**。`video/out/gpu/video.c:991` 无条件调用 `mp_image_params_restore_dovi_mapping()`，把 `repr.sys` 从 `DOLBYVISION` 重置为基础色彩系统；`video/out/gpu/` 目录内**仅有这一处** dovi 引用，无任何 `pl_shader_dovi_reshape`/`pl_dovi`。
3. DV 的 ICtCp→显示色彩重塑由 libplacebo `pl_renderer` 的 dovi reshape 完成，**只有 `vo_gpu_next`** 使用。故 Profile 5 被当基础色直出 → 发灰。

## 2. 关键约束

**libmpv render API 只能输出 OpenGL 或 Software。** 要启用 gpu-next 的完整色彩管理，必须让 mpv 以**真实 VO** 渲染到本地窗口，或由应用侧用 libplacebo 直接渲染。二者都需脱离 `mpv_render_context`。

## 3. 可行性门槛（必须先确认）

- mpv v0.40 **上游** `video/out/` 无任何 OHOS 引用；OHOS 支持（如 `ohos_common.c`/`context_ohos.c`）由 libmpv-ohos-build fork 在 CI 构建期加入，**不在上游 git**。
- 因此需确认 fork 的 mpv 是否提供 **`vo_gpu_next` 的 OHOS 窗口/上下文后端**（Vulkan 或 EGL 绑定 `OH_NativeWindow`）。确认方法：
  - 检查 fork 构建产物（库、VO 列表）是否含 gpu-next + OHOS context；
  - 或检查 fork 应用到 mpv 源码上的 OHOS/gpu-next 补丁。
- 若 fork **不支持** OHOS gpu-next 窗口 → 需要先扩展 fork（新增 Vulkan surface 绑定 `OH_NativeWindow` 的 gpu-next context），工作量和风险显著上升。

## 4. 候选方案

### 方案 (a)：真实 `vo_gpu_next` VO + HarmonyOS 原生窗口（推荐，复用 mpv 渲染管线）

- 应用把 XComponent 的 `OH_NativeWindow` 交给 mpv；mpv 以 `--vo=gpu-next` + OHOS Vulkan/EGL context 直接输出到窗口。
- **SDK 渲染层改动**：`napi_init.cpp` 由「应用创建 EGL surface + `mpv_render_context_render`」改为「初始化真实 VO」；应用侧从 `MPV_RENDER_API_TYPE_OPENGL` 回调迁移到窗口句柄注入。
- **前置依赖**：fork 必须提供 `vo_gpu_next` 的 OHOS 窗口 context；否则需先扩展 fork。
- **优点**：色彩管理完整（libplacebo `pl_renderer`），dovi RPU→显示 + tone-mapping 一并正确。
- **风险**：Vulkan/EGL 在目标电视的兼容性、窗口/表面生命周期管理、软解/硬解切换。

### 方案 (b)：应用侧 libplacebo 直渲染（mpv 只做 demux/decode）

- mpv 只负责解封装/解码，应用用 libplacebo `pl_renderer`（带 Vulkan surface）渲染解码帧，自行做 dovi RPU→显示 + 色彩管理。
- **难点**：libmpv 不直接暴露「原始解码帧」给外部；需 mpv 提供帧回调或改造成走解码器 + `mpv_render` 的像素流，改动更彻底。
- **优点**：可控性最高，脱离 mpv VO 框架；**缺点**：需自行实现渲染循环、dovi 管线、帧同步，工作量大。

## 5. 建议路径

1. **先做可行性门槛**：确认 fork 是否支持 OHOS `vo_gpu_next` 窗口/上下文。
   - 支持 → 走方案 (a)，SDK 渲染层从 render API 迁移到窗口 VO。
   - 不支持 → 评估扩展 fork 的成本；成本过高时再权衡 (b)。
2. **在真机迭代**：改造含 Vulkan/EGL 互操作，需在 EDIS-790A 真机逐步验证（软解、窗口、dovi 色彩）。
3. **验收**：DV Profile 5 片源真机色彩正确（不再发灰/掉饱和），与 SDR/HDR10 参考对比通过。

## 6. 诊断打点（已就位，用于真机确认）

- `video-params diag`（全量 dump）：查看 `colormatrix`（=色彩系统 repr.sys）。`colormatrix=dolbyvision`→dovi 未剥离；`colormatrix=bt2020nc`+`gamma=pq`+发灰→dovi 被 vo_gpu 剥离。
- `render context api=... vo=libmpv(vo_gpu)`：确认渲染后端为 OPENGL=vo_gpu。

> 注：`video-params diag` 补丁因 native 增量缓存可能未进上一版 HAR，干净构建（`devecocli build --clean` 或删除 `packages/vidall-player/build`）后生效。
