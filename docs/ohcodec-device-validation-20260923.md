# 新 OHCodec 与诊断配套包真机验收（2026-09-23）

## 结论与范围

本轮用户明确授权真机验证。使用华为智慧屏 MateTV Pro（192.168.3.85:5555），对本轮脚本重建的六个 FFmpeg 库和含诊断修复的 HAR 完成集成、构建、覆盖安装及实际播放验证。

样本：`Game.of.Thrones.S05E01.noHDR.2160p.22CH.26Subs.WEB.mkv`，SMB，H.264 3840×2160、23.976 fps。此次实际选中音轨在诊断面板显示 AC3，不能据文件名或此前记录声称验证了 TrueHD。

该样本硬解、暂停/恢复、快进及缓存字段验收通过。HEVC、HDR、Dolby Vision、其他音轨与长时间播放未覆盖；没有进行主观听音验收。

## 本次部署标识

- HAR：`9d0d556ccef78e62c16ec925891629930cc6121ab239d52eb1b45fb721d4fa38`。
- 已安装 HAP：`bc20bb492d3a378959e783564a96cb72582b50bf6a3d541fa7ca9a4cd4a25895`。
- 七个集成输入的哈希见 `dist/ohcodec-diagnostics-20260923/SHA256SUMS`；安装前已校验 HAP 内六库与候选包逐项一致。
- HAP 内 libmpv、NAPI 和六库哈希见 `dist/ohcodec-device-validation-20260923/deployed-hap-hashes.json`。

保留实际安装 HAP：`dist/ohcodec-device-validation-20260923/validated-entry-signed.hap`。通过 `devecocli build --modules entry` 构建，`devecocli run --module entry --device 192.168.3.85:5555 --skip-build` 覆盖安装成功，未卸载应用、未清理用户数据。

## 实测证据

19:01:52 原生日志确认：

```text
OHCodec is using ConsumerSurface Vulkan raw-YUV zero-copy
Using hardware decoding (ohcodec).
VO: [gpu-next] 3840x2160 ohcodec[nv12]
hwdec-current: ohcodec
```

- 暂停：19:02:00 设置 `pause=yes`，随后详情持续显示位置 0:06、`已暂停=true`。
- 恢复：19:04:52 设置 `pause=no`，界面显示 `已暂停=false`，位置推进到 0:07。
- 快进：点击“快进15秒”后，19:05:06 发起 seek 至 34061 ms 并恢复播放；界面位置为 0:35、暂停为 false。
- 快进后概要仍显示 `ohcodec`、3840×2160、23.976 fps，解码/输出丢帧为 `0 / 0`，画面已由 HBO 开头切换到片头场景。
- 缓存修复：前向缓存约 150.03 MiB、包队列约 162.85 MiB；快进后分别约 127.92 MiB、190.20 MiB。磁盘缓存显示“暂无数据”，未伪造为零。
- 缓冲时长及码率随运行更新；进度显示“约”，确认估算标记呈现。

证据位于 `dist/ohcodec-device-validation-20260923/`：`playback-evidence.log`、`paused-layout.json`、`resumed-layout.json`、`seek-layout.json`、`cache-layout.json`、`after-seek-overview-layout.json`、`cache.png`、`playing-after-seek.png`、构建和安装日志。播放日志仅保留相关事件，避免附带完整播放 URL 等无关内容。

## 保留状态与回退

TV 工作区 `/Users/yaoshining/.codex/worktrees/00e9/VidAll_TV` 保留新 HAR 与六库，未改动其余累积 UI 源码。新包保留在电视上；已通过返回键退出播放，`exit-layout.json` 确认播放根节点消失，设备释放给其他任务。未断开调试连接或清理全局 HDC 状态。

旧七个集成文件及替换前本地构建的 signed HAP 保存在 `dist/ohcodec-device-validation-20260923/backup/`，含 `SHA256SUMS`。旧 HAP 是替换前的本地构建产物，未从设备反向提取。需要回退时先校验该目录摘要，恢复其中 HAR 与六库到 TV 的 `entry/libs/` 并重新构建部署；也可使用对应备份 HAP 回退，但仍须保持宿主与库配套。

未提交、推送、合并或公开发布。
