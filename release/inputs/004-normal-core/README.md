# 正常核心输入（独立接入）

当前输入来自 Phase31 已验证的 Phase30 A TRACE-only 组合。8 个动态库的 SHA 与正常 HAP 完全相符；MPV 公开头来自精确匹配二进制的 `mpv-trace-c` 安装输出，SMB 公共头来自其配套 FFmpeg staging。`manifest.json` 是本目录唯一绑定入口，运行 `python3 -B scripts/audit/normal-core-verify.py` 校验。

`provenance/source-lock.json` 绑定精确生产者源码/补丁索引、静态 libplacebo、工具链及历史来源限制。`provenance/sbom.json` 列出运行库和静态链接输入，许可证正文与生产者完整索引位于 `licenses/`。此处的来源索引不宣称已复制全部源码构建闭包；离线接收者要重建时还需按精确引用取得生产者封存输入。索引校验与法律合规发布审核是不同验收层级。

静态 libplacebo 已链接进 mpv，不再重复打包 .a；头文件保持原始上游内容。Python 目标路径修复由生产者输入锁继承，未修改或回滚。

本目录是新独立组合，旧候选/TV 不替换，`formalArtifactAllowed=false`。HAR 打包完整动态库后，未来 TV 接入必须同时移除旧六库，禁止新旧混装。低 API 真机、物理 HDR 等未验证项不因输入审计通过而转为完成。

## 输入门禁与 TDD

`python3 -B native/tests/normal-core-input.test.py` 执行 15 个实际输入正例与篡改负例；`python3 -B scripts/audit/normal-core-verify.py --verify-external` 另核验本机生产者精确来源引用。前者不要求将生产者源码复制到消费仓库，后者要求原封存可读。首次 RED 是输入未接入的实际清单缺失；实现后完整门禁通过。详细阶段和保留失败界限见 `INPUT-VERIFICATION.json`。

可信 producer binding、实际编译证据和 source-lock 的 SHA 固定在校验器中；修改清单自报不能绕过。ABI 接受 ELF 符号版本后缀，必须包含固定最小 terminal/SMB 导出集合，空列表不通过。资源 `smb.conf` 属于输入内容校验，运行时目录与权限由 Player 初始化另行负责。

## Samba 资源边界

当前字符表由精确 Samba 源码内嵌：`codepoints.c` 的 `lowcase_table` / `upcase_table` 各 65,536 个 uint16，完整 131,072 字节都能在当前 avformat 中精确定位；`valid.dat` 是服务端文件名处理的历史注释，现实现为静态数组。不能将其他旧版 Samba 的外置 `.dat` 假设套用到当前组合。证据见 `provenance/samba-resource-audit.json`。

当前客户端必须实际准备并校验 `smb.conf`，以及可读 resource root、可写 state/cache 根目录与 state 下 private/state/lock 三子目录。可选 LMHOSTS 和动态模块不在当前 IP 直连 NAS 的验收范围；这不是对所有 Samba 可选功能的承诺。初始化实现不能用任意非空资源列表替代必要配置文件。
