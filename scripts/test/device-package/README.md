# 独立设备短测包

此目录在已锁 DevEco26 工具链中生成专用 **unsigned** HAP，消费同一已审源码构建的 HAR。它不签名、不安装、不上传、不连接设备。现有 Player/TV 产品、八个核心库和产品 API 配置不改动。

专用 bundle 为 `com.yaoshining.vidalldeviceprobe`，module `entry`，ability `EntryAbility`，API min 15 / target 22。fixture 白名单没有网络权限、备份 extension、NAS 分支、私有凭据或旧会话读取。生成器 `generate_media.py` 只接固定 lavfi 合成信号；30 秒 H264/AAC MP4 已生成并以 `fixtures/device-smoke/media-lock.json` 锁定，云端不需要另装 FFmpeg。媒体哈希不是厂商签名或私人媒体许可的替代。

## 验证

```sh
node scripts/test/device-package/session.test.cjs
node scripts/test/device-package/journal.test.cjs
node scripts/test/device-package/platform.test.cjs
python3 -B scripts/test/device-package/package.test.py
```

前三项转译并执行真实 ArkTS 逻辑类，平台观察由受控替身提供。`session.test.cjs --trace-json` 导出真实 `SmokeSession.run()` 产生的正常事件；执行器应直接消费此 trace 做跨模块契约测试，而不是另手写一套成功记录。所有宿主测试都不代表真机验收。

实际构建命令（显式锁定路径来自同次 SDK 准备）：

```sh
python3 -B scripts/test/device-package/package.py \
  --out <与target一致的out> --studio <锁定Studio> \
  --wrapper <锁定CLI> --common <锁定CLI-common>
```

要求 `out/work/context.json`、`evaluation-result.json` 与实际 checkout/tree/tracked bytes 一致，HAR 必须是当次 target 输出；真实 devecocli clean/build 后核实际 HAP、九库、API、包内媒体、ABC、依赖解析和 staging 源码。独立 Hvigor home 的 daemon 按 registry/cwd 身份停止。`--local` 只输出 `local-manifest.json`，显式 `localOnly=true`、`externalApprovalAllowed=false`，不能伪装成 GitHub run 或拿去批准安装。

云端模式生成独立 `device-package/unsigned-artifact/`，仅有 `manifest.json` 与 `device-unsigned.hap`；与原 `public/` 文本证据目录分离。工具**没有上传能力**。未来工作流新增上传前仍须精确审批，上传后 artifact ID/ZIP digest 放外部 envelope，不能回写包内制造自引用。

## 会话及事件

启动参数只接受 `sessionNonce`（32位小写hex）、`mode=normal-local-smoke`、`expectedUnsignedHapSHA256`（64位hex）。应用原子创建 `filesDir/device-smoke/<nonce>/`，同 nonce 已存在立即拒绝；`onNewWant` 拒绝复用进程会话。新的 `events.jsonl` 每行统一字段：

```text
schemaVersion, unsignedHapSHA256, nonce, bundle, pid,
startedAtMs, elapsedMs, seq, event, cycle, value
```

`unsignedHapSHA256` 是外部启动身份的回显，**不是运行库 hash 或 HAP 自证**。真实二进制身份由构建载荷、云端 artifact/外部审批、签名前后全载荷、官方验签及安装记录绑定；本应用不新增原生库扫描 API。事件时间是毫秒，`value` 一律字符串；复合值为 JSON 字符串。

| event | value / 语义 |
|---|---|
| session-start | `{mode,expectedUnsignedHapSHA256,identityEvidence:'launch-statement-only'}` |
| keep-screen | `true` / `false`，来自窗口实际回读 |
| runtime-ready | `ready`，公共初始化及状态核验后 |
| render-observed | `{generation,sequence}`，原始公开 firstFrame 事件 |
| frame | `{count,positionMs,evidence:'public-firstFrame-render-event'}`，当前 cycle 已观察到新首帧 |
| progress / resumed | `{beforeMs,afterMs,intervalMs}`，间隔700ms，实际推进至少500ms |
| paused | `{beforeMs,afterMs,intervalMs:1000,paused:true}`，两次暂停观察位置差不超过180ms |
| seek-request | `{targetMs:10000}` |
| seek-complete | `{targetMs,reachedMs,afterMs}`，命中容差1000ms且继续推进至少500ms |
| closed | `released`，cycle1 release实际完成 |
| reopened | `new-first-frame`，cycle2新的frame之后 |
| eof | `{positionMs,durationMs,completed:true}`，cycle2正常完成且最后实际位置>=28000ms |
| release-complete | `released`，release实际完成 |
| session-end | 仅成功且cleanup完成时 `passed` |
| session-failed / player-error | 明确失败，不落入成功end |

首帧按每个 player 创建时绑定的 cycle 与 `surfaceGeneration` 过滤，旧播放器迟到事件不能成为重开证据。正常整轮上限120秒，release/保屏关闭各有3秒有界尝试；finally 中两项独立，日志写入失败也不能跳过保屏关闭。外部执行器仍须更长事务 watchdog、异常进程清理和持久待清理 journal；应用卡死/异常退出不能自称保屏回读成功。

正常路径约30余秒；不执行长播、SMB、HDR、Hypium真机套件或主观声画验收。所有未实际运行项目保持待验收。
