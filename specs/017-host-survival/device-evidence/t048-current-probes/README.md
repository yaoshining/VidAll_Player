# T048 当前音频基线的故障诊断包

## 目的与边界

此前 T045 的关闭/全局故障 HAP 仍使用 T041 mpv，不含 T046 现代音频中断修复。按 S14 从当前 `62e4e3f` 生产输入重新构建两组独立诊断核心，再由 Player 工程构建完整 HAR，供独立消费工程原包接入。本次是本地 MacBook Pro ARM64 诊断准备，不是 iMac CI 正式交付，也没有修改正常 HAR、FFmpeg 或 VidAll_TV。

生产输入清单的 2353 项、全部生产补丁摘要均核验通过。关闭探针仅增加既有 `inject-wait.patch` 和日志库依赖；全局探针仅增加既有 `inject-process-terminal.patch`，单独启用 `handoffTest`。两组均保留生产隔离保护和现代音频修复。输入与完整编译检查见 `input-preparation.json`、`player-preparation.json` 及两组输入检查记录。

## 产物与验证

| 诊断用途 | 应用名称 | 版本 | HAP SHA-256 |
| --- | --- | --- | --- |
| mapper 关闭故障、晚关闭、隔离上限 | Spec017当前-关闭故障 | 1.0.50 | `ac90f2ce375c15661e0c3fbeb7571058f129f5236b9a9f708a5c966e55e1be99` |
| hardware-first 全局终局后兼容续播 | Spec017当前-全局恢复 | 1.0.51 | `09a5c2d0149bfb5053053b7937251b86be84eae6804ad1dd99f35fc178c87b9d` |

完整路径、HAR/九库/页面/素材摘要见 `tablet-preparation.json`。两份 HAP 均为 tv/tablet、仅 ARM64、九库无损压缩；安装包及实际依赖展开目录中的九库均与各自原 HAR 一致。FFmpeg 六库与 C++ 运行库逐字节等同已核验的 `62e4e3f` iMac 原始 HAR。桥由当前 Player 源码完整编译，记录三个翻译单元的摘要；不借用旧桥。

两组核心的 64 项 mpv 公共导出与生产一致；现代 Interrupt 注册符号存在于动态解析字符串中，不成为 ELF 强导入。关闭探针包含三个 FENCE_PROBE 日志且无 global 定时入口；全局包有定时入口且无 FENCE_PROBE。后者只验证真实终局管理器合同，不证明 GPU 自身发生了故障。

故障内录页新增与 T047 普通页相同的有界阶段显示。先以实际生成的 `record` 方法建立红测，再实现：正常录制事件可见、非录制事件不污染显示、超过 12 行删除旧行、每行限 160 字符并消除换行。生成接缝漂移和重复注入仍拒绝。相关测试通过，两份完整 ArkTS/HAP 编译通过。原硬件资格、Surface、手动返回/继续、原生日志确认、15 秒期限及真实 STARTED 门槛均保留。

## 尚未完成

两份新故障包尚未上传或设备执行，音轨未取得，不能计听声/旧音隔离通过。1.0.49 普通/焦点阶段诊断包也仍待手动上传；本轮刷新云调试“我的信息”只见 1.0.48，免费余额 345 分钟，无已分配设备。本轮没有消耗设备额度或购买。

先用 1.0.49 定位录音启动超时，取得录音后再执行这两组当前故障包；按各探针 README 同轮记录 PID、实际 OHCodec/Vulkan、故障身份、返回列表及新视频画面和音轨。API24 平板结果不替代 API19 TV 正式文件入口验收。不创建提前验收的 PR。

后续更新：`ea6b236` 的 iMac [43349876875](https://github.com/yaoshining/VidAll_Player/actions/runs/43349876875) 与 Ubuntu [43349962085](https://github.com/yaoshining/VidAll_Player/actions/runs/43349962085) 均通过，见 ci-status.json。用户已上传 1.0.49，Mini 实测确认卡在 start-returned 后等待 STARTED；本次仍无音轨，详见 T047 更新。本目录两份故障包尚未上传或执行。
