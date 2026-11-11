# 正常核心输入（独立接入）

当前输入在 Phase30 A TRACE-only 基线上应用 #89、会话隔离及 Spec 017 宿主恢复 mpv 补丁。六个 FFmpeg 运行库现消费 ohos_ijkplayer PR #11 的恢复 SDK，C++ 运行库保持原身份；MPV 公开头来自精确匹配二进制的 `mpv-trace-c` 安装输出，SMB 公共头来自其配套 FFmpeg staging。`manifest.json` 是本目录唯一绑定入口，运行 `python3 -B scripts/audit/normal-core-verify.py` 校验。

`provenance/source-lock.json` 绑定精确生产者源码/补丁索引、静态 libplacebo、工具链及历史来源限制。`provenance/sbom.json` 列出运行库和静态链接输入，许可证正文与生产者完整索引位于 `licenses/`。此处的来源索引不宣称已复制全部源码构建闭包；离线接收者要重建时还需按精确引用取得生产者封存输入。索引校验与法律合规发布审核是不同验收层级。

静态 libplacebo 已链接进 mpv，不再重复打包 .a；头文件保持原始上游内容。Python 目标路径修复由生产者输入锁继承，未修改或回滚。

本目录是新独立组合，旧候选/TV 不替换，`formalArtifactAllowed=false`。HAR 打包完整动态库后，未来 TV 接入必须同时移除旧六库，禁止新旧混装。低 API 真机、物理 HDR 等未验证项不因输入审计通过而转为完成。

## 输入门禁与 TDD

`python3 -B native/tests/normal-core-input.test.py` 执行实际输入正例与篡改负例；`python3 -B scripts/audit/normal-core-verify.py --verify-external` 另核验本机生产者精确来源引用和本次重建的静态 libplacebo。重建目录迁移时设置 VIDALL_MPV_BUILD_ROOT。前者不要求将生产者源码复制到消费仓库，后者要求原封存可读。首次 RED 是输入未接入的实际清单缺失；实现后完整门禁通过。详细阶段和保留失败界限见 `INPUT-VERIFICATION.json`。

可信 producer binding、实际编译证据和 source-lock 的 SHA 固定在校验器中；修改清单自报不能绕过。ABI 接受 ELF 符号版本后缀，必须包含固定最小 terminal/SMB 导出集合，空列表不通过。资源 `smb.conf` 属于输入内容校验，运行时目录与权限由 Player 初始化另行负责。

## Samba 资源边界

当前字符表由精确 Samba 源码内嵌：`codepoints.c` 的 `lowcase_table` / `upcase_table` 各 65,536 个 uint16，完整 131,072 字节都能在当前 avformat 中精确定位；`valid.dat` 是服务端文件名处理的历史注释，现实现为静态数组。不能将其他旧版 Samba 的外置 `.dat` 假设套用到当前组合。证据见 `provenance/samba-resource-audit.json`。

当前客户端必须实际准备并校验 `smb.conf`，以及可读 resource root、可写 state/cache 根目录与 state 下 private/state/lock 三子目录。可选 LMHOSTS 和动态模块不在当前 IP 直连 NAS 的验收范围；这不是对所有 Samba 可选功能的承诺。初始化实现不能用任意非空资源列表替代必要配置文件。

## FFmpeg 关闭恢复 SDK 接入

生产者合并提交 `32887363cb103163fe6557ca64c05539ad6d73f2`，SDK 来源为上游本地构建，非 CI 目标重建。`provenance/ffmpeg-recovery-sdk.json` 保存原始 217 项 SDK 清单，`ffmpeg-recovery-merge.json` 保存上游合并/归档绑定，`ffmpeg-recovery-compatibility.json` 保存本次实际 ABI/142 个头文件/归档核验。最终 Player HAR 仍须由 iMac 自托管 GitHub Actions 构建。

Spec 017 已使用恢复 SDK 作为当前 mpv 链接输入；`normal-compile-binding.json` 与 `mpv-link-inputs.json` 记录此次实际构建，旧 source-lock exactReferences 仅保留历史基线追溯。当前六库和编译头文件均由恢复 SDK 锁定；六库无 TRACE/TEST/DIAGNOSTIC/EXPERIMENT，mpv 保持 TRACE，所有正常产物均无故障注入。两张 Samba 字符表逐字节匹配新库，偏移已更新。

## Spec 017 核心重建

`provenance/host-recovery-input.json` 锁定补丁、新增音频登记源码及预编译 SDK；`native/scripts/prepare-host-recovery-input.py` 校验并派生独立输入，不修改来源、不编译 FFmpeg。`native/tooling/normal-core` 导入封存 mpv/libplacebo 构建和审计工具，来源摘要见 origins.json，恢复 ABI 白名单为六个符号。命令和边界见该目录 README.md。

此次 MacBook Pro / Darwin arm64 构建得到 libmpv SHA-256 `814e4f02ced52a15a213fd9a0c54f37ffbbe6ca466df758bd04ab0a9fa901beb`，64 个公开导出、253 个链接输入及 56 个 libplacebo 归档成员已校验。静态/源码校验不证明真实 GPU 故障恢复；最终 HAR 仍须由 iMac CI 构建。
