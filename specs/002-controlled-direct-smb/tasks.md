# 任务：受控 direct SMB

- [X] T001 先写 ArkTS 测试，覆盖匿名 `smb://`、userinfo 拒绝、未验证能力拒绝和 `localhostProxy` 不回归。
- [X] T002 实现 `MediaSource.kind='smb'`、URI 校验和内部能力门禁；公开接口不得包含 SMB 凭据。
- [X] T003 先写受控构建配置测试，验证 Samba 锁定、FFmpeg `--enable-libsmbclient`、`pkg-config` 隔离与 ELF 白名单要求。
- [X] T004 实现来源锁、受控构建配置和 ELF/SBOM/NOTICE 门禁；缺少完整来源或交叉工具链必须失败。
- [X] T005 添加与 WebDAV 一致的 SMB 连接配置界面：持久化服务器/共享/路径/用户名，密码仅保留当前会话，并始终构造不含 userinfo 的 `smb://` URI。
- [ ] T006 在 ARM64 API 22 TV 执行匿名/认证、首帧、seek、断网、重连和释放验证并归档脱敏证据。
