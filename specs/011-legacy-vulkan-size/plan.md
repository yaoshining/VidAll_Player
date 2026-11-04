# 实施计划：旧基线 Vulkan 尺寸通知与 CI HAR 交付

**分支**：`codex/legacy-vulkan-size-83` | **日期**：2026-11-03 | **规格**：[spec.md](spec.md)

## 方案摘要

在旧基线 `NativeSession::Resize` 的 Vulkan 分支，持生命周期锁依次设置 NativeWindow geometry 与 `ohos-surface-size`。两者成功再提交会话宽高；失败回滚，回滚失败则标记不可用。其他原生方法和 ArkTS 不变。先以自动化回归、本地完整 HAR 和隔离消费工程验证，再推送本项目专用 CI；最终交付只使用 CI 附件。

## 技术背景

- C++17/NAPI、既有 ArkTS、旧 libmpv；无新增公开接口或系统 API。
- 原 geometry、mpv 属性设置调用及异步 NAPI 边界已经存在；本轮只补 Vulkan 调用路径，不新增 UI 线程阻塞接口。
- 最低 API 15、目标 API 22；API 19 兼容策略保持原样，设备证据仍待本轮验证。
- 测试采用生产函数提取编译的平台替身、CTest、TypeScript 5.6.3 会话测试、真实 HAR 的 tar/ELF 审计。
- 不增加存储、权限、UI 或焦点逻辑；既有遥控和返回流程由消费方按原流程回归。
- 保持两个 ABI；x86_64 仅 NAPI 探针。CMake 固定旧 C++ 库并拒绝漂移，禁止 SDK 自动注入新运行库。
- 本修复分支恢复 `[self-hosted, macOS, deveco]` iMac CI，使用既有 Studio 和锁定 CLI 1.3.4；记录实际运行器及 Studio/SDK/编译器身份。
- 不修改 `deveco26-build` 的分支准入或主线批准值，不新增 `LEGACY83_APPROVED_EVENT_SHA`；本分支不使用该云端环境或私有归档凭据。
- 用户明确普通分支直接使用 iMac CI；现有 `8350234e…` HAR 恢复为 #83 验收候选，继续消费端验证，无需等待重建。

## 宪章检查（研究前及设计后复核）

| 原则 | 处理与证据 |
| --- | --- |
| 原生优先、兼容性 | 使用既有 OHNativeWindow/mpv API；无新 API 或版本提升；设备覆盖待 T011 |
| 状态、线程和释放 | lifecycle 锁保护通知；失败不提交尺寸；并发 Detach 测试；不扩大资源所有权 |
| 错误处理与安全 | 返回错误、失败回滚、不可用封闭；日志仅会话/代际/尺寸/返回码 |
| TDD | 旧实现先在新增测试中失败，最小代码后通过；CI 审计及流程也先增加失败测试 |
| 文档与追踪 | 本目录 spec/plan/tasks/contracts 对应源代码、测试与证据；补建时序如实记录 |
| TV 验收 | CI 只交付候选，不冒充设备通过；T011 未完成前不关闭 #83、不启动 #84 |
| 职责边界 | mpv/Player 范围内；FFmpeg 不变，不调用其他项目 |

设计检查无新增宪章例外；旧基线既有 GPU 故障限制保留并明确，不借本轮声称已解决。范围/方案使用用户既有确认；后续如需改 FFmpeg，须先报告而不能扩展实施。

## 阶段与文件

1. 规格和设计：本目录 `spec.md`、`research.md`、`data-model.md`、`contracts/delivery.md`、`quickstart.md`。
2. US1 测试及最小修复：`native/tests/vulkan-size/resize.test.py`、`packages/vidall-player/src/main/cpp/napi_init.cpp`。
3. 构建输入固定：`native/cmake/legacy-cxx-runtime.cmake`、`native/tests/legacy-runtime.test.py`、模块 CMake/profile 和旧 x86_64 runtime 输入。
4. US2 测试及 CI：`scripts/test/legacy83-ci/`、`.github/workflows/test-player.yml`；严格测试→构建→审计→上传。
5. 交付：保存 CI run/源码/哈希；通知 TV 会话使用最终 CI 包，待消费端验收回执。

## 复杂度与回退

不迁移正常核心或 #84 草案；不生成新退出策略。修复分支独立，未合并主线。消费端可回退到哈希 `826b667d…` 的旧 HAR；本地预验证包不能作为最终交付。CI 没有修改其他仓库的权限或步骤。

云端 SDK 工具准备代码从主线 `a3d4812` 原样复用；不执行正常核心的 evaluate build，不导入新核心/运行库，不编译 FFmpeg。这些工具作为历史云端尝试保留，本分支当前工作流不调用它们；HAR 仍由旧基线的 default target 完整构建。

## 主线集成

旧基线构建配置、固定库和 CI 脚本可从[兼容分支归档](https://github.com/yaoshining/VidAll_Player/tree/32bb822)复现。主线从 `a3d4812` 接入同一段 Vulkan Resize 逻辑，沿用正常核心现有的运行时准入检查。PR 的宿主回归增加终局拒绝场景。设备回执对应旧基线的 CI 哈希。

## PR 验证与手动云构建

主线集成使用同仓 PR 的合并预览提交在 iMac 上完整构建并验证消费工程。主线推送执行原有云端门禁。手动从主线发起的云构建接受仓内目标分支，审批绑定已解析的提交，入口和操作步骤见 AGENTS.md。
