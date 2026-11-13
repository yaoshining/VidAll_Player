# Spec017 当前候选与未完成交付

2026-11-14：四项待办已完成 **2/4**。API24 Mini已通过真实系统打断/手动恢复，以及关闭和全局故障后同进程续播的音画验收。永久平台音频挂起尚未解决，API19 TV正式文件入口未验收；**未提Spec017 PR、未合并、不是最终可接入交付**。

## 原始CI产物与来源

- 生产候选：`c7d56ee765f3ffde6059979e80c8f0162089ce01`。
- [GitHub Actions构建及原始HAR附件](https://github.com/yaoshining/VidAll_Player/actions/runs/43464070369)：iMac自托管macOS/X64，不是云端Mac。
- 原始HAR SHA256：`6fda6fb1ffa0cb6d78865399e811af1a9d74ae129b518280628afa59e90f9edf`。未由消费端重打包。
- [九库哈希与CI身份](device-evidence/t051-ci-preparation.json)。`libmpv.so` SHA256：`23fd405c02f8c959bf7811c0cd1f2e40b6fd6f96384fbe8cfda6357dd5b1fb6a`。mpv受控核心由本地MacBook Pro交叉构建，最终正常HAR由iMac CI构建；FFmpeg沿用上游预编译SDK，本轮未修改或构建。
- 仅支持完整 `arm64-v8a` 九库播放。x86_64旧探针不是播放支持；TV不能静默删架构或混旧桥，需另行补齐匹配SDK/核心或显式确认产品支持边界。当前未提供完整x86_64 HAR。
- 设备独立HAP由本地MacBook Pro构建。普通/焦点HAP消费以上原始CI HAR；两组故障HAP消费T053独立完整诊断HAR，不能作为正式产物。T054/T055只修改验收程序，九库分别与来源逐个一致。

## 当前验证结果

| 层次 | 结果 | 边界 |
| --- | --- | --- |
| c7d56ee宿主与CI | 94项宿主、7组音频生产函数及iMac CI通过 | 不能代替设备输出 |
| T054/T055工具 | 10套工具回归、硬件资格/页面集成回归、ArkTS构建与九库核验通过 | 测试用本地HAP，未重建生产核心 |
| API24 Mini普通/焦点 | 1.0.60 PID45494、1.0.64 PID25123前后不变；实际Alarm导致暂停，解除后保持暂停，人工一次恢复；坏片返回、普通暂停/恢复、seek、OHCodec/Vulkan、释放重开通过 | 实际内录已完整导出，9个窗口全部通过；系统服务SendInterruptEvent日志未取回；不宣称人工听感/扬声器音质 |
| API24 Mini关闭故障 | 1.0.61 PID59902前后不变；真实OHCodec/Vulkan mapper关闭接缝注入、手动返回新片、晚关闭完成日志、隔离上限后软件解码通过；8个音轨窗口通过 | 注入返回错误，不声称复现自然驱动故障；不是永久Stop/Release挂起 |
| API24 Mini全局故障 | 1.0.65 PID33028前后不变；初始OHCodec/Vulkan，计时终局后手动返回/新片及第三次兼容重开，5个音轨窗口通过 | 全局锁保持terminal；是计时探针，不是GPU破坏；仅本次运行兼容 |
| API19 TV模拟器历史 | 62e4e3f CI原包坏片/播放/暂停/重开通过 | 旧核心、software/no，不能作当前硬解或真实声音证据 |
| API26历史崩溃 | c7d56ee尚未在该故障设备独立复验 | 不以API24通过关闭T049/T050 |
| API19 TV正式入口 | 未完成 | 后续由TV接入正式CI HAR执行 |

证据：[焦点](device-evidence/t054-normal64/README.md)、[关闭故障](device-evidence/t054-fence/README.md)、[全局手动恢复](device-evidence/t055-global/README.md)、[实际录音持久文件清单](device-evidence/t054-t055-artifacts.json)。信号分析器的deviceAccepted保持false；设备结论依据包身份、PID、实际路径、事件及音画综合判断，不能用单个分析器结果替代。

## 阻塞及不变的要求

平台renderer Stop/Release永久不返回时，无法证明其已提交音频缓冲已停止；撤销回调、填零、固定等待或并发静音都不是停止确认。保留未知资源会占用16槽和有界执行器，重复永久故障不能无限恢复。见[第3项具体限制](device-evidence/t050-permanent-audio-limit.md)。需要平台有界断开协议，或经API19TV证实支持的独立可重建播放进程；现有公开子进程接口有设备类型限制。未获得依据前，不强行释放、不清零预算、不放宽不退出主应用要求。

Renderer已成功Release后Builder清理挂起属于已有T035可恢复边界；Stop返回错误但实际状态明确STOPPED属于已有T041边界。两者都不能推广到平台调用永不返回。

## TV 迁移步骤

1. 核对原始 HAR 与九库哈希，整体替换旧 Player 产物及重复依赖；不在 TV 中修改或重打包 HAR。先解决 x86_64 支持边界。
2. 创建任何 Player 前调用 `initializePlayerRuntime(context, { terminalPolicy: 'preserve-host', deadlineMs: 3000 })`；不要在终局通知中结束应用。
3. 新视频默认 standard；每次 `load` 的身份回执绑定稳定媒体 ID，只有 `onPlayerFault` 的 known 归属才能标记该视频。TV 持久化和重启策略由 [#372](https://github.com/yaoshining/vidall-tv/issues/372) 跟进，#371 手动选集暂停单独处理。
4. 全局终局后停止使用旧实例，保留旧 Surface，等待 recovery.ready 后创建 compatible 实例并使用新 Surface。只有实际首帧与音频确认后才提示兼容切换成功。普通坏片与可隔离会话故障沿用原恢复路径。
5. 按 [接入文档](../../docs/normal-core-integration.md) 处理容量错误和迟到回调；`PLAYER_EVENT_QUEUE_FULL` 是桥会话故障，释放后新建，不作为视频硬解失败标记。自动连播不能解除用户暂停或未结束的音频打断。
6. 从 API 19 TV 正式文件入口继续验证正常播放、音频打断/手动恢复、切集、退出重开、故障后返回、再播其他视频及连续故障上限，分别保存包哈希、PID、音画与原生日志。
