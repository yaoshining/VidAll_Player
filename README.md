# VidAll_Player

HarmonyOS TV `libmpv` 播放 SDK 的受控构建项目与最小应用示例。

示例应用同时支持 TV 遥控器焦点操作和手机触屏操作，提供 WebDAV 目录浏览、本地文件选择、Surface 重建与前后台恢复、缓冲/错误展示及播放器释放后重建验证。

## 当前状态

- 初始 HarmonyOS 应用可构建并在启动时输出 `VidAll_Player` 生命周期日志。
- 支持手机和 TV 安装声明；`compatibleSdkVersion` 为 HarmonyOS 5.0.3 / API 15，`targetSdkVersion` 为 API 22。
- GitHub Actions 从固定提交的 OpenHarmony `libmpv` 源码构建流程生成 ARM64 `libmpv.so` 与 SHA-256 文件；构建下载和中间目录会按系统、ABI、SDK、Meson 版本及锁定输入缓存，不缓存最终发布制品。
- US4 流媒体与 SMB 代理已实现：HLS/DASH/HTTP(S) 直链与 SMB localhost HTTP 代理的加载路径、租约清理、缓冲事件与网络失败分类；真机播放结论见下方支持矩阵。

## 支持矩阵

能力结论使用三态：**已通过真机样本** / **已构建待验证** / **不支持或暂缓**（FR-037）。
构建成功不等于已支持；缺少 ARM64 真机证据的能力不得标记为已通过。

| 能力 | 结论 | 说明 |
|---|---|---|
| 本地文件播放 | 已构建待验证 | US1/US2 已实现，待 ARM64 真机样本 |
| HTTP/HTTPS 直链 | 已构建待验证 | 认证头逐次设置、重定向凭据过滤；seek/断网恢复待真机 |
| HLS（master/media、fMP4/TS） | 已构建待验证 | `hls-bitrate=highest` 选择最高码率变体；运行期自适应切换依赖 FFmpeg 构建，待真机 |
| DASH（MPD） | 已构建待验证 | `ff_dash_demuxer` 符号已构建期验证（#21）；自适应交给 FFmpeg DASH demuxer 默认策略，待真机 |
| SMB localhost HTTP 代理 | 已构建待验证 | `localhostProxy` 仅限环回明文 HTTP；租约关联/清理已覆盖；策略与验收用例见 `docs/smb-localhost-http-proxy.md` |
| 外挂字幕（HTTP/HTTPS/本地缓存 file://） | 已构建待验证 | `sub-add` 远程 URL；本地缓存 file URI 校验已覆盖 |
| 外挂音频（HTTP/HTTPS） | 已构建待验证 | `audio-add` 远程 URL，加载后自动选中 |
| 缓冲状态事件（paused-for-cache） | 已构建待验证 | `getBufferingState` + `buffering` 事件；SDK 事件顺序已覆盖 |
| 网络中断恢复 | 已构建待验证 | 失败分类（可重试/不可恢复）+ 重新 `load()` 恢复；清理事件顺序已覆盖 |
| RTSP / UDP / SRT / RTMP | 不支持或暂缓（可选未验证） | 输入校验以 `PROTOCOL_NOT_VERIFIED` 拒绝；完成单独真机验证前不宣称支持 |

完整的性能、容器/视频、音频、字幕、网络、HDR/色彩和 IJK 兼容性矩阵位于 `release/capabilities/arm64-tv-capability-evidence.json`。该文件是发布门禁输入：只有标为"已通过真机样本"的条目才会携带匿名 ARM64 TV、样本、执行时间、指标和证据文件；其余条目不得将构建结果表述为支持。

当前候选版本没有 ARM64 TV 真机性能数据，因此首帧、跳转、缓冲恢复、CPU/PSS 和 4K 一小时长播均为"已构建待验证"，并以同样本 IJK 对比作为采集阈值；高码率、HDR 和高级音频能力不作未证实承诺。

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

## 候选 SDK 契约

`@vidall/player` 当前冻结为 `0.1.0` 候选；`packages/vidall-player/Index.ets` 是唯一公开入口。候选阶段禁止消费者导入 NAPI、NativeWindow、EGL/GLES、libmpv 或 `src/internal`。

以下命令验证公开 API、原生生命周期测试目标、API 15/19/22 审查基线和“无 HAR 内部 native 装入证据即阻断真实 bridge”的记录：

```bash
bash native/tests/contract-baseline.test.sh
```

受控网络夹具位于 `scripts/test/network-fixtures/`，只监听 loopback 且不含真实凭据；WebDAV/认证/chunked 场景必须由运行时受控环境注入。

## 自动化测试

`entry/src/ohosTest/` 包含 `@vidall/player` 的 Hypium 端侧单元测试，覆盖媒体输入失败时的结构化脱敏错误、会话状态和事件顺序，以及释放后的命令拒绝。测试依赖真实 HarmonyOS 设备或模拟器，执行前先构建并安装测试包，再运行：

```bash
hdc shell aa test -b com.yaoshining.vidallplayer -m entry_test \
  -s unittest OpenHarmonyTestRunner
```

GitHub Actions 的 `验证 ArkTS 测试模块` 任务会在 PR 和 `main` 的相关变更中构建 HAR 与测试模块，以防止测试代码或依赖关系失效。由于 GitHub 托管运行器没有可用的 HarmonyOS 设备，该任务不宣称已执行端侧 Hypium 用例；端侧执行仍需在受控设备运行上述命令。

## 原生构建工作流

工作流 `.github/workflows/build-libmpv.yml` 在 Ubuntu 与 macOS 清洁环境验证受控构建工具，并上传来源锁、feature manifest、SPDX/CycloneDX SBOM、`NOTICE` 与许可证审计报告。完整不可变来源锁记录在 `native/config/sources.lock.json`；实际发布制品还会附带 SHA-256、ELF 审计与可重复构建报告。

`native/scripts/build-libmpv-controlled.sh` 只接受已在受控 SDK 环境检出的锁定来源和本地生成的 `libmpv.so`，绝不下载或执行外部 `bundle.sh`。目前 OpenHarmony 交叉编译适配层仍待纳入本仓库；因此该脚本会明确拒绝未提供的编译输入，而不会伪造构建成功。发布流程、许可证限制和可重复性验证见 `docs/controlled-libmpv-release.md`。

## 文档与规划

- 功能规格：`specs/001-harmonyos-mpv-sdk/spec.md`
- SMB localhost HTTP 代理策略与验收用例：`docs/smb-localhost-http-proxy.md`
- 宪章：`.specify/memory/constitution.md`
