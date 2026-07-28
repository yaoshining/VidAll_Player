# libmpv 受控发布流程

## 发布输入

- `native/config/sources.lock.json` 是唯一允许的上游来源清单。所有来源必须固定为 40 位 Git commit，禁止使用分支、浮动 tag、预编译 release 或未审计的外部构建脚本。
- 在隔离的 OpenHarmony SDK 容器中检出锁定的来源，并保留 FFmpeg configure 选项、MPV Meson 选项及组件列表。
- 设置 `SOURCE_DATE_EPOCH` 为发布提交时间，并在相同源码、工具链和配置下完成两次独立构建。

## 生成与审计

将已构建的 `libmpv.so` 及构建元数据置于受控来源目录后运行：

```bash
native/scripts/build-libmpv-controlled.sh \
  --source <受控源码目录> \
  --output dist/libmpv/arm64-v8a \
  --skip-compile
```

该命令生成 `libmpv.so.sha256`、feature manifest、SPDX/CycloneDX SBOM、`NOTICE`、许可证审计和 ELF 审计报告。ELF 审计只允许 `libc++.so` 与 `libhilog_ndk.z.so`；新动态依赖必须先完成安全与兼容性审查。

候选发布前还必须校验 `release/capabilities/arm64-tv-capability-evidence.json`：

```bash
native/scripts/validate-capability-evidence.sh \
  --input release/capabilities/arm64-tv-capability-evidence.json
```

校验器只接受"已通过真机样本"、"已构建待验证"和"不支持或暂缓"。真机通过项必须提供匿名 ARM64 TV、匿名样本、执行时间、指标和证据文件；未验证项禁止填充这些字段，也禁止在 README 或发布说明中宣称已支持。

随后验证两次独立制品：

```bash
native/scripts/verify-reproducible-artifacts.sh \
  --first <第一次/libmpv.so> \
  --second <第二次/libmpv.so> \
  --output dist/libmpv/arm64-v8a/reproducibility.json
```

## 许可证门禁

MPV 为 GPL-2.0-or-later；受控 SMB 路径静态链接 Samba `libsmbclient`（GPL-3.0-or-later），并要求 FFmpeg 使用 `--enable-gpl --enable-libsmbclient`、mpv 使用 `-Dgpl=true`。因此，包含该 SMB 路径的最终 `libmpv.so` 和随附制品按 GPLv3 发布，不能以 LGPL 或无 SMB 支持的制品描述替代。

`license-audit.json` 的 `review-required` 是发布阻断条件：必须确认静态链接方式、完整 Samba 传递依赖闭包、启用的 FFmpeg 编解码器、完整许可证文本、NOTICE，以及与对应精确源码和构建脚本一同提供的源码获取方式后，才能签出 release tag。ELF 审计必须禁止动态 `libsmbclient.so`；SMB 代码只能通过受审计的静态闭包进入最终制品。

发布 tag 必须附带 changelog、已知限制、上述全部审计制品、可重复构建报告和 GPLv3 源码提供说明。当前受控脚本不包含完整交叉工具链适配层，不能将其“跳过编译”模式解释为生产构建已经完成。
