# 实施计划：受控 direct SMB

## 技术路径

1. 将 `smb` 增加为公开 `MediaSource.kind`，但不增加凭据字段；输入校验只接受无 userinfo 的绝对 `smb://` URI。
2. 由内部 `DirectSmbCapability` 注入受控构建的能力状态。未验证时拒绝，避免 ArkTS 状态机伪造播放成功。
3. 在 `sources.lock.json` 中记录 Samba/libsmbclient 及其已完成的静态传递依赖闭包（GnuTLS、popt、zlib、GMP、Nettle、libtasn1）和 OpenHarmony `pkg-config` 交叉编译约束；构建脚本必须在来源、静态 sysroot 与构建证明齐全前失败，不得下载或执行未锁定的上游脚本。
4. 将 SMB sysroot 的静态库、头文件和 `smbclient.pc` 注入 FFmpeg/mpv 共用的构建目录；FFmpeg 显式使用 `--enable-gpl --enable-libsmbclient`，mpv 使用 `-Dgpl=true`。ELF 审计必须禁止动态 `libsmbclient.so`，并在 SBOM/NOTICE/source offer 中跟踪 GPLv3 义务。
5. 真机 ARM64 TV 使用已批准的脱敏服务器样本验证首帧、seek、认证失败、断网重连和释放；缺失证据保持“已构建待验证”。

## 当前可交付边界

当前已完成可测试的公开 URI 校验、能力门禁，以及 ARM64 静态 Samba 依赖闭包的受控构建。FFmpeg/libmpv 的 GPLv3 构建配置与 SMB sysroot 注入已纳入构建链；CI 会在同一次 `build-libsmbclient` 成功后下载该 sysroot、执行真实 ARM64 libmpv 交叉编译，并审计 ELF 不含动态 `libsmbclient.so`。仍须取得该构建的实际成功制品和 API 22 TV 运行时验证。虽然发现一台 API 23 TV，但它不符合 API 22 验收目标，且当前 HAP 未配置签名，不能部署；因此不能生成或宣称 direct SMB 已通过运行时/真机验证。Run `30393247171` 仍在 SMB sysroot 校验步骤退出，日志未标示失败断言；现已为下载目录、`find` 错误、静态归档、pkg-config 文件和头文件检查加入具名诊断，并由契约测试锁定，避免继续猜测 artifact 或 runner 路径。
