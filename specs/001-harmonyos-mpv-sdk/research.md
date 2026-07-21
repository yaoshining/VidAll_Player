# 研究记录：VidAll_Player 可发布组件库

## 原生播放架构

- **决策**：公开 `@vidall/player` ArkTS 只提供强类型会话、命令、事件和错误；NAPI、XComponent NativeWindow、EGL/GLES 和 libmpv 保持内部实现。每个会话独立拥有命令队列、`mpv_handle`、渲染器和订阅表。
- **依据**：官方 XComponent 指南说明 NativeWindow 可承载 EGL/OpenGLES 和媒体渲染。以会话边界管理所有权可避免全局图形上下文、跨线程竞态和释放后回调。
- **备选方案**：公开 NAPI 或全局播放器单例；前者泄露内部实现，后者不能保障独立会话、切源与回收。
- **落实**：控制命令串行化；耗时解析、网络与 libmpv 等待不在 UI 线程运行；事件带每会话单调序列号；释放时依次拒绝新命令、撤销回调、解绑 EGL、终止 mpv、清空引用。

## 画面与兼容性

- **决策**：ArkTS XComponent 生命周期仅映射为 `attachSurface`、`resizeSurface`、`detachSurface`。NativeWindow/EGL 只在有效 surface 时段由渲染线程持有，并使用 surface generation 丢弃旧画面任务。
- **依据**：这样可安全处理零尺寸、重建、销毁和重复释放，且不让消费方持有 native 指针。
- **决策**：固定 API 15 安装、API 19 新增或敏感 API 审查、API 22 认证。高版本能力必须运行时探测并提供 API 15-18 降级记录。
- **备选方案**：仅以当前 SDK 编译成功判断兼容；不能证明安装下限、降级或认证条件。

## 供应链与发布

- **决策**：以全量不可变 `sources.lock.json` 替换现有 bootstrap，锁定全部直接/传递源码、补丁、归档 SHA-256、许可证、构建配置和工具链摘要；只执行受控下载、校验、补丁和离线构建。
- **依据**：当前 `native/scripts/build-libmpv-bootstrap.sh` 虽固定参考提交，仍执行其 `bundle.sh`；当前锁定文件也明确未覆盖传递依赖，不能作为生产发布输入。
- **备选方案**：持续使用固定 Git 提交 bootstrap；提交固定并不锁定运行时下载、子模块、补丁和工具链。
- **落实**：macOS/Linux clean build 均输出来源证明、能力清单、SBOM、LICENSE/NOTICE、SHA-256 与 ELF ABI/符号/动态依赖审计；任一缺失阻断候选。
- **决策**：tag 先生成一个不可变候选制品集合，再由同一 `release-manifest.json` 上传 GitHub Release 与批准私有 ohpm 源，双向回读一致后才标记已发布。
- **风险处理**：任一渠道失败保持 `candidate`/`failed`，不宣称已发布；不可变远端版本由批准的人工补偿处理。

## 引导构建故障与缓存

- **故障根因**：2026-03-07 的引导工作流在 FFmpeg 完成后构建 libxml2 `v2.15.1` 失败。固定参考仓库安装的 apt Meson `0.61.2` 不接受 libxml2 使用的 `c_std=c11,c99,c89` 选项组合，错误为“Value `c11,c99,c89` is not one of the choices”。这也说明参考仓库虽锁定提交，其运行时依赖版本仍会漂移，不能作为发布证据。
- **短期修复**：工作流固定安装 Meson `1.7.0`，使其先于系统 Meson 被解析；引导脚本在 Meson 或参考提交变化时清除相应中间构建目录，并始终检出并校验参考仓库提交。
- **缓存边界**：GitHub Actions 仅缓存 pip、Cargo registry/git、固定参考仓库下载的源码和可由完整 key 失效的中间构建目录。key 包含运行系统、ABI、OpenHarmony SDK、Meson 版本、来源锁、构建脚本与工作流内容。`dist/` 和上传工件绝不作为缓存输入，构建完成后仍重新生成并校验 SHA-256。
- **残余风险**：参考脚本仍按 tag 下载 libxml2、FFmpeg、MPV 等依赖，且会在线安装 Rust/cargo-c；缓存只降低耗时，不能补足来源可复现性。阶段 1 的正式发布链仍必须迁移为本仓库控制的传递依赖锁、归档 SHA-256、补丁与离线构建。

## 兼容验证与迁移

- **决策**：以独立 `consumer-smoke`、IJK 行为矩阵和消费方 `playerEngine=ijk|vidall` 功能开关推进迁移；本库绝不读取、修改、构建、提交或发布 VidAll_TV。
- **依据**：独立样例验证公开契约；矩阵将构建选项转化为设备、样本、行为、证据和三态结论。
- **落实**：矩阵覆盖媒体输入、WebDAV、SMB localhost HTTP、轨道/字幕、音频路由、硬解回退、跳转、控制与生命周期。未有 ARM64 真机证据的能力只能为“已构建待验证”或“不支持或暂缓”。

## HarmonyOS 原生边界与分层

- **决策**：将 ArkTS HAR 作为唯一消费者边界；示例以 ArkTS `XComponent` 承载画面，内部适配层把它的创建、尺寸变化和销毁转换为受限的 surface 命令。NativeWindow、NAPI、EGL/OpenGLES 及 `mpv_handle` 不进入公开 API，也不得由消费者缓存或跨线程传递。
- **依据**：本机 HarmonyOS 文档 `开发指南/.../napi-xcomponent-guidelines` 与 `API参考/.../ts-basic-components-xcomponent` 都将 XComponent 定义为可承载 EGL/OpenGLES 和媒体数据的 Surface；`native_interface_xcomponent.h`、`external_window.h` 和 Node-API 参考分别界定 Native XComponent、NativeWindow 与稳定的 ArkTS/Native 桥接边界。该设计使 UI 生命周期和原生资源所有权可分别审计。
- **备选方案**：直接向 ArkTS 暴露 native handle，或使用全局单例渲染器。前者会绕过线程和释放约束，后者不能满足 FR-001 的独立会话与图形上下文要求，均不采用。
- **API 15/19/22 处理**：实现开始前必须逐项查询所用 XComponent、NativeWindow、NAPI、EGL 和系统能力的 API 可用性；API 19 以后才可用或行为变化的调用必须经运行时探测封装，并为 API 15--18 记录拒绝、无操作或软件降级。不以当前 API 22 编译通过替代该审查。

## 原生线程、状态和渲染释放

- **决策**：每个会话持有单独的命令串行队列、事件序号、`mpv_handle`、渲染资源和回调登记；UI 线程只发起短操作，原生工作线程处理媒体命令和 libmpv 事件，渲染线程独占 NativeWindow/EGL/GLES。跨线程通知只传递脱敏、可序列化事件，并在 ArkTS 侧验证会话和单调序号。
- **依据**：XComponent/NativeWindow 生命周期可在尺寸为零、重建和销毁时变化；把 surface generation 和会话状态一起校验，可丢弃旧 surface 的渲染/事件任务，避免释放后使用。Node-API 返回值必须逐次检查并转换为稳定 `native`/`lifecycle` 错误。
- **备选方案**：在 ArkUI UI 线程同步调用 libmpv，或由任意线程直接操作 EGL。前者违反宪章的 UI 响应性要求，后者容易造成上下文竞态、死锁或崩溃，均不采用。
- **释放结论**：首次 `release()` 原子地封闭命令入口，停止事件源，注销 NAPI 回调，解绑和销毁 EGL surface/context/display，终止 mpv，再清空引用；后续调用是无操作。实现须用压力测试和 ARM64 真机证据证明这一顺序。

## 供应链、法律与 ELF 审计

- **决策**：候选构建只接受一个完整 `sources.lock.json`：每个直接和传递源码/归档、子模块、补丁、许可证文本来源、工具链、容器或系统镜像以及构建开关都须有不可变身份、SHA-256、下载位置、许可证标识和用途。候选同时生成 SPDX 或 CycloneDX SBOM、LICENSE 汇集、NOTICE、许可证结论、来源证明和每个工件的 SHA-256。
- **依据**：现有 `native/config/sources.lock.json` 仅列出两个参考来源，且 `native/scripts/build-libmpv-bootstrap.sh` 会执行外部仓库的 `bundle.sh`；现有 `.github/workflows/build-libmpv.yml` 只做一个 Ubuntu 构建、文件存在与 SHA 校验。这些事实不能证明传递输入、补丁、工具链、许可证或可重现性，因此当前 bootstrap CI 明确为不可发布引导基线。
- **备选方案**：只锁定 Git commit、只保留预编译 `libmpv.so`、或把 SBOM/NOTICE 作为发布后的人工附件。它们分别无法锁定运行时下载、不能从源重建、或会使发布缺少可审计证据，均不采用。
- **ELF 结论**：构建脚本必须在候选前检查 `aarch64-linux-ohos` 架构、ELF ABI、SONAME/NEEDED 动态依赖白名单、导出符号白名单和禁止符号；审计 JSON 连同命令版本和输入 SHA 进入 manifest。任何偏差、未知依赖或审计工具缺失必须非零退出。

## 候选、审批、双渠道回读

- **决策**：受保护 tag 只创建一次不可变候选目录和 `release-manifest.json`；批准后只上传该目录中的同一 HAR、原生库、SBOM、NOTICE、能力证据和校验文件到 GitHub Release 与批准的私有 ohpm 源。上传后分别回读版本、来源提交、HAR SHA-256、SBOM SHA-256 和发布说明摘要，完全相等才产生 `published` 回执。
- **依据**：双渠道若各自重建，会引入同标签不同字节和供应链分叉；以候选清单为唯一事实源可使审批、回滚和故障处置可追踪。
- **备选方案**：两条工作流独立构建后分别发布，或先发布一个渠道再补另一个。前者不能保证一致，后者会暴露半发布版本，均不采用。
- **失败规则**：无批准、无最小权限凭据、门禁缺失、上传失败或回读不一致时只保留 `candidate` 或写入 `failed` 诊断；绝不宣称发布成功。已上传的不可变版本由批准的人工补偿流程处理，仓库不保存制品源名、凭据或审批人身份。

## 能力证据与 IJK 隔离迁移

- **决策**：能力的唯一状态为“已通过真机样本”“已构建待验证”“不支持或暂缓”。每个结论绑定 SDK/组件版本、锁定摘要、ARM64 TV 设备匿名标识、API 层、测试素材匿名标识、执行时间、指标、日志摘要和限制。IJK 行为矩阵由经授权的基线证据填写，VidAll_Player 仅提供独立 consumer-smoke 和消费方可选 `playerEngine=ijk|vidall` 开关契约。
- **依据**：编译成功不能证明电视硬解、字幕、HDR、音频路由或网络恢复实际可用；在本仓库独立验证并让开关归消费者所有，可避免改动 VidAll_TV 并允许灰度回退。
- **备选方案**：以构建选项声明支持，或在本仓库直接改 VidAll_TV 验证。前者会误报能力，后者违反范围和 FR-040，均不采用。
- **ARM64 门禁**：API 22 ARM64 TV 上必须安装 API 15 兼容包，执行 100 次核心生命周期冒烟以及来源、遥控器、后台、网络和释放用例。没有该真机证据，候选不得进入发布审批。
