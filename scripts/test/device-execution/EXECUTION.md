# 专用短测本地执行入口

当前代码可准备固定的签名/验签/安装/短测/清理事务，**尚未完成专用材料下的真实签名或真机执行**。`controller.py` 仍只负责只读预检；`imac.py` 默认仅输出 pending，不自动读取历史签名或连接设备。无本轮精确执行批准，不得把它拷到持钥 iMac 后直接运行受测 PR 代码。

## 已实现的检查

- `executor.py`：官方 `verify-app` 提取本次证书/profile、`verify-profile` 认证内容与有效期/bundle/设备、精确 profile 字节与证书 DER 绑定、SID 实际 signer 匹配、unsigned/signed 全 ZIP 有效载荷比较。
- `imac.py`：外部事务授权摘要、固定专用 bundle、工具字节锁、签名前后 approved unsigned 摘要、系统安装元数据、独立 PID/内核 startTicks、设备时间窗口、新 nonce 事件、全事务锁和持久清理 journal。
- 签名证书链顺序不能证明实际 signer。`signer-helper/ActualSigner.java` 使用同一已锁官方 jar 的 SignerInfo SID 唯一匹配实际签名证书，拒绝批准证书仅作为额外链成员出现；精确 class SHA 必须由外部配置批准，不能取自产物自报。class 在本地/云端编译，iMac 不编译。
- 短测只使用专用包内合成媒体；真实首帧、进度推进、暂停至少 1 秒、恢复、10 秒 seek、关闭重开、EOF、release、保屏 false 和 session-end 均必须符合实际共用 `SmokeSession` 事件格式，整体不超过 120 秒。异常、晚到 player-error、旧 nonce/进程、缺证均拒绝。

工具观察锁为 `device-tools.observed.json`：它不是执行批准，不改变默认 SDK。CLI 1.2.0 当前是主体加本包 `node_modules`，没有独立 common 包；整树 4620 文件/76,899,574 字节摘要包含实际依赖。事务入口核全闭包；实际调用 CLI 时重核其闭包，HDC 查询仅核本次 HDC/控制器，Java 调用核 Java/JAR/helper。采样循环不重复 CLI 盘点，使用固定 HDC 的新鲜连接、UDID、PID/startTicks；断连不尝试全局重启 HDC。

## 本机入口与审批格式

安全缺省：

```sh
python3 -B scripts/test/device-execution/imac.py
```

返回 pending、退出码 2，不执行工具或设备写入。执行前需将已审不可变控制器和已批准 helper class 放在独立可信目录；不能 checkout 待测 PR 执行其脚本。固定本机状态目录为 `/Users/shiningyao/Library/Application Support/VidAllDeviceExecution/tv-192.168.3.85-5555`，父目录准备和权限属于后续配置预览，不在本轮自动创建到 iMac。

获批后的命令形状：

```sh
python3 -B /受信任已审目录/imac.py --execute \
  --artifact /批准的unsigned-artifact.zip \
  --artifact-approval /批准的制品envelope.json \
  --execution-approval /批准的本次事务.json \
  --execution-approval-sha256 <外部批准的事务文件SHA256> \
  --signing-config /本机专用签名配置.json \
  --tools-lock /已批准的device-tools.observed.json \
  --state-directory '/Users/shiningyao/Library/Application Support/VidAllDeviceExecution/tv-192.168.3.85-5555'
```

事务文件精确字段：`schemaVersion=1`、`purpose=device-smoke-local`、32 位十六进制 `nonce`、`bundleName=com.yaoshining.vidalldeviceprobe`、`deviceSerial=192.168.3.85:5555`、真实设备 `deviceIdSHA256`、`controllerSHA256`、`artifactApprovalSHA256`、`toolLockSHA256`、`signingConfigSHA256`、`mode=normal-local-smoke`、`allowInstall=true`、`allowUninstallOwnBundle=true`、Unix 秒 `expiresAt`。控制器摘要按 `controller_identity()` 的固定文件名及原始字节计算；外部审查后批准，不能从未经审查的文件现算现批。每个 nonce 只能使用一次。

签名配置精确字段：`schemaVersion=1`、同 bundle/真实 `deviceIdSHA256`、`profileFile/profileSHA256`、`certificateFile/certificateDER_SHA256`、`keystoreFile/keystoreSHA256`、`keyAlias`、`passwordMode=interactive-local`、`signerHelperClassPath/signerHelperClassSHA256`。所有路径必须为本机明确绝对路径。完整配置摘要由事务文件绑定；私钥只读本人文件、无组/其他用户权限。不要把私钥、口令、完整 profile 或设备白名单发聊天、进仓库或公开日志。

首阶段只支持官方 `sign-app -pwdInputMode 1` 交互终端输入，口令不放 argv/环境变量，非交互环境明确 pending。**IDE 自动生成证书/profile 不保证用户知道 keystore 口令，也不证明 CLI 可使用。** 尚未验证这些专用材料的口令供给；不会解密/打印 IDE 管理密码或复用 TV 签名。若用户无法安全输入，继续 pending，需要用户自行准备/导入可控口令的专用测试 keystore 并匹配证书/profile；账号/本机材料配置须另给准确预览。未来 Keychain 无人值守方案未实现、未配置。

同一事务内正式 `verify-app`/`verify-profile` 输出必须是全新目录中的真实文件；旧输出或 exit 0 无输出不通过。所有摘要在安装前再次绑定，不能 unsigned 和 signed 同时替换后自算新摘要通过。系统包信息 fingerprint 和 versionCode 必须匹配，安装前未知同 bundle 一律不覆盖、不自动卸载。

## 清理与恢复

仅本轮明确安装成功并核身份的包允许 force-stop/uninstall。签名等待期间出现其他同 bundle，或安装超时结果未知，即使证书/version 相同也不能视为本轮所有物。

正常路径要求应用 release/保屏 false 回读，再核本会话进程、Ability、Window 与包卸载。异常强停无法应用回读时保持 `appSelfCleanup=unconfirmed`；系统级退出证明与应用自清理分开。pid 查询错误/timeout/空错误输出不当 absent；窗口表必须完整且没有本 PID，不只搜索 bundle 字符串。

断连或清理未知留下 `journal.json` 阻止下一事务；不会通过删除 journal 解锁。`--recover` 使用同一批准 nonce/制品与配置，只核旧事务后有界清理，不签名、安装或启动。恢复额外要求已核的安装生命周期 `installTime/updateTime` 与当前包一致；缺失、格式未知、重装后变化、PID/startTicks 变化均保持未知，不 stop/uninstall 新进程。尚未有目标设备的真实 `bm dump`/Window dump 格式兼容证据，这些解析仅通过宿主替身测试；真实设备 schema 不满足时失败关闭，不虚构字段。

固定命令参考官方 [bm 工具说明](https://github.com/openharmony/docs/blob/master/en/application-dev/tools/bm-tool.md) 与 [包签名 fingerprint 说明](https://github.com/openharmony/docs/blob/master/en/application-dev/quick-start/common-problem-of-application.md)。`devecocli device list` 优先盘点；直接使用固定 HDC 是为避免 `run` 隐式构建并支持已核 HAP 安装、独立状态及清理查询。iMac 不运行 npm/ohpm/Hvigor/CMake/clang。

本机仅自动清除本进程临时目录，保留持久 journal/nonce 账本；不修改用户签名材料。结果 `installedPayloadVerified` 只指签名与全载荷一致、九库摘要和安装记录；`runtimeMappedLibraryHashVerified=false`，没有读取进程映射逐字节哈希。真实短测通过也不扩展到 HDR、主观听音、NAS 长播或九套 Hypium。

## 测试与尚未启用的部分

```sh
python3 -B scripts/test/device-execution/controller.test.py
python3 -B scripts/test/device-execution/executor.test.py
python3 -B scripts/test/device-execution/imac.test.py
```

后两组运行真实适配函数，但平台输出是替身；正常 trace 直接来自真实 `SmokeSession` 宿主执行，不能称官方签名/设备验收。helper 单独测试命令见其 README，使用同锁 jar 的真实 SID/证书逻辑和临时合成证书，不是目标设备受信签名。

本轮只准备云端同源 unsigned HAP 构建与独立上传工作流，7 天保留；尚未推送/上传。新增合成 MP4 543,702 字节，不能将提交描述为纯文本；未来 unsigned HAP 约 55 MB。制品 source 支持既有 `merge_group` 事件，但要求 headSHA 与实际 group checkout/eventMergeSHA 相同；不能借用 PR head。此兼容不新增远端环境或审批权限。iMac GitHub 手动入口、专用 label/环境/Secret 在首次本地真实闭环后另提，当前没有启用。真实签名材料/口令可用性、设备 schema、实际短测、HDR/听音均继续待验收。
