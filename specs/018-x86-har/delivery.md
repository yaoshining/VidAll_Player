# Spec018 双架构 HAR 交付

## 原始 CI 产物

- [下载 HAR 制品](https://github.com/yaoshining/VidAll_Player/actions/runs/43822153744/artifacts/14205341445)：ZIP 内唯一文件 `vidall_player.har`，解压后直接使用，不重新打包。
- [iMac Actions](https://github.com/yaoshining/VidAll_Player/actions/runs/43822153744) 已通过。源提交 `a66cd41e73842937a929a53fa18918363f6266f7`，分支 `codex/x86_64-har`；尚未合入 main。
- HAR SHA-256：`d8813a573872de3a034b5b94aa54b8b317c0e509f2b6ada4c88684bb2c562dec`，大小 41057326 字节。
- ZIP SHA-256：`cc38325d1088cbba2c5251104043bffc016bce864f387146fc989dde748ff57d`。Actions 当前保留至 2026-11-30，下载需 GitHub 登录。
- 每架构九库的完整哈希、ZIP/HAR 区分及步骤结果见 [ci-delivery.json](ci-delivery.json)。两个桥已与 iMac 本轮实际编译输出比对，16 个固定库与封存输入匹配。

## 构建来源与支持边界

HAR 的 ArkTS、NAPI 与打包由自托管 Intel iMac `yaoshiningdeiMac` 执行，标签 `self-hosted/macOS/X64/deveco`，不是云端 Mac。x86 mpv/libplacebo 及静态依赖由本地 macOS arm64 交叉构建，配方、源码和符号伴随库封存在 `release/inputs/018-x86-core`。FFmpeg 使用用户提供的上游 r3 Release（同样为上游本地构建），Player 未修改或构建 FFmpeg。

- ARM64：保留原固定八库、OHCodec/Vulkan 零拷贝与 Spec017 恢复合同。
- x86_64：当前 Player 桥、真实 mpv/OHAudio 与恢复接口，软件解码和软件呈现；不提供 OHCodec/Vulkan 硬解。不将硬件 HDR/DV 或性能宣称与 ARM64 等同。字幕使用宿主提供字体。
- iMac CI：输入门禁、双架构真实编译/链接/打包、独立消费者、缺公共 API 的编译失败负例、完整 Hypium 编译通过；Hypium 未运行。
- 本地主机：104 项门禁通过；本地消费者通过不充当最终 CI 产物。
- 未完成：x86_64 目标播放运行验收，iMac 当前没有模拟器实例或镜像；API19 TV 真机验收仍独立跟进。不能据此标记正式 TV 播放验收完成。

## TV 接入步骤

1. 下载并核对原始 HAR SHA-256，整体替换原 `@vidall/player` 本地 HAR 依赖；记录源提交。HAR 内版本仍为 `0.1.0`，须按文件哈希辨认本次产物，并重新解析本地依赖，避免复用旧缓存。
2. 保留 `arm64-v8a` 与 `x86_64` 声明。检查实际 HAP 中每个声明架构均为九库；不要混用旧 Player 桥、重复携带旧 FFmpeg 库或手工重打包 HAR。
3. 公共初始化与 `preserve-host` 接口不变，继续现有终局事件、加载身份和故障返回/恢复流程。此次未修改 TV；手动选集暂停标记问题仍属于消费端，不纳入本修复结论。
4. 用消费端正式文件入口分别验证正常音画、暂停恢复、音频打断与手动恢复、跳转/切集、关闭重开和坏片后返回再播。x86 软件路径与 ARM64 硬解路径分别记录；API19 TV 缺口不由其他设备结果替代。

Todoist：T004a CI 交付完成；T004b 模拟器运行待处理，父任务保持未完成。API19 TV 和多次永久挂起资源耗尽问题继续按原独立事项跟进。
