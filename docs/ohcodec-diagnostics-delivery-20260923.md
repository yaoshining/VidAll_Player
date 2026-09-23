# OHCodec 与诊断修复配套交付（2026-09-23）

## 变更

以 `76d3bd5` 的 OHCodec 恢复版本为基础构建。开始本轮工作时，工作区已有六个诊断修复文件，其内容与 `eddc051` 完全一致：缓存状态改为整张 `NODE_MAP` 读取，时长与播放百分比标记为估算。本轮保留这些改动并完成验证，没有再次 cherry-pick。

新增 OHCodec 运行库专项测试，先复现相似符号 `av_ohcodec_release_buffer_invalid` 被误接受，再将导出检查改为完整符号名匹配，兼容 ELF 版本后缀。8 项测试涵盖两种导出位置、版本后缀、相似符号、缺少导出、缺少解码器、缺少桥接、文件缺失及工具失败，已接入 CTest。

## 构建与验证

- `cmake -S native/tests -B /tmp/vidall-player-handoff-tests`、构建及 CTest：14/14 通过。
- `node native/tests/diagnostics-session.test.cjs`：通过。
- `build-libmpv-bootstrap.test.sh`、`build-libmpv-patches.test.sh`、`controlled-release.test.sh`：通过。
- `devecocli build --modules vidall_player --build-mode release`：成功。存在现有版本号 SemVer、CMake 最低版本及 NAPI 声明验证提示，未阻止构建。
- `native/scripts/build-ohcodec-ffmpeg.sh`：从脚本锁定的 FFmpeg 和构建补丁提交实际构建成功，使用现有 SMB/GnuTLS 静态 sysroot；未重新构建该静态依赖。
- 从交付 HAR 提取的 ARM64 `libmpv.so` 与仓库二进制逐字节一致。
- 新 HAR 内 libmpv 与本次重建六库：OHCodec 配套检查、ELF 审计通过；原有不含 OHCodec 的 FFmpeg prefix 被拒绝。

FFmpeg 构建命令（本轮输出目录已存在，不可直接覆盖重跑）：

```sh
OHOS_NDK=/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/native \
FFMPEG_SOURCE_REPO=/Users/yaoshining/.cache/vidall-player/libmpv-ohos-build/libmpv/ffmpeg \
LIBMPV_BUILD_REPO=/Users/yaoshining/.cache/vidall-player/libmpv-ohos-build \
SMB_PREFIX=/Users/yaoshining/.cache/vidall-player/smb-sysroot \
OUTPUT_ROOT=/tmp/vidall-ohcodec-script-validation-20260923 JOBS=8 \
bash native/scripts/build-ohcodec-ffmpeg.sh
```

## 交付目录

`dist/ohcodec-diagnostics-20260923/`（本地构建产物，不纳入 Git）：

- `vidall_player.har`：含诊断修复与 OHCodec libmpv。
- `arm64-v8a/`：宿主 HAP 应配套使用的六个 FFmpeg 动态库，HAR 中不内嵌这些库。
- `SHA256SUMS`、`delivery.json`：交付摘要及来源说明。
- `evidence/`：FFmpeg 构建日志、配置、锁定提交、应用补丁、SMB 静态输入摘要、Player 工作区差异、ELF 审计及旧库拒绝记录。
- `licenses/`：FFmpeg 和所复用 SMB/TLS 依赖的许可证文本。

HAR SHA-256：`9d0d556ccef78e62c16ec925891629930cc6121ab239d52eb1b45fb721d4fa38`。

## 验收边界

本次为供 TV 集成的本地候选包，尚未提交、推送、合并或公开发布；未修改 TV 集成文件，也未操作电视。本次没有新组合的真机证据。重建六库与此前 TV 实测库的摘要不同，不能继承此前 H.264 样本的通过结论。

此前 TV 任务报告同一 4K H.264 样本在暂停、恢复和快进后仍为 `ohcodec`，该证据仅对应此前产物。新包需由 TV 任务重新确认硬解、诊断缓存字段及播放控制；HEVC、HDR、Dolby Vision 和长时间播放仍待验证。

辅助脚本仍输出运行库，并非可直接输入 bootstrap 的完整发布 prefix。交付目录补充了来源、配置、输入摘要及许可证，但不等同于完整公开发行流程或全依赖从源码重建证明。公开发布前仍应执行仓库既有发布门禁。

## 后续真机验收

同日用户授权后，新组合已完成上述 H.264 样本的电视验收，硬解、暂停/恢复、快进及缓存字段通过。此前“尚未真机验证”描述为候选包生成时状态；当前证据和部署哈希见 `docs/ohcodec-device-validation-20260923.md`。HEVC/HDR/DV 与长时边界仍保留。
