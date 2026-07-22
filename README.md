# VidAll_Player

HarmonyOS TV `libmpv` 播放 SDK 的受控构建项目与最小应用示例。

## 当前状态

- 初始 HarmonyOS 应用可构建并在启动时输出 `VidAll_Player` 生命周期日志。
- 支持手机和 TV 安装声明；`compatibleSdkVersion` 为 HarmonyOS 5.0.3 / API 15，`targetSdkVersion` 为 API 22。
- GitHub Actions 从固定提交的 OpenHarmony `libmpv` 源码构建流程生成 ARM64 `libmpv.so` 与 SHA-256 文件；构建下载和中间目录会按系统、ABI、SDK、Meson 版本及锁定输入缓存，不缓存最终发布制品。
- 当前为构建骨架，未接入 NAPI、XComponent、WebDAV 浏览或实际播放能力；这些能力均为“已构建待验证”或尚未实现，不能视为已支持。

## 本地构建应用

```bash
devecocli build
```

连接设备后可运行：

```bash
devecocli run --module entry --device <设备序列号>
```

启动日志可使用以下命令查看：

```bash
devecocli log --bundle-name com.yaoshining.vidallplayer --from 5m --tail 100
```

## 自动化测试

`entry/src/ohosTest/` 包含 `@vidall/player` 的 Hypium 端侧单元测试，覆盖媒体输入失败时的结构化脱敏错误、会话状态和事件顺序，以及释放后的命令拒绝。测试依赖真实 HarmonyOS 设备或模拟器，执行前先构建并安装测试包，再运行：

```bash
hdc shell aa test -b com.yaoshining.vidallplayer -m entry_test \
  -s unittest OpenHarmonyTestRunner
```

GitHub Actions 的 `验证 ArkTS 测试模块` 任务会在 PR 和 `main` 的相关变更中构建 HAR 与测试模块，以防止测试代码或依赖关系失效。由于 GitHub 托管运行器没有可用的 HarmonyOS 设备，该任务不宣称已执行端侧 Hypium 用例；端侧执行仍需在受控设备运行上述命令。

## 原生构建工作流

工作流 `.github/workflows/build-libmpv.yml` 在 Ubuntu 22.04 上从锁定提交构建 ARM64 OpenHarmony `libmpv.so`，并上传 `libmpv-ohos-arm64-v8a` 工件。固定来源记录在 `native/config/sources.lock.json`。

该工作流是初始引导链：正式发布前必须补齐全部传递依赖锁定、许可证/SBOM、ELF 动态依赖白名单和可复现性审计。

## 文档与规划

- 功能规格：`specs/001-harmonyos-mpv-sdk/spec.md`
- 宪章：`.specify/memory/constitution.md`
