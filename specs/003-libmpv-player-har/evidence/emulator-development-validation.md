# 模拟器开发期验证记录

- 候选：本地工作树中的未发布 HAR；不分配发布 candidateId。
- 设备：`Huawei_TV`，序列号 `127.0.0.1:5555`，TV ARM64 模拟器。
- ABI 证据：设备命令 `uname -m` 返回 `aarch64`；已安装应用的 `bm dump` 显示 `cpuAbi: arm64-v8a`。
- 日期：2026-08-03。
- 目的：验证 HAR、独立 fixture 与公开入口的 ARM64 native 会话创建/释放，以及 XComponent attach/detach 的开发期生命周期回归；不验证媒体播放、首帧或渲染线程。

## 已执行的开发验证

| 项目 | 结果 | 说明 |
| --- | --- | --- |
| `devecocli build --modules vidall_player libmpv_player_consumer libmpv_player_consumer@ohosTest` | 通过 | HAR、仅依赖 `@vidall/player` 根入口的 TV fixture 与 Hypium 测试模块均成功打包；XComponent adapter 使用显式名义类型 wrapper，consumer 可在不访问内部 bridge 的情况下传入公开播放器。 |
| HAR 内容检查 | 通过 | 包含 `package/libs/arm64-v8a/libmpv.so` 与 `package/libs/arm64-v8a/libvidall_player_native.so`。 |
| 安装 fixture 与 `libmpv_player_consumer_test` | 通过 | 已在 `127.0.0.1:5555` 重装主模块和测试模块。 |
| `aa test -b com.yaoshining.vidallplayer -m libmpv_player_consumer_test -s unittest OpenHarmonyTestRunner -w 60` | 通过 | 6 项通过、0 失败、0 错误：公开入口会话创建、重复 stop/release、release 后 load/play/attach/resize/detach 控制拒绝、订阅关闭与新会话恢复；并覆盖未附着、零尺寸、陈旧 generation 及 adapter 参数校验的 XComponent 错误路径。 |
| `native/tests/fixture-public-import.test.sh` | 通过 | fixture 页面及测试仅导入 `@vidall/player`，未引用内部、NAPI 或 entry 路径。 |
| `native/tests/har-native-packaging.test.sh` | 通过 | HAR 包含 ARM64 libmpv 与受控 native bridge 静态边界。 |
| `native/tests/contract-baseline.test.sh` | 通过 | 内部 CTest 11/11 通过，且静态基线未发现 AVPlayer 回退。 |

## 限制与结论

本次结果证明开发期 ARM64 模拟器能加载 HAR 内的 libmpv，并完成真实 native session 的创建、释放与重复释放，以及 XComponent attach/detach 的公开错误路径回归。最新重建、重装后复跑确认 XComponent 从 `XComponentController.getXComponentSurfaceId()` 取得实际 Surface ID，NAPI 模块加载成功，6 项 Hypium 回归通过（0 失败、0 错误），且启动后近期 crash 查询未返回本 bundle 的新崩溃。修复事件线程稳定句柄后，fixture 可持续运行。它不表示已完成 NativeWindow/XComponent、EGL/GLES、媒体加载、播放控制、mpv 事件循环、真实资源释放时序或首帧验证。

本记录不关闭 G1、G2 或 G3，不构成发布批准、TV 支持声明、供应链审核、ELF 审核、真实设备播放或首帧证据。候选仍保持未发布和阻断状态。
