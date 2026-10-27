# 专用短测本地执行入口

当前专用手动材料已通过真实官方签名、verify-app/profile、实际Signer SID、同unsigned精确派生`.pages.info`与原载荷校验。Round7首次安装及身份核验通过，但宿主拒绝终态事件序列，原清理联合门禁未确认；原始事件已删除，具体失败分项不能追认。后验只读确认设备无残留，原journal仍为`cleanup-unknown`。本次修复保留安全事件/准确错误码/逐项清理与独立最终结果，仅本地测试与审查通过，尚无新设备结果。

`controller.py`仍只读预检，`imac.py`缺完整参数时仅输出pending。每次部署、签名和设备执行均需要当前代码及输入的精确批准，不能直接在持钥iMac checkout受测PR运行。

## 已实现的检查

- `executor.py`：官方 `verify-app` 提取本次证书/profile、`verify-profile` 认证内容与有效期/bundle/设备、精确 profile 字节与证书 DER 绑定、SID 实际 signer 匹配、unsigned 原成员逐字节一致及官方精确派生 `.pages.info` 比较。
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

签名配置精确字段：`schemaVersion=1`、同 bundle/真实 `deviceIdSHA256`、`profileFile/profileSHA256`、`certificateFile/certificateDER_SHA256`、`keystoreFile/keystoreSHA256`、`keyAlias`、`passwordMode=interactive-local`、`signerHelperClassPath/signerHelperClassSHA256`、`pagesHelperClassPath/pagesHelperClassSHA256`、`pagesInfoSHA256/pagesInfoBytes`。所有路径必须为本机明确绝对路径。完整配置摘要由事务文件绑定；私钥只读本人文件、无组/其他用户权限。不要把私钥、口令、完整 profile 或设备白名单发聊天、进仓库或公开日志。

首阶段只支持官方 `sign-app -pwdInputMode 1` 交互终端输入，口令不放 argv/环境变量，非交互环境明确 pending。**IDE 自动生成证书/profile 不保证用户知道 keystore 口令，也不证明 CLI 可使用。** 当前手动专用材料已由用户在官方TTY成功解锁，后续完整验签与有效载荷总门禁通过；口令始终未由代理读取。官方两次密码提示各30秒，输入不回显并需回车；没有延长提示时限。不会解密/打印 IDE 管理密码或复用 TV 签名。若用户无法安全输入，继续 pending，需要用户自行准备/导入可控口令的专用测试 keystore 并匹配证书/profile；账号/本机材料配置须另给准确预览。未来 Keychain 无人值守方案未实现、未配置。

同一事务内正式 `verify-app`/`verify-profile` 输出必须是全新目录中的真实文件；旧输出或 exit 0 无输出不通过。所有摘要在安装前再次绑定，不能 unsigned 和 signed 同时替换后自算新摘要通过。系统包信息 fingerprint 和 versionCode 必须匹配，安装前未知同 bundle 一律不覆盖、不自动卸载。

## 清理与恢复

仅本轮明确安装成功并核身份的包允许 force-stop/uninstall。签名等待期间出现其他同 bundle，或安装超时结果未知，即使证书/version 相同也不能视为本轮所有物。

正常路径要求应用 release/保屏 false 回读，再核本会话进程、Ability、Window 与包卸载。异常强停无法应用回读时保持 `appSelfCleanup=unconfirmed`；系统级退出证明与应用自清理分开。pid 查询错误/timeout/空错误输出不当 absent；窗口表必须完整且没有本 PID，不只搜索 bundle 字符串。

断连或清理未知留下 `journal.json` 阻止下一事务；不会通过删除 journal 解锁。`--recover` 使用同一批准 nonce/制品与配置，只核旧事务后有界清理，不签名、安装或启动。恢复额外要求已核的安装生命周期 `installTime/updateTime` 与当前包一致；缺失、格式未知、重装后变化、PID/startTicks 变化均保持未知，不 stop/uninstall 新进程。包清单、UDID 与 Window 表格已有目标设备只读格式证据；Round7安装后的 `bm dump -n` 身份/生命周期已匹配实际格式，真实设备 schema 不满足时失败关闭，不虚构字段。

固定命令参考官方 [bm 工具说明](https://github.com/openharmony/docs/blob/master/en/application-dev/tools/bm-tool.md) 与 [包签名 fingerprint 说明](https://github.com/openharmony/docs/blob/master/en/application-dev/quick-start/common-problem-of-application.md)。`devecocli device list` 优先盘点；直接使用固定 HDC 是为避免 `run` 隐式构建并支持已核 HAP 安装、独立状态及清理查询。iMac 不运行 npm/ohpm/Hvigor/CMake/clang。

本机仅自动清除本进程临时目录，保留持久 journal/nonce 账本；不修改用户签名材料。结果 `installedPayloadVerified` 只指签名与全载荷一致、九库摘要和安装记录；`runtimeMappedLibraryHashVerified=false`，没有读取进程映射逐字节哈希。真实短测通过也不扩展到 HDR、主观听音、NAS 长播或九套 Hypium。

## 测试与尚未启用的部分

```sh
python3 -B scripts/test/device-execution/controller.test.py
python3 -B scripts/test/device-execution/executor.test.py
python3 -B scripts/test/device-execution/imac.test.py
```

后两组运行真实适配函数，但平台输出是替身；正常 trace 直接来自真实 `SmokeSession` 宿主执行，不能称官方签名/设备验收。helper 单独测试命令见其 README，使用同锁 jar 的真实 SID/证书逻辑和临时合成证书，不是目标设备受信签名。

首阶段历史：当时只准备云端同源 unsigned HAP 构建与独立上传工作流，7 天保留。当前已完成云端 run 40177077035 attempt 2，并冻结 artifact 12592874084；不得把该CI结果扩展为本轮新执行器的CI通过。新增合成 MP4 543,702 字节，不能将提交描述为纯文本；未来 unsigned HAP 约 55 MB。制品 source 支持既有 `merge_group` 事件，但要求 headSHA 与实际 group checkout/eventMergeSHA 相同；不能借用 PR head。此兼容不新增远端环境或审批权限。iMac GitHub 手动入口、专用 label/环境/Secret 在首次本地真实闭环后另提，当前没有启用。当前手动材料/alias/TTY口令及安装身份schema已实际验证；短测、原清理联合门禁及HDR/听音仍未验收。本次提交只含执行器相关文本，不含既有MP4/HAP/库或新二进制上传。

## Round3 精确派生与失败证据

锁定官方 JAR 的 `SignProvider.copyFileAndAlignment` 在 alignment=4、signCode=1 时生成 `.pages.info`。签名命令显式使用 `-signCode 1`；公开CLI不接受 `-a`，alignment使用同锁JAR已核默认4；`pages-helper/ExpectedPages` 从外部批准的 unsigned 字节独立派生，运行时核 JAR 与输入摘要，拒绝输入已有该成员。helper class 和预期派生 SHA/长度均在外部签名配置中固定，启动及每次 Java 调用重核，不从 signed 提取后自证。原成员仍逐字节相等，不泛化豁免 `META-INF` 或未知新增文件。

不一致时最多记录32项名称摘要/长度及成员内容摘要/长度；仅固定 `.pages.info`、`module.json`、`ets/modules.abc` 可记明文名称。异常属性须通过固定schema重新构造，不保存原内容、profile或stderr。专属结果在外层finally删除临时包前保存。Round2实际signed已清理，官方无私钥复现只能说明预处理机制；这是Round3执行前历史状态；后续实际通过及Round7失败边界以上述当前状态为准。

Round3显式-a4曾被真实CLI拒绝，未生成签名包，13份副本已清理。Round4新增 `sign-cli-contract.test.py`：从真实prepare_signed捕获argv，进入同锁官方CmdUtil解析，不调用签名；正常参数接受，追加-a4或未知参数拒绝。参数解析通过不等同真实签名/完整验签通过。

## 本次累计诊断修复与证据保存

每次成功读取的本nonce事件先于场景校验/卸载保存到`smoke-<nonce>.json`：已知固定APP错误码保留，未知名称/值仅记录有界长度/hash，绝不落密码、profile、原UDID或全TTY。损坏JSON保留可解析前缀与坏行摘要。每条清理命令立即保存退出/超时/输出摘要和固定语义，后续失败不抹掉前项；归属状态单独记录。

最终结果绑定已验证approval/controller、unsigned、可信PID/startTicks和真实签名摘要；签名/安装/场景/清理独立报告。中断明确失败状态，证据写入失败不会阻止原归属门禁下的必要清理，也不能报告通过。磁盘不可写或SIGKILL仅能依赖已完成的原子快照。状态目录700/记录600，拒nonce复用、软链接和摘要漂移。

旧cleanup-unknown对账尚未实现或批准，不可删除journal、更换state目录绕过。拟先锁下新鲜只读核对，再原字节归档失败journal并追加cleanup-only对账记录；是否更新可变事务头须另行精确批准，不能把旧场景改成passed。

129项Python测试已接既有host入口。`pages-helper/test.py`依赖冻结unsigned制品，`sign-cli-contract.test.py`只调用同锁官方公开参数解析；本次仅精确本地重放，未将二者接入云端，未新增制品下载或工作流。具体状态见`REPAIR-SUMMARY.json`，精确commit重放结果放仓外避免自引用。
