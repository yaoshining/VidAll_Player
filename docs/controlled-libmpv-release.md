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

随后验证两次独立制品：

```bash
native/scripts/verify-reproducible-artifacts.sh \
  --first <第一次/libmpv.so> \
  --second <第二次/libmpv.so> \
  --output dist/libmpv/arm64-v8a/reproducibility.json
```

## 许可证门禁

MPV 为 GPL-2.0-or-later，FFmpeg、libplacebo 与 FriBidi 等可能带来 LGPL 义务。`license-audit.json` 的 `review-required` 是发布阻断条件：必须确认实际链接方式、启用的 FFmpeg 编解码器、完整许可证文本、NOTICE 和对应源码获取方式后，才能签出 release tag。

发布 tag 必须附带 changelog、已知限制、上述全部审计制品和可重复构建报告。当前受控脚本不包含交叉工具链适配层，不能将其“跳过编译”模式解释为生产构建已经完成。
