# 设备制品与固定控制器契约（方案，尚未启用）

## 云端 unsigned 制品清单

`schemaVersion`、`repositoryId=1307243374`、`repository=yaoshining/VidAll_Player`、`workflowPath`、`workflowSHA`、`runId`、`runAttempt`、`event`、`headSHA`、`eventMergeSHA`、`sourceTreeSHA`、`sourceTrackedBytesSHA256`、`toolchainLockSHA256`、`releaseSourceLockSHA256`、`inputHAR_SHA256` 必需且来源一致。workflow必须固定为获审云端构建入口，run/attempt成功且实际checkout是已审事件；不能只取文件名或最新artifact。

包内manifest字段：包成员路径白名单、unsignedHAPBytes/SHA256、bundleName、moduleName、abilityName、minAPI15/targetAPI22、九库各SHA、`media`的rawfile路径/bytes/SHA/生成器SHA/参数/合成来源说明、测试模式白名单、测试入口源码摘要。archive内重复/逃逸/符号链接/缺失媒体/其他包必须拒绝。上传后另建外部approval envelope，绑定runId/runAttempt/artifactId/GitHub ZIP digest与包内manifestSHA；这些值只能来自已核GitHub元数据和人工精确预览，不回写已上传ZIP。包内不包含尚不存在的artifactId或ZIP自身digest，避免自引用。下载后核外部envelope→整个ZIP→manifest→HAP/成员；自称hash却无外部绑定、错误attempt或缺envelope均拒绝。

测试包应独立于TV生产包，专用bundle名称最终签名预览时固定；尚无已批准名称/profile，不能把当前consumer包当可安装包。普通consumer仍可不带媒体做编译验证，不能因此省略device-package的媒体门禁。

## iMac 本地签名

固定 `unsignedHAP_SHA256` → `signedHAP_SHA256`；本地配置只提供明确的signer工具路径/SHA、JRE路径/SHA、证书SHA/指纹、profile SHA/bundle/有效期/允许设备、key alias与安全取密方式。签名材料需用户专项提供，不自动探测~/.ohos/config，不复用TV生产材料、不在日志输出口令或profile设备清单。

用实际官方验签工具核签名和profile，验签失败不可安装。签名前后全部有效载荷成员（除标准签名元数据块）必须同集合/同bytes/SHA，九库/模块API/bundle/媒体分别复核。不得仅比九库而遗漏ArkTS代码/资源变化。云端unsigned输入及其原始证据保持不可改写。signed包/profile只在iMac受控私有目录，运行后按批准保留期清理；不上传公开Actions artifact。

当前签名材料缺失时状态为 `signing_ready=false / deviceVerified=false / pendingReason=signing-material-missing`，不能制造假签名或把unsigned包安装失败算测试失败。

## 可信执行与工具

仅手动执行，控制器固定已审commit及脚本SHA，来源为默认分支/明确受信任不可变版本，不执行任意PR checkout、包内脚本或用户给的shell/URL。构建相关npm/ohpm/Hvigor/CMake/clang均不得出现在iMac执行路径；签名与验签是显式单独动作，不允许借签名恢复编译。

`devecocli device list`用于设备盘点；低层固定HDC安装/aa test/日志采集若CLI不足则记录例外及SHA。root当前只读发现HDC SHA `7469af52a47d2334b44b2ed6c09b5d9e6c17d0ca45ff37eaa95bb0234cd66f95`、serial `192.168.3.85:5555`，实际启用前仍需新鲜核验，不将历史在线当当前在线。

GitHub拟专用label `vidall-device-imac`，精确runner21；concurrency固定设备组且cancel-in-progress=false，加本机进程锁，已有占用则待验，不抢占。准备、签名、安装、运行、结果、cleanup均绑定同一个sessionId。下载只需本仓Actions read，iMac不需要私有SDK缓存PAT。安装/停止只能针对批准测试bundle；禁止修改系统保屏、重启全局HDC、操作TV应用。

## 结果

`deviceVerified=true`只能来自已核工具/身份/包/设备/已审测试模式完整执行，包含实际初始化/首帧/测试报告完成标志/预期断言/错误计数/应用保屏释放与本次进程窗口退出。设备offline/认证拒绝/测试缺报告/超时/清理缺证必须区分pending/failed，不能用GitHub job成功覆盖这些字段。物理HDR/听音不在自动短场景验收内。
