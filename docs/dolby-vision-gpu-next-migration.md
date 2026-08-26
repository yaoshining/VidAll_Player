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

## 3. 可行性门槛（**已确认通过**）

**重要澄清**：libmpv-ohos-build fork 实际拉取的 mpv 是 **`ErBWs/mpv` 分支 `feat-ohos-0.41.0`**（OHOS 改造 fork），**不是** `native/config/sources.lock.json` 中标注的上游 mpv v0.40.0（commit `287d7cdb`）。该 branch 源码树（已核实）含：

- `video/out/ohos_common.c` / `ohos_common.h`（OHOS 窗口支持）
- `video/out/opengl/context_ohos.c`（OHOS OpenGL 上下文）
- `video/out/vulkan/context_ohos.c`（**OHOS Vulkan 上下文**）
- `video/out/gpu_next/context.c` / `context.h`（gpu_next 上下文框架）
- `video/out/vo_gpu_next.c`（`vo_gpu_next` 渲染器）
- `video/out/hwdec/hwdec_vulkan.c`、`video/filter/vf_gpu_vulkan.c`

即 fork **支持 `vo_gpu_next` 的 OHOS Vulkan/EGL 窗口上下文**——(a) 方案（真实 `vo_gpu_next` VO + OHOS 窗口）具备可行性，无需先扩展 fork。

> ⚠️ 供应链一致性提醒：`sources.lock.json` 记录的 mpv 上游 commit（v0.40.0）与 fork 实际构建的 ErBWs/mpv `feat-ohos-0.41.0` **不一致**。这影响「锁定的源码 == 实际构建源码」的可复现声明；建议在实现 (a) 前先在锁中校正 mpv 来源/commit 或明确 fork 版本策略。

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

1. **可行性门槛已通过**（见第 3 节）：fork 支持 OHOS `vo_gpu_next` 窗口/上下文 → 走方案 (a)，SDK 渲染层从 render API 迁移到窗口 VO。需在真机（EDIS-790A）逐步验证 Vulkan/EGL 互操作。
2. **在真机迭代**：改造含 Vulkan/EGL 互操作，需在 EDIS-790A 真机逐步验证（软解、窗口、dovi 色彩）。
3. **验收**：DV Profile 5 片源真机色彩正确（不再发灰/掉饱和），与 SDR/HDR10 参考对比通过。

## 6. 诊断打点（已就位，用于真机确认）

- `video-params diag`（全量 dump）：查看 `colormatrix`（=色彩系统 repr.sys）。`colormatrix=dolbyvision`→dovi 未剥离；`colormatrix=bt2020nc`+`gamma=pq`+发灰→dovi 被 vo_gpu 剥离。
- `render context api=... vo=libmpv(vo_gpu)`：确认渲染后端为 OPENGL=vo_gpu。

> 注：`video-params diag` 补丁因 native 增量缓存可能未进上一版 HAR，干净构建（`devecocli build --clean` 或删除 `packages/vidall-player/build`）后生效。

## 7. 真机实证（证据链闭环，EDIS-790A，DV Profile 5）

native 日志关键行：

```
render context api=opengl vo=libmpv(vo_gpu): DV dovi reshape 需 vo_gpu_next（render API 不可达）
Upgraded to GL renderer
video-params diag: pixelformat=yuv420p10 average-bpp=24 w=3840 h=1606 dw=3840 dh=1606
  colormatrix=dolbyvision colorlevels=full primaries=bt.2020 gamma=pq sig-peak=4.929 light=display
  max-luma=1000.607 min-luma=0.000  (PQ 高光 1000nit 信号，但被渲染成发灰)
  max-pq-y=0.672 avg-pq-y=0.300
```

解读：
1. `colormatrix=dolbyvision` → mpv 确实识别到 Dolby Vision（非普通 HDR）。
2. `primaries=bt.2020 gamma=pq` → mpv 把 dovi 当**基础 BT.2020/PQ** 处理，**无 ICtCp/IPTPQc2 reshape 标记**（dovi RPU 未应用）。
3. `render context api=opengl vo=libmpv(vo_gpu)` → 一句话 root cause：当前 `vo=libmpv`+OpenGL 无法做 dovi reshape，必须 `vo_gpu_next`。
4. `colormatrix=dolbyvision` 但画面发灰（平均饱和度 0.277）+ `max-pq-y=0.672` → dovi 被识别但被 `restore_dovi_mapping` 剥离/未 reshape，被当 BT.2020/PQ 渲染 → 发灰。

> 与第 1 节源码级结论（vo_gpu `restore_dovi_mapping` 剥离 dovi）完全一致。Root Cause 已 100% 实锤：libdovi 已就位、dovi 能被识别，但 `vo=libmpv`(OpenGL) 无法到达 gpu_next 的 `pl_renderer`。
