# 任务与证据

- [x] 核对 #83 已验收基线、需求、宪章及一致性。
- [x] R1/R2 在旧实现复现暂停重绘、重新绑定、释放失败并验证修复。
- [x] R3 复现缺少 completed，验证 EOF 身份、乱序、切源、停止和释放。
- [x] R4 核验本轮 iMac Actions 附件、源码、库与 HAR 哈希。
- [x] R5 消费端以本轮 HAR 完成模拟器、云平板与 TV 回归，记录设备、系统版本、音画和最低 API 覆盖。

旧基线红测：GL 暂停 resize 绘制 0 帧，SW 暂停与失败分支不符合预期，Vulkan 分离以及重绑的成功/失败场景未通过。原生 EOF 与 ArkTS 均未发出 completed。旧草案另在停止请求与 JS 回调交错、同一媒体重新绑定两项失败。修复后 Vulkan 17、GL 9、SW 4 个场景，原生事件、ArkTS 会话、CTest 14 项及 Spec Kit 前置检查通过。

补充红绿回归：极短视频在首帧回调前结束，及窗口未就绪导致首次 load 被拒绝后重试。两者都能收到当前媒体的唯一 completed。

## 2026-11-05 交付记录

构建提交 `3eb03a83bbf105073c37c023716df4d52c0f4daf`，实际运行器为 X64 自托管 iMac `yaoshiningdeiMac`。本轮 GitHub Actions 完整构建 debug HAR，下载后逐项复核了 SHA256SUMS、manifest 及全部五个库。[构建日志](https://github.com/yaoshining/VidAll_Player/actions/runs/41879909118) · [CI 附件](https://github.com/yaoshining/VidAll_Player/actions/runs/41879909118/artifacts/13349306018)

HAR SHA-256 为 `2178b223126faafe9012f436861874d543dde11f982cb1abd0edb40a34d15729`，7,407,330 字节，较 #83 增加 5,909 字节。libmpv 和两个 libc++ 与 #83 相同。ARM64 bridge 在已有 libEGL 上新增 eglGetError、eglQuerySurface 两个导入，其他导入和动态库依赖均与基线一致。

| HAR 成员 | SHA-256 |
| --- | --- |
| `libs/arm64-v8a/libc++_shared.so` | `9b67147034bfc1d2b7b51b97b638713f90bd8ca9cf4acbcdac6cbc6d155f6042` |
| `libs/arm64-v8a/libmpv.so` | `3ae9969ac13a58aaa5827520a44e56461f566aff66b9bdd7fe4b78f0da31b076` |
| `libs/arm64-v8a/libvidall_player_native.so` | `3e2c9100bff65bc3fdf96baf16112bf0b36206a3e50a225613667b0a297424d3` |
| `libs/x86_64/libc++_shared.so` | `c65b4e92e52bdbf170d0c11a02c2e3b280fd140c4b8a764e40d8d4875e5ce944` |
| `libs/x86_64/libvidall_player_native.so` | `36e69a7aa86a4e799f1df93fa847e213f75fe041453bba80b8f4ef7660524f3d` |

本地独立示例通过公开 API 整包消费同一 CI HAR，使用 devecocli 编译出未签名 HAP，SHA-256 为 `2846bfe27303be2836a47c38dd8d292ea35c802472f3d50740f7cf70e4b093dd`。HAP 内五个 HAR 库逐字节匹配。
## 2026-11-08 消费端验收

VidAll_TV 已签收本轮 HAR，消费端 OpenSpec 任务 6.2 已完成。开发签名 HAP 为 `8a7fc3a11674372a5c194f250ae261e52a06610620dbdc89052e65fa8edf1d74`，133,233,785 字节。消费端实际引用的 HAR 与上文 iMac CI 产物哈希一致。以下四个环境使用同一份开发签名 HAP。

| 环境 | 已核对的验收结果 |
| --- | --- |
| API 22 平板模拟器 | 正式文件入口自然切集，第二集拖动、返回后重开到 44.120 秒。播放中退出、快速重开及 HTTP 503 均未误触发连播。 |
| API 19 TV 模拟器 | 自然播完进入第二集，取消倒计时则停留第一集。切集后遥控器能操作第二集进度和控制区。 |
| MatePad Air WKI-W10 云平板，API 26 | AList 播放中暂停，连续横竖屏切换及缩放悬浮窗保持完整画面，恢复后时间码继续推进。第二集拖动并返回后，从文件列表直接重开可续播。 |
| EDIS-790A 家庭电视，API 24 | Vulkan 3840×2160 尺寸通知成功。自然播完只触发一次 completed 和一次下一集选核。取消倒计时后停留第一集。第二集暂停在 34.360 秒，重开后推进到 39.560 秒。 |

消费端最终回执为 VidAll_TV 的 `openspec/changes/adapt-harmonyos-tablet/player84-acceptance-2026-11-08.md`（SHA-256 `cc88640388b1c30436782de918dce6bae52fd0f5318165f630645537ba16f436`）。同目录的 `evidence/issue84/final/package.json` 记录签名 HAP 和原生库哈希。

Koofr 首次远距离定位偶发超时在直接打开第二集时也能复现，消费端已列为独立待办。最低实测 API 19 来自 TV 模拟器，API 15 安装下限、API 19 实体平板和独立扬声器听感未作本轮验证。
