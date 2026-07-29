# 功能规格：受控 libmpv direct SMB 播放

**分支**：`yaoshining-libmpv-direct-smb`
**日期**：2026-07-27
**Issue**：#41

## 用户场景与验收

用户可以通过公开 ArkTS API 传入不含 userinfo 的 `smb://host/share/path` URI。若服务器允许匿名访问，播放器不注入凭据；若服务器要求认证，凭据只能通过内部原生桥接的运行时安全通道提供，不能出现于 URI、公开类型、事件、日志、SBOM、审计或制品。

- 受控构建必须锁定 Samba/`libsmbclient` 及其传递输入、许可证和构建开关，并使 FFmpeg 显式启用 `--enable-libsmbclient`。
- 运行时必须基于随受控构建交付的能力证明判断 direct SMB 是否可用；证明缺失、过期或声明未启用时，稳定拒绝加载并不得声称支持。
- `smb://` URI 必须拒绝 userinfo、空主机和不安全格式；`localhostProxy`/lease 保持原有行为。
- 测试至少覆盖匿名 URI、含 userinfo 的 URI、能力缺失、认证失败、断网、Range/seek、重连与释放后调用。真机媒体结果只能以 ARM64 API 22 TV 证据标记为通过。

## 非目标

- 不改变现有 `localhostProxy` 或业务层代理 lease 的职责。
- 不在公开 ArkTS API 暴露 SMB 用户名、密码、令牌、native handle 或内部凭据注入接口。
- 在未获得受控构建和真机证据前，不将 direct SMB 标记为已支持。

## 约束

- 公开 API 可接收无凭据 `smb://` URI；服务器认证由仅内部原生桥接在运行时处理。
- 所有日志、错误和证据必须脱敏，不能包含完整 SMB 路径、查询或凭据。
- 仅承诺 `aarch64-linux-ohos` / ARM64 TV；API 15 安装兼容、API 19 审查、API 22 认证。
