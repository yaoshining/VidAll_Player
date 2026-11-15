# x86_64 SDK r2 接收核验（2026-11-16）

## 已通过的输入检查

- 来源：[上游 Release](https://github.com/yaoshining/ohos_ijkplayer/releases/tag/ffmpeg8-x86_64-sdk-20261115)，附件 `ffmpeg8-ohos-x86_64-20261115-r2.tar.gz`，asset ID `751557299`。
- 压缩包 SHA-256：`3b3e7763e381a569e8362cd4d828e9c3a89605b7505de6f04b14fb46c870e269`。
- manifest SHA-256：`b74fd1c9afc9adbfa766849bc7c494cc4511684d84f79b0649ad2f3b3146634a`；308 个文件记录及包含 manifest 的 309 项 SHA256SUMS 均通过。
- 六库均为 OHOS x86_64 ELF；SONAME 分别为 `.so.62/.62/.11/.60/.6/.9`，DT_NEEDED 仅包内六库和 `libc.so`。完整每库摘要见 `evidence.json`。
- 上游声明仅软件解码，无 OHCodec；HTTPS/TLS/SMB 已编译启用，运行未验证。
- 实际构建机器为上游本地 macOS arm64、DevEco Native API26 / 26.0.0.105；它是 Release 分发的本地 SDK，不称为 CI 编译产物。Player 最终 HAR 仍要求 iMac Actions。

## 未通过：宿主 SMB 初始化合同

SDK 缺少 `include/libavformat/ohcodec_smb_runtime.h`，`libavformat.so.62` 也未动态导出 `ohcodec_smb_runtime_configure_v1`。这不是缺少 OHCodec 硬解接口：名字的历史前缀不改变其 SMB 配置用途。

Player main `native/runtime/process_runtime.cpp` 的 `Configure` 在任何真实 mpv 实例初始化之前，都会调用该接口，设置应用沙箱内的配置文件、状态、缓存及资源目录。当前 SDK 即使启用了 SMB 协议，也不能满足这个配置合同。不能删除调用、伪造成功返回，或退回全局环境变量来宣称兼容。

使用当前 Player 头文件编译 `sdk-host-runtime-probe.c`，链接真实 r2 `libavformat.so.62`，OHOS x86_64 Clang/LLD 实际退出 1：

```text
ld.lld: error: undefined symbol: ohcodec_smb_runtime_configure_v1
```

完整命令和输出见 `sdk-link-probe.json`；只执行了交叉编译与链接，没有运行目标程序或重建 FFmpeg。

## 门禁与复验

新增 `native/scripts/check-ffmpeg-host-runtime.py`，作为 SDK 接收流程的前置命令；它仅核对 SMB 运行时前置条件，不替代 SDK 哈希、完整 ABI、函数签名链接及目标运行验收，也尚未接入完整 HAR CI。

```sh
python3 native/tests/check-ffmpeg-host-runtime.test.py
python3 native/scripts/check-ffmpeg-host-runtime.py \
  --sdk /path/to/sdk --abi x86_64 \
  --nm /path/to/native/llvm/bin/llvm-nm --output /tmp/sdk-host-runtime-gate.json
```

9 项单元测试先因缺实现失败，补最小实现后全部通过。覆盖纯软件正常输入、版本化符号、缺符号、伪相似名称/未定义符号、缺头文件、ARM64 混入、非共享 ELF/截断、缺库及工具失败。模拟工具输出仅用于门禁单元测试，不作为 SDK 接收证据；真实 r2 门禁退出 1，报告见 `sdk-host-runtime-gate.json`，另有上述真实链接负例。

需要上游提供与 ARM64 相同的真实 SMB 沙箱运行时实现、配套头文件和动态导出，不要求补硬解。新 SDK 到位后重跑前置检查及链接，再继续 mpv/libplacebo、NAPI、多 ABI HAR、iMac CI 和 x86 模拟器验收。API19 TV 缺口独立保留。

上游补充要求已写入 [Issue #12 跟进评论](https://github.com/yaoshining/ohos_ijkplayer/issues/12#issuecomment-6898821057)。Todoist 分区 `6j2g9x5HHGRfcVwp` 已同步，T003a `6j2h5Q8mfc68rwvp` 已勾选；T002/T003/T004 未勾选。

额外真实正例：以当前 main 封存的 ARM64 include/六库建立只读目录映射运行同一门禁，退出 0，见 arm64-host-runtime-control.json；证明当前 Player 基线确实已有此导出。该正例不是 x86 验收。
