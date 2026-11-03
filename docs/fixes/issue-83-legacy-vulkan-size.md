# #83：旧基线 Vulkan 尺寸通知修复

## 范围

本轮从 `0ad5d6d3b52a39b342a50a413d4440f184107a22` 建立 `codex/legacy-vulkan-size-83`，仅修复 `NativeSession::Resize` 在 Vulkan 路径未通知渲染端新尺寸的问题。该源码对应 TV 现用 HAR：SHA-256 `826b667dcd315e75e71f89065c3aef4bd60ea73743916ee629469f93228c66a9`，7,400,880 字节。

生产代码在 `Resize` 方法外逐字节保持旧基线；方法内的非 Vulkan 分支也保持原样。ArkTS、公开 API、初始化、GL/SW、completed 通知及旧核心行为均未变更。本轮不引入进程退出策略。更广的旋转、暂停重绘与播完通知属于 #84，须等 #83 消费方验收反馈后继续。

## 实现

Vulkan 的本地渲染线程已返回，不能依靠 `geometryDirty_` 唤醒它。本次在持有生命周期锁期间：

1. 对现有 `OHNativeWindow` 设置新 buffer geometry。
2. 向旧 libmpv 已支持的 `ohos-surface-size` 属性提交 `宽x高`，由核心和 VO 更新尺寸。
3. 两步都成功才保存会话宽高。属性失败时回滚窗口尺寸；回滚也失败则标记 renderer 不可用，拒绝后续播放和 resize，等待重新 Attach。
4. 记录请求、返回值、代际和 VO 报告尺寸。VO 尺寸读回仅作诊断，不代表新帧已提交或 GPU 已完成。

生命周期锁使 Detach/Release 不会在这次通知途中改变当前窗口。未修改已有 GPU 故障处理机制；旧基线限制仍然存在。

## 构建与运行库

使用完整 Player 工程和 `devecocli build --modules vidall_player@default` 生成 HAR，没有修改或替换产物中的单独成员。

构建机为 DevEco Studio 26.0.0.851，Native SDK 26.0.0.105，CLI 1.3.4，debug/default，ABI 保留 arm64-v8a 和 x86_64。x86_64 仍仅为 NAPI 探针，没有 libmpv 播放能力。目标 API 22、最低 API 15 不变；生成元数据的 compileSdkVersion 为 26.0.0.105，apiReleaseType 从 Beta1 变为 Release，须由消费方重新完成设备兼容性验收。

使用 `OHOS_STL=none` 禁止当前 SDK 自动替换 C++ 运行库，显式链接并打包原有运行库；CMake 在构建前校验 SHA-256。ARM64 运行库及 libmpv 已在旧基线源码树中，x86_64 运行库从上述已验明哈希的原 HAR 提取为构建输入并纳入维护分支。该输入提取不是对新 HAR 的事后替换。

| 构建输入 | SHA-256 |
| --- | --- |
| ARM64 libmpv | `3ae9969ac13a58aaa5827520a44e56461f566aff66b9bdd7fe4b78f0da31b076` |
| ARM64 libc++ | `9b67147034bfc1d2b7b51b97b638713f90bd8ca9cf4acbcdac6cbc6d155f6042` |
| x86_64 libc++ | `c65b4e92e52bdbf170d0c11a02c2e3b280fd140c4b8a764e40d8d4875e5ce944` |

FFmpeg 继续由宿主负责，HAR 没有增加 FFmpeg、curl 或 smb2。两种 ABI 的 NAPI bridge 均经完整重编译；动态库依赖和导入符号集合与旧 HAR 完全相同。旧 bridge 已有的 C++ `abort` 导入保持不变，不应把“没有新增退出策略”解释为“任何故障都不会退出”。

## 验证

先执行新测试，旧实现能编译但在 Vulkan 通知、回滚、重试、连续旋转与并发 Detach 等断言失败。修复后 15 个场景通过，包括旧 GL/SW 分支保持原行为的断言。窗口、mpv、EGL 为主机替身，实际编译执行生产 `Resize`，不能代替设备 Vulkan swapchain 验证。

复现命令：

```sh
python3 native/tests/vulkan-size/resize.test.py packages/vidall-player/src/main/cpp/napi_init.cpp
python3 native/tests/legacy-runtime.test.py
cmake -S native/tests -B /tmp/vidall-legacy83-tests
cmake --build /tmp/vidall-legacy83-tests -j 4
ctest --test-dir /tmp/vidall-legacy83-tests --output-on-failure
node native/tests/diagnostics-session.test.cjs
node native/tests/diagnostics-device.test.cjs
```

节点测试的 `TYPESCRIPT_PATH` 可显式指向 TypeScript 5.6.3。交付目录另含最终测试记录、源代码补丁、HAR 成员比较、工具链哈希、ABI 审计和独立消费工程打包证据。

尚需消费方验收：先模拟器加载/旧流程，再云平板与 TV 的 Vulkan 播放、旋转/窗口尺寸变化、退出/重进和必要日志。当前主机测试与消费 HAP 构建不等于设备播放验收；不得沿用此前实验 HAR 的设备结论。

## 最终 CI 交付要求（2026-11-03 补充）

上述本地构建仅用于提前验证，最终交付必须使用本分支 GitHub Actions `test-player.yml` 生成的 `legacy83-ci-har-<提交>-<尝试>` 附件。该流程在受控 DevEco 运行器完整编译 Player HAR，不编译 FFmpeg、不触发其他项目。CI 实际 Studio/SDK/编译器版本、源码提交、run URL、库哈希和 ABI 核对结果写入附件 `manifest.json`，不能用本地预验证工具链记录代替。

CI 依次完成主机测试、完整构建、当前提交身份及旧核心/运行库校验，成功后才上传 HAR。设备验收仍由消费方使用该 CI 产物重新执行。若后续发现 FFmpeg 变更需求，只向用户说明职责边界，由用户安排 `ohos_ijkplayer` 流程。
