# mpv 正常核心构建工具

从 ohos_ijkplayer 的 Phase30 封存构建工具导入 **mpv/libplacebo** 编译和静态校验部分；原始及导入摘要见 `origins.json`。未导入或执行 FFmpeg 编译脚本。`validate_one.py` 对原有四个 terminal 导出之外增加六个恢复接口，仍拒绝内部 `mp_host_*` 和 `mp_ohcodec_terminal_*` 导出。其他第三方封存代码保持原文。

先取得来源锁对应的基线 manifest、依赖目录、mpv 源树和已交付 FFmpeg SDK（不是源码）：

```sh
python3 -B native/scripts/prepare-host-recovery-input.py \
  --baseline <Phase30-A-package.json> --dependencies <封存依赖目录> \
  --mpv <封存mpv源树> --sdk <恢复SDK目录> --output <全新输入目录>
python3 -B native/tooling/normal-core/fresh_build.py \
  --input-root <全新输入目录> --run-root <全新构建目录> \
  --sdk <OHOS-native-SDK> --meson <meson路径> --ninja <ninja路径> \
  --pkg-config <pkg-config路径> --jobs 8 --stable-prefix /usr/local --handoff-trace
```

工具验证全部输入摘要，将 pkg-config 前缀迁移到独立构建副本；只构建 libplacebo 和 mpv。原 SDK 六库保持字节不变。产物不能手工改 ELF/RPATH 伪装可复现；`run-summary.json`、`input-final-check.json`、`validation/static-validation.json` 和实际链接/编译命令共同记录结果。源树检查、OHCodec 注册及 Vulkan 调用静态证据不等于目标运行。

宿主范围测试：

```sh
python3 -B native/tests/host-survival/prepare-input.test.py
python3 -B native/tests/audio-interrupt/interrupt.test.py <派生mpv源码>
python3 -B native/tests/host-survival/audio-data.test.py <派生mpv源码>
python3 -B native/tests/host-survival/audio-control.test.py <派生mpv源码>
python3 -B native/tests/host-survival/audio-lifecycle.test.py <派生mpv源码>
python3 -B native/tests/host-survival/fault-context.test.py <派生mpv源码>
```

新二进制必须同步输入 manifest、库绑定、实际编译记录、源码锁和审计器固定摘要，通过篡改负例后才可参与 HAR 打包。本地核心交叉编译与最终 iMac CI HAR 是两层证据，交付时分别披露。仅支持完整 ARM64 播放，不把 x86_64 probe 当成核心。
