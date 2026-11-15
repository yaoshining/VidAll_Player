# Spec018 实施计划

## 阶段
1. 核对main、当前x86桥路径、上游SDK、旧库ELF与接口，保存只读证据。
2. 由ohos_ijkplayer交付或指出已有x86_64 SDK；Player核验六库/头文件/PC/来源/许可证/能力。已取得 r2；哈希/架构通过，SMB 运行时接口门禁和实际链接失败，见 sdk-acceptance.md。由上游补接口后重新核验；不改 FFmpeg，不跳过 Player 初始化。
3. 按TDD先补多ABI输入与HAR检查的失败用例，再扩展mpv/libplacebo及其静态依赖构建、当前NAPI链接和C++运行库选择；不得复用ARM64静态archive。确认软解/硬解与恢复接口的编译边界后再实现。
4. 在独立本地目录构建预验证，推动iMac分支CI产出完整HAR；验证独立消费工程和x86_64模拟器，下载原包核对全部库，最后给下载地址。

## TDD计划
先红：缺六库之一、误用ARM64 ELF、头文件/库版本错配、旧probe桥、错误恢复ABI、未知DT_NEEDED、错误C++运行库、包缺ABI、负例失效。再实现最小多ABI支持并绿测；最后验证正常完整输入和实际消费者。2026-11-16 已完成宿主 SMB 前置门禁的 9 项红绿测试和真实 SDK 链接负例；尚未修改生产播放代码，未重复运行 ARM64 全套，也未宣称完成 x86 播放测试。R7 对应 T002 及 T003a。

## 宪章/职责
不新增HarmonyOS API或改变用户交互；不降低API19要求或音频安全合同。无FFmpeg/TV修改、无新云端环境权限。iMac最终HAR与本地核心编译分别披露。输入缺失时不把单纯扩充abiFilters当成完成。

负责会话：[修复 issue #89](thread://01a1bccc-e2cc-7a13-8cd6-31aae7079fb0?hostId=local)；thread ID `01a1bccc-e2cc-7a13-8cd6-31aae7079fb0`；host `local`；更新2026-11-16。
