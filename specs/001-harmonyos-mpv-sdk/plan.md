# VidAll_Player HarmonyOS/OpenHarmony TV libmpv 组件库实施计划

**分支**：`001-harmonyos-mpv-sdk` | **日期**：2026-07-21 | **规格**：[`spec.md`](./spec.md)

## 概述

将当前应用骨架演进为独立、可版本化、可审计的 ArkTS/ohpm 库 `@vidall/player`（最终包名须在批准的私有制品源登记后冻结）。库以严格类型化 ArkTS 门面隔离 NAPI、XComponent NativeWindow、EGL/GLES 与 libmpv，为独立播放会话提供受控媒体输入、明确状态机、事件和错误契约。交付可复现 ARM64 `aarch64-linux-ohos` 构建、供应链证据、独立消费者样例、能力/兼容矩阵和候选制品双渠道发布设计；当前 bootstrap CI 明确是必须替换的风险基线，不可作为发布证据。

## 技术上下文

**语言/版本**：ArkTS（HarmonyOS Stage 模型）、C/C++17（NAPI、EGL/GLES、libmpv）、Bash/Python 3（受控构建和审计）；所有公开 ArkTS 类型显式声明。

**主要依赖**：HarmonyOS SDK/Hvigor/ohpm，XComponent 与 NativeWindow，Node-API/NAPI，EGL/OpenGLES，锁定提交和 SHA 的 libmpv 与其全部传递依赖；SBOM 生成器与 ELF 审计工具作为受控工具链输入。

**存储**：运行时仅保存会话状态和经系统安全存储引用的 WebDAV 配置；构建保存机器可读 JSON 证明、SBOM、LICENSE/NOTICE、SHA、能力和兼容矩阵；不保存明文凭据。

**测试**：ArkTS 单元测试、NAPI/C++ 单元测试、契约测试、隔离消费者集成测试、受控网络服务测试、macOS/Linux 清洁构建测试、ARM64 TV 真机手工与自动化证据；由 `devecocli build` 执行 HarmonyOS 构建。

**目标平台**：ARM64 `aarch64-linux-ohos` TV 真机为首期承诺；组件 API 15 安装兼容、API 19 新增/敏感 API 审查、API 22 认证；手机仅为示例可安装验证，x86_64 模拟器和 Vulkan 不在承诺范围。

**项目类型**：可发布 HarmonyOS ArkTS/ohpm 库，附带 TV/手机示例、原生库、构建/发布自动化与独立消费者验证。

**性能目标**：不在 ArkUI UI 线程执行媒体解析、网络或阻塞原生调用；首帧、跳转、缓冲恢复、CPU、内存和长播稳定性按设备/样本记录，不以未测阈值承诺支持。

**约束**：独立播放器、独立图形上下文；可重复释放；所有上游与传递依赖不可变锁定；发布物必须含 SBOM、许可证结论、NOTICE、SHA、ELF ABI/符号/动态依赖审计、能力三态和双渠道一致性回读；绝不修改、构建、提交、发布 VidAll_TV。

**规模/范围**：一套公开 SDK、ArkTS/NAPI/渲染分层、ARM64 原生构建供应链、样例/消费者验证、IJK 行为矩阵和发布工作流。RTSP、UDP、SRT、RTMP、Vulkan、杜比视界和音频直通不在首期默认支持。

## 宪章检查

### Phase 0 前门禁

| 宪章要求 | 设计响应 | 结论 |
|---|---|---|
| HarmonyOS 原生与 API 兼容 | 使用官方 XComponent/NativeWindow/NAPI；固定 API 15/22 并以 API 19 审查和降级记录约束新增能力。 | 通过 |
| TV 交互 | TV 示例规定遥控器、焦点和返回键验收；SDK 本身不持有页面焦点。 | 通过 |
| 组件、状态、资源 | ArkTS 门面、会话控制、NAPI 桥接、渲染器和供应链工具职责分离；会话状态机、surface 世代和释放顺序明确。 | 通过 |
| 媒体可靠性 | 显式八态、串行切源、脱敏结构化错误、网络/文件输入校验、线程边界和释放规则均为契约。 | 通过 |
| 安全与隐私 | 不允许 URL 用户信息；认证头仅运行时内存；日志/事件/发布物脱敏；凭据最小权限注入。 | 通过 |
| 性能与质量 | UI 线程禁止阻塞任务；清洁构建、单元/契约/集成/真机门禁和资源审计纳入候选门禁。 | 通过 |
| 中文文档与交付纪律 | 本功能文档、矩阵、发布/风险/验收记录均使用中文；法律及协议原文保留并加中文说明。 | 通过 |

**Phase 0 结论**：无未解决澄清项或需要例外的宪章违反。现有 bootstrap CI 的不完整供应链控制是已识别风险，实施必须替换，不能以现状绕过门禁。

## 项目结构

### 文档

```text
specs/001-harmonyos-mpv-sdk/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    ├── arkts-sdk.md
    ├── release-manifest.md
    └── compatibility-matrix.md
```

### 目标源码与交付结构

```text
packages/vidall-player/                 # 可发布 ArkTS/ohpm HAR 库
├── Index.ets                           # 唯一公开导出
├── src/public/                         # 类型、控制器、错误与事件门面
├── src/xcomponent/                     # ArkTS XComponent 生命周期适配
├── src/internal/                       # 输入校验、命令串行化、状态映射
├── src/native/                         # NAPI 声明；不对消费者导出
├── oh-package.json5
└── build-profile.json5

native/
├── bridge/                             # NAPI 导出和 ArkTS 事件派发
├── session/                            # 每会话 mpv 所有权、命令队列、状态
├── render/                             # NativeWindow、EGL/GLES、surface 世代
├── media/                              # libmpv 配置、受控头部、轨道与错误映射
├── include/                            # 内部 C++ 头文件
├── tests/                              # 原生单元与生命周期测试
├── config/                             # 完整 sources.lock、白名单、构建配置
└── patches/                            # 已锁定上游补丁

examples/tv-phone-demo/                 # TV/手机最小示例，遥控器可达
examples/consumer-smoke/                # 只通过公开 ohpm 契约验证的隔离消费者
scripts/
├── build/                              # 清洁、可复现 macOS/Linux 构建
├── audit/                              # SHA、ELF、符号、动态依赖、敏感信息审计
├── evidence/                           # 能力和真机证据校验
└── release/                            # 候选制品、双渠道发布和回读

release/                                # 由 CI 生成且不提交的候选/发布证明
├── manifests/
├── sbom/
├── licenses/
├── capabilities/
└── audits/

.github/workflows/
├── verify.yml                          # PR 验证，不使用 bootstrap
├── candidate.yml                       # tag 候选制品与审批输入
└── publish.yml                         # 批准后双渠道上传与回读
```

**结构决策**：以库、原生实现、示例、脚本和生成证明五个边界隔离职责。`entry/` 现有应用骨架只能作为迁移来源或示例宿主，不能作为库公开接口；不在本计划中修改任何 VidAll_TV 路径或仓库。

## 实施阶段

### 阶段 A：建立库边界与公开契约

1. 创建 `packages/vidall-player` HAR 包并固定模块/包元数据，所有库依赖通过 lockfile 精确锁定。
2. 按 `contracts/arkts-sdk.md` 实现 `createPlayer`、`VidAllPlayer`、状态、事件、错误、媒体来源与轨道类型；禁止 `any`、不安全断言和公开 native handle。
3. 实现 ArkTS 命令串行器、输入/头部/重定向信任范围校验、错误脱敏器和事件顺序检查；为所有命令写明前置条件、失败条件、释放后行为与幂等性。
4. 将 XComponent 的创建、尺寸变化、销毁仅适配为 surface 附着/调整/分离，不把 NativeWindow 传给消费方。
5. 为 API 15/19/22 建立审查表和运行时特性探测封装；高版本能力必须有 API 15-18 降级及可验证记录。

**验收**：契约测试能覆盖状态迁移、重复 stop/release、无效 URI、零尺寸/销毁 surface、乱序事件与脱敏错误。

### 阶段 B：实现 NAPI、会话与渲染生命周期

1. 建立每会话独立的 `mpv_handle`、受控命令队列、订阅表和渲染实例；禁止全局播放器和全局 EGL context。
2. 在 NAPI 桥接层建立线程安全事件投递，所有 libmpv 事件先进入原生队列，再按会话序号进入 ArkTS；释放时撤销投递并使旧任务失效。
3. 在渲染线程管理 NativeWindow、EGLDisplay、EGLContext、EGLSurface 和 libmpv render API；以 surface generation 防止销毁后使用。
4. 按固定顺序完成释放：拒绝新命令、停止媒体/回调、解绑渲染、销毁 EGL surface/context/display、终止 mpv、清除 NAPI 引用和队列。
5. 映射本地/HTTP(S)/HLS/DASH/localhost 代理、轨道、外挂字幕、硬解回退和错误；网络认证头不写入 URL、日志或持久化。

**验收**：原生单元与集成测试证明独立会话、切源、surface 重建、后台/异常释放、连续控制、无悬垂回调；所有长耗时路径不在 UI 线程执行。

### 阶段 C：替换 bootstrap 为受控可复现构建

1. 以全量 `sources.lock.json` 替换当前只锁定参考提交的清单，覆盖 libmpv、ffmpeg/依赖、子模块、补丁、归档 SHA-256、许可证、工具链/容器摘要和构建开关。
2. 用受控下载、校验、补丁应用和离线构建脚本替换 `native/scripts/build-libmpv-bootstrap.sh`；禁止执行未审计上游仓库的下载脚本作为发布输入。
3. 产出 `aarch64-linux-ohos` 原生库和 HAR，生成来源证明、能力清单、SHA、CycloneDX 或 SPDX SBOM、LICENSE/NOTICE、许可证结论、变更日志与已知限制。
4. 实现 ELF 审计：确认架构、ABI、导出符号白名单和动态依赖白名单；对不允许项返回非零。
5. 在 macOS 与 Linux 空目录执行清洁构建，记录输入和差异解释；预编译库只可用作对照，不能成为唯一生产输入。

**验收**：任何浮动依赖、哈希不匹配、缺少许可证/SBOM/审计结果或平台输出不一致都会阻断候选。

### 阶段 D：示例、消费者和兼容证据

1. 建立 TV/手机最小示例，封装 WebDAV 安全配置、目录选择、XComponent 画面、播放错误、重试、资源释放；TV 页面对遥控器焦点、确认和返回明确验收。
2. 建立隔离 `consumer-smoke`，仅从批准私有 ohpm 源安装候选 HAR，验证“创建 -> 附着 -> 加载 -> 播放 -> 释放”，不得访问 `native/` 或任何 VidAll_TV 内容。
3. 建立 IJK 兼容矩阵，以 `contracts/compatibility-matrix.md` 列出媒体浏览、WebDAV、SMB localhost HTTP、音轨/字幕、音频路由、硬解回退、跳转、控制和生命周期；每行关联 SDK、样本、设备、证据和三态。
4. 定义由消费方持有的 `playerEngine=ijk|vidall` 渐进迁移开关与回退规则。本库只保证公开契约，不修改 VidAll_TV。
5. 记录本地/HTTP(S)/WebDAV/HLS/DASH/SMB 样本、容器/编解码器、字幕、4K/10-bit/60fps/HDR/高规格音频的真机结论，未实测只能标“已构建待验证”或“不支持或暂缓”。

**验收**：一台 ARM64 TV 的 API 22 真机运行 API 15 兼容包，完成媒体、网络、生命周期、遥控器和资源释放门禁；一台可安装手机完成示例基本验证。

### 阶段 E：候选制品与双渠道发布

1. 将现有 `.github/workflows/build-libmpv.yml` 作为待删除风险基线，替换为 PR 验证、tag 候选和批准发布三条受控工作流；所有 action 和构建工具同样锁定不可变版本/摘要。
2. 受保护 tag 只生成一个不可变候选制品集合及 `release-manifest.json`，先完成构建、审计、敏感信息扫描、安装和真机证据校验，再请求批准。
3. 批准后使用同一候选清单上传 GitHub Release 和批准私有 ohpm 制品源；私有源名称、凭据和审批人不写入仓库。
4. 两渠道完成后回读版本、来源提交、HAR SHA、SBOM 和发布说明；完全一致才写入 `published` 回执。
5. 任一上传或回读失败保留 `candidate`/`failed`，输出脱敏处置报告，不宣称已发布；不可变远端版本仅由批准人工补偿流程处理。

**验收**：发布流在无凭据/审批时安全失败；两个渠道的回读一致率为 100%；任何门禁缺失均不能发布。

## 测试与发布门禁

| 层级 | 必测场景 | 阻断条件 |
|---|---|---|
| ArkTS 单元/契约 | 状态、命令前置、输入、错误脱敏、事件序号、幂等释放 | 未覆盖释放/错误/边界，或类型检查失败。 |
| 原生单元/集成 | 会话隔离、线程投递、surface 世代、EGL 释放、libmpv 错误映射 | 泄漏、死锁、使用已释放对象、UI 线程阻塞。 |
| 网络媒体 | WebDAV 认证、TLS/SNI、重定向、Range、chunked、超时、DNS、重试和 localhost 代理清理 | 敏感信息泄露、跨信任范围带认证重定向、不可恢复状态。 |
| 消费者 | 私有源安装、公开 API 冒烟、没有内部依赖 | 未安装、引用内部实现或需要改 VidAll_TV。 |
| 构建供应链 | macOS/Linux clean build、锁定、SBOM、NOTICE、SHA、ELF 审计 | 浮动依赖、哈希/ABI/符号/动态依赖不匹配。 |
| ARM64 TV 真机 | API 15 安装、API 19 审查、API 22 认证、遥控器、播放/切源/重建/后台/网络/释放 | 缺少证据，或未验证能力标记为支持。 |
| 发布 | 候选批准、GitHub/私有 ohpm 上传和回读 | 双渠道任一失败或清单不一致。 |

## Phase 1 后宪章复核

- 公开 SDK、数据模型、错误/事件和发布清单均有显式类型与中文文档，符合原生优先、可维护性和交付纪律。
- 会话状态、线程边界、surface 世代、NAPI/EGL/libmpv 所有权和释放顺序已在契约与数据模型中定义，符合媒体可靠性和资源管理。
- TV 交互责任限定在示例并列入真机焦点/返回验收；SDK 不承担页面状态，符合组件边界。
- 输入、认证头、日志、SBOM、制品与 CI 凭据均定义最小化与脱敏约束，符合安全与隐私。
- API 15 安装、API 19 审查、API 22 认证以及 ARM64 真机三态证据、macOS/Linux 构建与发布阻断均已设计；无宪章例外。

## 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 参考 bootstrap 仍隐式下载上游输入 | 不可复现、许可证与安全证据失效 | 阶段 C 完全锁定来源并禁止 bootstrap 进入候选流程。 |
| 目标 TV 与硬解/字幕行为差异 | 能力误报或播放失败 | 用设备/样本三态矩阵、软解回退和真机门禁，不作未证实承诺。 |
| 双渠道发布部分成功 | 消费方看到不一致版本 | 只从同一候选清单发布、回读后标记发布、失败保持候选并人工补偿。 |
| NAPI/EGL/画面销毁竞态 | 崩溃、死锁、泄漏 | 会话队列、surface 世代、线程隔离、明确释放序与压力测试。 |
| 集成方错误迁移 IJK 行为 | 业务回归 | 独立消费者样例、行为矩阵与消费方功能开关回退；不修改 VidAll_TV。 |

## 复杂度跟踪

无宪章违反需要豁免。NAPI、EGL/GLES 和 libmpv 的组合是实现原生播放器、独立渲染和 ARM64 支持的必要复杂度；ArkTS 公开面仍保持受限且可替换。
