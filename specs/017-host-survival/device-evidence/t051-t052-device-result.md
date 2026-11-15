# T051 / T052：API24 音频初始化恢复与剩余收证

日期：2026-11-14。生产候选 c7d56ee；iMac 自托管 CI 43464070369 全部通过，原始 HAR 与九库见 t051-ci-preparation.json。独立 HAP 为本地 MacBook Pro 构建，不冒充 CI HAR 或 API19 TV 验收。

## 设备与初始化实测

实际分配 MatePad Mini / MLR-AL10 / 6.1.0.125(SP20C00E125R1P4) / API24 / ARM64，免费调试；没有购买或切换手机。

1.0.55（无录音干扰）PID61107，00:42:06 与00:42:11两次OHAudio打开均出现 `using soft-buffer of 9600 samples`，之前1.0.54的回调登记错误3不再出现。此处soft-buffer是音频缓冲，不代表视频转成软解。

同一PID的P17记录覆盖坏片NATIVE_PLAYBACK_FAILED→released→bad-media-returned、新会话2首帧、暂停前后进度均833.333ms、恢复到1566.667ms、seek到20066.667ms、正常release、新会话3首帧及关闭；summary firstFrames=2/errors=0。实时diagnostics标识decoder=ohcodec/backend=vulkan。见 t051-mini-init.txt 与 t051-startup-events.txt。

这支持T051回退在该设备修复了初始化路径；没有逐分支运行时日志，不能将具体dlsym调用结果写成直接观测。该无录音轮次没有实际音轨，不算声音验收。

## 系统打断与录音

1.0.56两轮在录屏授权往返阶段CAPTURE_START_TIMEOUT，未进入播放；不能归为Player播放/打断失败，也不能据此证明录音器不支持。

T052仅把独立工具真实STARTED等待从15秒改为有界60秒，非法/非有限参数拒绝。虚拟时钟红绿覆盖15秒后授权成功、60秒仍未开始失败、迟到事件不成功、无界参数不创建资源。12组生命周期与其余4套工具回归、ArkTS构建/九库一致性通过。1.0.57和c7d56ee CI原HAR九库完全一致，见t052-preparation.json。

1.0.57实际出现系统授权面板，确认后capture-state=0、capture-started=1794588735148；画面出现正常视频及“打断已解除，请手动继续播放”。该状态按验收页面控制流意味着已走到系统暂停及解除后保持暂停检查之后，但本轮原生日志尚未取回，不将页面状态替代完整事件/音轨证据。

随后发出一次手动继续点击（uitest click 460 340，Shell返回No Error）。取P17日志时华为云明确提示登录失效，返回登录页；浏览器当时仅展示旧PID61107缓存，不能冒充1.0.57的日志。手动继续后的进度、当前PID、实际声音与完整录音尚未确认。暂停等待截图本机保留在 /tmp/spec017-t052-await-manual.png。

## 剩余项

四项Todoist仍0/4：第1项已修初始化且观察到等待手动恢复，第2项当前故障包仍须同步新核心及完成真实音轨，第3项永久音频Stop/Release未知状态边界未解决，第4项待前置，不创建PR。API26历史CppCrash仍未复验，API19 TV正式入口独立待验。

当前实际阻塞为华为云登录失效，已请求扫码；不能声称正在自动等待设备。失效时会话已使用约14分钟，未获明确释放成功，剩余时段按平台会话上限结束，重新登录后需核实分配状态。

## 重新登录后的独立重跑

用户扫码后登录恢复，原会话已结束；重新分配同版本Mini并安装1.0.57。运行前后pidof均23494。实际capture-started=1794589321675，画面等待手动继续后点击一次。P17日志捕获到focus-flow-completed-audio-pending、后续暂停进度7466.667ms保持不变、恢复10466.667ms、seek20566.667ms、实际ohcodec/vulkan、session3新首帧、summary(firstFrames=2,errors=0)、capture stop/release返回、capture-closed=1794589362776。

见t052-rerun-events.txt；当前日志从focus-flow-completed开始，早期系统打断/手动恢复逐事件未捕获，不能把后续普通pause/resume日志冒充系统打断原始日志。系统日志仅取得01:02:35/music/hintType3，见t052-rerun-system.txt，不能将其说成前面Alarm的PAUSE决策。完整事件文件及实际MP4仍未导出。

点击导出并释放后返回机型列表，下载等待未返回文件。当前无占用设备；准备T054通过工具显式导出本应用自生成证据，使用平台已有剪贴板同步，不读其他应用或绕过文件权限。
