# 实施计划：受控 direct SMB

## 技术路径

1. 将 `smb` 增加为公开 `MediaSource.kind`，但不增加凭据字段；输入校验只接受无 userinfo 的绝对 `smb://` URI。
2. 由内部 `DirectSmbCapability` 注入受控构建的能力状态。未验证时拒绝，避免 ArkTS 状态机伪造播放成功。
3. 在 `sources.lock.json` 中记录 Samba/libsmbclient 及当前已知传递依赖（GnuTLS、popt、zlib）和 OpenHarmony `pkg-config` 交叉编译约束；构建脚本必须在源码和构建证明齐全前失败，不得下载或执行上游脚本。
4. 在 ELF 审计中显式允许并验证 `libsmbclient.so`，在 SBOM/NOTICE/source offer 中跟踪其许可证。
5. 真机 ARM64 TV 使用已批准的脱敏服务器样本验证首帧、seek、认证失败、断网重连和释放；缺失证据保持“已构建待验证”。

## 当前可交付边界

本次先实现可测试的公开 URI 校验、能力门禁和受控构建配置门禁。当前 Samba 传递依赖闭包被明确标记为待解析，构建脚本会拒绝生成 direct SMB 制品。虽然发现一台 API 23 TV，但它不符合 API 22 验收目标，且当前 HAP 未配置签名，不能部署；因此不能生成或宣称 direct SMB 已通过运行时/真机验证。
