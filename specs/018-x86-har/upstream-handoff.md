# 给ohos_ijkplayer的x86_64 SDK交付要求

已于2026-11-15按用户授权创建[上游Issue #12](https://github.com/yaoshining/ohos_ijkplayer/issues/12)，由用户安排上游处理。2026-11-16 已取得 r2，仍缺宿主 SMB 配置接口，核验见 sdk-acceptance.md。

VidAll_Player已合并Spec017，当前main为`8a3ce572fb4b534cb4308db4c5f7c356cea5332b`。需要补充x86_64完整HAR；Player分支`codex/x86_64-har`已建立，等待可消费的FFmpeg SDK。请由ohos_ijkplayer工程提供已有产物路径，或按其流程构建交付；Player不在本仓编译/修改FFmpeg。

## 最小输入
1. OHOS x86_64的FFmpeg 8系列六库：libavcodec.so.62、libavformat.so.62、libavfilter.so.11、libavutil.so.60、libswresample.so.6、libswscale.so.9；正确ELF Machine/SONAME，完整DT_NEEDED闭包。不能用Linux宿主x86库替代OHOS库。
2. 与上述二进制匹配的include及可重定位lib/pkgconfig；版本/configure能力、源提交/源码摘要、工具链/构建机器、manifest文件清单与SHA256、许可证/SBOM。
3. 明确x86可用能力：若包含OHCodec，应携带当前关闭恢复修复和相应接口；若只支持软件解码，必须明确声明，Player再实现与验证对应编译分支，不要求伪造不存在的硬件能力。不得用stub模拟成功关闭/恢复。
4. 提供完整SDK下载地址及验证命令。诊断not-release附件、纯源码清单和TV中散落的旧六库不足以作为开发SDK。
5. 补充此前清单未点名的消费端必需接口：配套 `libavformat/ohcodec_smb_runtime.h` 和真实动态导出 `ohcodec_smb_runtime_configure_v1`。即便禁用 OHCodec 硬解，此 SMB 沙箱配置合同仍需保留；不得以空实现替代。按当前 ARM64 合同，复制配置字符串，在创建 SMB context 前设定 config/state/cache/resource 路径；重复、冲突、初始化先后及错误处理须与现有语义一致。

## 2026-11-15 初次核对（历史）
截至2026-11-15，上游默认分支master为`32887363cb103163fe6557ca64c05539ad6d73f2`（PR11合并）。producer-sdk.py对targetAbi硬编码arm64-v8a，Player已锁定的关闭恢复SDK亦为ARM64。Release列表为空，已遍历198个Actions附件，未找到当前完整x86 SDK。README的基础x86构建说明不是现成SDK交付证明。

TV旧六库确为x86 ELF，但当前libavcodec未导出av_ohcodec_release_buffer；未找到这些库配套的受控头文件/PC/源身份包。缺此符号仅说明不能直接走当前OHCodec集成，不表示纯软件方案技术上不可行。

## 2026-11-16 接收结果

r2 SDK 六库/摘要/依赖闭包通过，但第 5 项头文件和符号均缺失。最小 OHOS x86_64 链接已实际复现 undefined symbol，详见 sdk-link-probe.json。软件解码能力声明本身可接受；本轮阻塞与硬解无关。上游修复及重新交付仍由用户安排，Player 不修改或重建 FFmpeg。

## Player接手后
先验证SDK，随后编译当前mpv/libplacebo及x86静态依赖、链接当前NAPI，保留preserve-host与音频合同；iMac Actions构建完整HAR，验证消费工程和x86模拟器后交付源提交/原HAR/九库哈希。API19 TV正式入口仍独立验收。
