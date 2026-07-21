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

## 原生构建工作流

工作流 `.github/workflows/build-libmpv.yml` 在 Ubuntu 22.04 上从锁定提交构建 ARM64 OpenHarmony `libmpv.so`，并上传 `libmpv-ohos-arm64-v8a` 工件。固定来源记录在 `native/config/sources.lock.json`。

该工作流是初始引导链：正式发布前必须补齐全部传递依赖锁定、许可证/SBOM、ELF 动态依赖白名单和可复现性审计。

## 文档与规划

- 功能规格：`specs/001-harmonyos-mpv-sdk/spec.md`
- 宪章：`.specify/memory/constitution.md`
