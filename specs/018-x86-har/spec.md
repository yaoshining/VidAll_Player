# Spec018：x86_64完整播放HAR

状态：r3 SDK 输入验收通过，x86_64 核心和本地双架构 HAR 已构建；iMac CI HAR 已交付，目标播放运行尚未验收。基线main `8a3ce572fb4b534cb4308db4c5f7c356cea5332b`，工作分支`codex/x86_64-har`。

## 用户目标
在main基础上补充x86_64可用的完整Player HAR，提供CI原包地址并同步Todoist。当前ARM64产物不变；不使用旧桥或只有NAPI探针的产物冒充完整播放。

## 需求与验收
- R1：x86_64桥必须由当前Player源码编译并链接可运行的mpv及匹配FFmpeg依赖；只有ELF架构正确或HAR编译通过不算播放支持。
- R2：SDK来源必须固定提交/哈希，包含六库、匹配头文件/pkg-config、配置/能力、许可证及依赖闭包。FFmpeg构建归ohos_ijkplayer，Player只读消费，不替其构建或发布。
- R3：保留Spec017 preserve-host、音频打断/手动恢复、尺寸、旋转和播完合同。x86_64硬解能力按SDK与目标实际能力声明；软件路径不假装OHCodec硬解，不能用无行为stub伪造恢复接口。
- R4：缺库、错架构、SONAME/依赖冲突、旧桥/探针、配置未知或哈希不匹配必须在交付前拒绝。保持ARM64完整九库；最终双架构内容和每库哈希显式记录。
- R5：普通分支由iMac自托管Actions交付原始HAR；记录实际runner、源提交、HAR与每库哈希及消费方式，不重打包Player。
- R6：分层记录主机、消费构建、x86_64模拟器的正常播放/暂停恢复/seek/关闭重开/坏片续播。模拟器不替代API19 TV硬解验收，#93不并入本次完成结论。
- R7：软件解码可以不提供 OHCodec，但不能删除现有 SMB 沙箱初始化合同。SDK 须提供匹配的 `libavformat/ohcodec_smb_runtime.h` 和真实动态导出 `ohcodec_smb_runtime_configure_v1`；不以空实现、跳过检查或全局环境变量覆盖冒充兼容。

## 历史 r2 阻塞（r3 已解除）
2026-11-16 已下载上游 Release 的 `ffmpeg8-ohos-x86_64-20261115-r2.tar.gz`，核验 309 项摘要与六库 x86_64 架构、SONAME 和依赖闭包。SDK 为本地 macOS arm64 构建的软件解码版本，不提供 OHCodec，这一能力边界可接受；它尚缺 R7 的配套头文件与动态导出。当前 `process_runtime.cpp` 在所有真实 mpv 架构初始化时均调用该接口，最小 OHOS x86_64 链接实际失败，不能宣称可接入。详情见 `sdk-acceptance.md`、`sdk-host-runtime-gate.json`、`sdk-link-probe.json`。SDK 目标运行未验收。

负责会话：[修复 issue #89](thread://01a1bccc-e2cc-7a13-8cd6-31aae7079fb0?hostId=local)；thread ID `01a1bccc-e2cc-7a13-8cd6-31aae7079fb0`；host `local`；更新2026-11-16。

## r3 接续（2026-11-16）
r3 已补齐 R7；332 项摘要和真实 x86_64 链接通过，证据 r3-sdk-evidence.json。后续仅 x86_64 禁用 OHCodec 与 Vulkan，使用软件解码和现有 render API 路径；保留真实 OHOS 音频、host recovery 和 terminal API。ARM64 输入/行为不变。x86 字幕使用宿主提供字体，编译库与能力单独记录，不宣称与 ARM64 硬件/HDR 路径等价。

## 当前验收边界
本地和 iMac CI 双架构 HAR、独立消费者构建成功，交付见 delivery.md。iMac 未安装模拟器实例或镜像，x86_64 运行验收尚未完成；不以构建通过标记 R1/R6 的播放验收完成。API19 TV 缺口仍单独跟踪。
