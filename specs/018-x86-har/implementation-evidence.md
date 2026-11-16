# Spec018 实现与回归证据

- 输入：r3 SDK 六库、配套头文件、332 项摘要与实际 OHOS x86_64 SMB 链接通过，见 `r3-sdk-evidence.json`。
- 核心：从 Spec017 封存源码逐文件校验，重新构建 x86 mpv/libplacebo、字幕与 Lua 依赖；不复用 ARM64 静态 archive，不编译 FFmpeg。构建配方与来源、符号伴随库见 `release/inputs/018-x86-core`。
- 先红后绿：真实构建先因无条件引用 `ohcodec_buffer.h` 失败；仅 x86 增加 OHCodec 编译边界后，启用未解析符号拒绝的严格链接通过。宿主恢复与真实 OHAudio 保留，门禁拒绝缺恢复接口或错误引入 av_ohcodec 的库。
- 新增自动回归：ELF/接口/依赖闭包 5 项、固定运行库 8 项、DevEco 合同 42 项、HAR 合同 31 项、消费者 10 项、Hypium 3 项、设备包 13 项、CI 摘要 4 项；SMB 前置门禁 9 项。Initialize 提取测试分别编译软件开关 0/1，验证 GPU 环境存在时 x86 仍选软件与 hwdec=no。
- 本地 HAR：两架构各九库；独立消费者 HAP 包含18库且与当前 HAR 逐库一致。见 `local-har-evidence.json`、`local-consumer-evidence.json`。
- 既有 ARM64 设备包：在专用短测工程中通过官方 nativeLib.filter 明确排除 x86 payload，保持原设备审批合同；交付 HAR、正常消费者、Hypium 仍为双架构。实际 HAP 和原合同验证通过，见 `local-arm-device-package.json`。
- 验收限制：以上本地构建不冒充最终 CI。iMac x86_64 的 emulator list 无实例，image list 无已安装镜像；未下载镜像、未执行目标播放。API19 TV 仍独立待验收。

## 宿主回归
全量主机回归结果见 `host-regression.json`。第一次因 Initialize 测试夹具未定义新编译宏失败，修正为双配置真实方法编译后通过；没有删除或跳过原有回归。
