# 实施与宪章检查

使用官方 SDK 的 `OH_AudioStreamBuilder_SetRendererCallback`（API 10）一次注册旧系统的写入和中断回调；API 20 以上沿用 `SetRendererWriteDataCallback`。音频线程仅投递当前 AO 的原子事件，mpv 播放线程负责设置文件局部暂停，并沿用 Player 已观察的 pause 属性。旧系统每个文件独占 AO，中断状态随文件清理。注册失败走既有初始化清理路径。

宪章检查覆盖版本分流、线程边界、生命周期、最小权限、中文记录和测试先行。该修复位于播放器音频输出层，无 UI、存储或额外权限。复用锁定 mpv 源码和既有 FFmpeg 动态库，只编译 mpv。R1–R3 先用宿主替身和实际 ARM64 ELF 检查，再以 API 19、API 20 模拟器验证。R4 以 iMac CI 的原始 HAR 以及同一 HAR 的消费复测为准。

## 核心重建与核验

从 `ErBWs/mpv@6edeee00a07b9b76f197aa71eee3d029fb090de4` 干净检出，在独立目录应用 `native/patches/mpv/0001-ohaudio-legacy-interrupt.patch`（SHA 见来源锁）。Meson 使用兼容版 arm64-crossfile、既有静态依赖及 9 月 23 日交付的六个 FFmpeg 动态库，通过 pkg-config 引用配套头文件（含 OHCodec 公共头）。构建参数沿用兼容基线的 opensles=disabled、ohos/egl-ohos/vulkan/shaderc/lua=enabled、gpl=true、build-date/cplayer=false、manpage-build=disabled、default-library=shared。Ninja 编译 mpv，Meson 安装并 strip，再用 SDK llvm-strip --strip-unneeded。补丁也接入原有 bootstrap 构建入口。

本次使用本机 DevEco Studio 自带 OHOS clang 15 编译核心。与 #84 包中 libmpv 比对，无导出删改；仅新增导入 OH_GetSdkApiVersion 和 OH_AudioStreamBuilder_SetRendererCallback，新增依赖 libdeviceinfo_ndk.z.so（版本查询自 API 10 可用）。OHCodec 硬解符号配对校验通过。核心 SHA 见 CI 输入锁；HAR 由 CI 使用该锁定输入完整构建。
