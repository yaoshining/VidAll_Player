# #83 iMac CI 临时验证记录（非最终云端交付）

本次 run 实际使用 iMac self-hosted，用户指出来源不符后已降为临时验证。云端最终产物必须等待 T014/T015，不以本记录完成最终验收。

## CI 身份（历史已完成）

- GitHub Actions：[41640263079，attempt 1](https://github.com/yaoshining/VidAll_Player/actions/runs/41640263079)，2026-11-03，成功。
- 构建提交：`2808387bca4f6f7bf2b2d2057e547f6708dd9035`，分支 `codex/legacy-vulkan-size-83`。
- 产物附件：`legacy83-ci-har-2808387bca4f6f7bf2b2d2057e547f6708dd9035-1`，artifact ID `13233185847`。
- 附件 ZIP digest：`sha256:d9fd75e212f87496486cb8592d2b7be08a6a69ec00356225a807e8b2f8d5b275`，区别于包内 HAR 哈希。
- 文件：`vidall_player-issue83-ci.har`，7,401,421 字节。
- HAR SHA-256：`8350234e956dd02c0d4265a79c91f1ef832755a2c7349ad2eb3fbb3f250add8e`。
- 实际 CI 工具链：Studio 26.0.0.851、Native SDK 26.0.0.105、CLI 1.3.4。目标 API 22、最低 API 15 保持不变。
- 主机测试、完整 Player HAR 构建、事件提交身份、库哈希/ABI 审计及上传全部通过。未安装设备、未修改或构建 FFmpeg、未触发其他项目。

## 库身份（下载后复核）

| 成员 | SHA-256 |
| --- | --- |
| ARM64 libmpv | `3ae9969ac13a58aaa5827520a44e56461f566aff66b9bdd7fe4b78f0da31b076` |
| ARM64 libc++ | `9b67147034bfc1d2b7b51b97b638713f90bd8ca9cf4acbcdac6cbc6d155f6042` |
| ARM64 bridge | `1d32d08a5f4ebce5832d9ad59792b676f1fda1c2bf33d13e1a57644a3fc1fed4` |
| x86_64 libc++ | `c65b4e92e52bdbf170d0c11a02c2e3b280fd140c4b8a764e40d8d4875e5ce944` |
| x86_64 bridge | `a16489a43e9ea0123b23e4eda357e970316ce3ffb16b7827edf90552d27d10f6` |

核心和运行库逐字节保持旧 HAR；两个 bridge 的动态库依赖与导入符号集合与原包相同。HAR 从 Actions 附件直接下载，未替换任何成员。

## 消费端（待完成）

已通知“实施 VidAll_TV 平板适配”会话使用 `8350234e…` CI 包，取代 `36592128…` 本地预验证包。等待按模拟器→云平板/TV 顺序反馈当前包的尺寸变化、退出/重进结果。x86_64 仍仅探针。

T009/T010 是历史临时 CI 记录；云端 T014/T015 和设备 T011/T012 保持未完成。CI 成功不等于 #83 设备验收或发布完成；#84 尚不能继续实施。

本记录是构建后的证据补记；后续仅修改本记录和任务状态不会改变上述 CI 构建提交或产物身份。
