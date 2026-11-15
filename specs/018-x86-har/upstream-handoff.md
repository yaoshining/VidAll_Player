# 给ohos_ijkplayer的x86_64 SDK交付要求

VidAll_Player已合并Spec017，当前main为`8a3ce572fb4b534cb4308db4c5f7c356cea5332b`。需要补充x86_64完整HAR；Player分支`codex/x86_64-har`已建立，等待可消费的FFmpeg SDK。请由ohos_ijkplayer工程提供已有产物路径，或按其流程构建交付；Player不在本仓编译/修改FFmpeg。

## 最小输入
1. OHOS x86_64的FFmpeg 8系列六库：libavcodec.so.62、libavformat.so.62、libavfilter.so.11、libavutil.so.60、libswresample.so.6、libswscale.so.9；正确ELF Machine/SONAME，完整DT_NEEDED闭包。不能用Linux宿主x86库替代OHOS库。
2. 与上述二进制匹配的include及可重定位lib/pkgconfig；版本/configure能力、源提交/源码摘要、工具链/构建机器、manifest文件清单与SHA256、许可证/SBOM。
3. 明确x86可用能力：若包含OHCodec，应携带当前关闭恢复修复和相应接口；若只支持软件解码，必须明确声明，Player再实现与验证对应编译分支，不要求伪造不存在的硬件能力。不得用stub模拟成功关闭/恢复。
4. 提供完整SDK下载地址及验证命令。诊断not-release附件、纯源码清单和TV中散落的旧六库不足以作为开发SDK。

## 核对结果
截至2026-11-15，上游默认分支master为`32887363cb103163fe6557ca64c05539ad6d73f2`（PR11合并）。producer-sdk.py对targetAbi硬编码arm64-v8a，Player已锁定的关闭恢复SDK亦为ARM64。Release列表为空，已遍历198个Actions附件，未找到当前完整x86 SDK。README的基础x86构建说明不是现成SDK交付证明。

TV旧六库确为x86 ELF，但当前libavcodec未导出av_ohcodec_release_buffer；未找到这些库配套的受控头文件/PC/源身份包。缺此符号仅说明不能直接走当前OHCodec集成，不表示纯软件方案技术上不可行。

## Player接手后
先验证SDK，随后编译当前mpv/libplacebo及x86静态依赖、链接当前NAPI，保留preserve-host与音频合同；iMac Actions构建完整HAR，验证消费工程和x86模拟器后交付源提交/原HAR/九库哈希。API19 TV正式入口仍独立验收。
